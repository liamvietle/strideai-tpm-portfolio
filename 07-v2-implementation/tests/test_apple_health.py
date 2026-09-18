from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main
from app.apple_health import (
    AppleHealthDailySummary,
    AppleHealthSyncInput,
    daily_state,
    upsert_apple_health,
)
from app.personal_models import DailyCheckInInput
from app.personal_service import build_accumulated_input, create_personal_recommendation


def _sync(days: list[AppleHealthDailySummary]) -> AppleHealthSyncInput:
    return AppleHealthSyncInput(
        athlete_id="viet",
        device_id="test-device-1234",
        app_version="1.0.0",
        generated_at=datetime.now(timezone.utc),
        summaries=days,
    )


def _run(day: str, **updates) -> DailyCheckInInput:
    values = {
        "athlete_id": "viet",
        "checkin_date": day,
        "planned_activity_type": "run",
        "planned_distance_km": 8,
        "planned_intensity": "easy",
        "human_decision": "maintain",
    }
    values.update(updates)
    return DailyCheckInInput(**values)


def test_sync_is_idempotent_and_builds_rolling_hrv_baseline(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "strideai.db"))
    days = [
        AppleHealthDailySummary(
            date=f"2026-09-{day:02d}",
            timezone="Asia/Ho_Chi_Minh",
            sleep_hours=6 + day / 100,
            sleep_sample_count=4,
            hrv_ms=40 + day,
            hrv_sample_count=3,
            resting_hr_bpm=45 + day / 10,
            resting_hr_sample_count=1,
            source_names=["Apple Watch"],
        )
        for day in range(1, 10)
    ]
    first = upsert_apple_health(_sync(days))
    second = upsert_apple_health(_sync(days))
    assert first.inserted == 9
    assert second.inserted == 0
    assert second.updated == 9

    state = daily_state("viet", "2026-09-09")
    assert state is not None
    assert state["source"] == "apple_health"
    assert state["hrv_baseline_days"] == 8
    assert state["hrv_baseline_low"] is not None
    assert state["hrv_baseline_high"] is not None
    assert "device_id" not in state


def test_health_data_hydrates_today_and_unchecked_history(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "strideai.db"))
    upsert_apple_health(
        _sync(
            [
                AppleHealthDailySummary(
                    date=f"2026-09-{day:02d}",
                    timezone="Asia/Ho_Chi_Minh",
                    sleep_hours=4.0 + day / 10,
                    hrv_ms=55 + day,
                    resting_hr_bpm=47,
                )
                for day in range(1, 9)
            ]
        )
    )

    accumulated, _ = build_accumulated_input(_run("2026-09-08"))
    assert accumulated.sleep_hours == 4.8
    assert accumulated.hrv_ms == 63
    assert len(accumulated.recovery_history) == 7

    response = create_personal_recommendation(_run("2026-09-08"))
    assert response.recommendation is not None
    assert response.accumulated_fatigue.observed_days_7 == 7


def test_apple_health_api_requires_access_key_and_returns_daily_state(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "strideai.db"))
    monkeypatch.setattr(main, "APP_KEY", "secret")
    payload = _sync(
        [
            AppleHealthDailySummary(
                date="2026-09-18",
                timezone="Asia/Ho_Chi_Minh",
                sleep_hours=7.25,
                hrv_ms=64,
                resting_hr_bpm=44,
            )
        ]
    )
    with TestClient(main.app) as client:
        assert client.post("/app/api/apple-health/sync", json=payload.model_dump(mode="json")).status_code == 401
        response = client.post(
            "/app/api/apple-health/sync",
            json=payload.model_dump(mode="json"),
            headers={"X-StrideAI-Key": "secret"},
        )
        assert response.status_code == 200
        state = client.get(
            "/app/api/apple-health/daily-state?date=2026-09-18",
            headers={"X-StrideAI-Key": "secret"},
        ).json()
    assert state["available"] is True
    assert state["state"]["sleep_hours"] == 7.25


def test_app_shell_exposes_apple_health_status(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "strideai.db"))
    monkeypatch.setattr(main, "APP_KEY", "")
    with TestClient(main.app) as client:
        html = client.get("/app").text
    assert "Apple Health recovery sync" in html
    assert "/app/api/apple-health/daily-state" in html
