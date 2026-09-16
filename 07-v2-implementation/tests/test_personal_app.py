from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.personal_history import list_personal_history
from app.personal_models import DailyCheckInInput
from app.personal_service import build_accumulated_input, create_personal_recommendation
from app.personal_storage import calculate_recent_load_ratio, init_personal_app_db
from app.storage import upsert_activities
from app.models import ActivityRecord, RecommendationAction


def _payload(day: str, **overrides) -> DailyCheckInInput:
    values = dict(
        athlete_id="viet",
        checkin_date=day,
        planned_distance_km=8.0,
        planned_intensity="easy",
        sleep_hours=4.5,
        hrv_ms=60,
        hrv_baseline_low=46,
        hrv_baseline_high=78,
        resting_hr_bpm=47,
        soreness_0_10=0,
        pain_flag=False,
        subjective_fatigue="normal",
        recent_load_ratio=None,
        days_until_event=10,
        human_decision="maintain",
    )
    values.update(overrides)
    return DailyCheckInInput(**values)


def test_personal_workflow_builds_recovery_history(monkeypatch, tmp_path: Path):
    db = tmp_path / "strideai.db"
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(db))
    init_personal_app_db()

    create_personal_recommendation(_payload("2026-09-01", sleep_hours=4.0))
    create_personal_recommendation(_payload("2026-09-02", sleep_hours=4.2))
    accumulated, _ = build_accumulated_input(_payload("2026-09-03", sleep_hours=4.4))

    assert len(accumulated.recovery_history) == 2
    response = create_personal_recommendation(_payload("2026-09-03", sleep_hours=4.4))
    assert response.accumulated_fatigue.observed_days_7 == 3
    assert response.recommendation.action != RecommendationAction.maintain


def test_recent_load_is_derived_from_imported_runs(monkeypatch, tmp_path: Path):
    db = tmp_path / "strideai.db"
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(db))
    init_personal_app_db()
    activities = [
        ActivityRecord(
            source="garmin",
            source_activity_id=f"a{i}",
            athlete_id="viet",
            start_time=f"2026-09-{i:02d}T06:00:00",
            activity_type="Running",
            distance_km=10.0,
            duration_seconds=3600,
            average_hr=140,
            max_hr=160,
            raw_format="test",
        )
        for i in range(1, 9)
    ]
    upsert_activities(activities)

    ratio = calculate_recent_load_ratio("viet", "2026-09-09")
    assert ratio is not None
    assert ratio > 1.0


def test_history_keeps_human_decision_separate(monkeypatch, tmp_path: Path):
    db = tmp_path / "strideai.db"
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(db))
    create_personal_recommendation(
        _payload("2026-09-10", sleep_hours=3.0, human_decision="maintain")
    )
    rows = list_personal_history("viet")

    assert len(rows) == 1
    assert rows[0]["human_decision"] == "maintain"
    assert rows[0]["recommendation"] is not None


def test_personal_app_shell_is_served(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "strideai.db"))
    with TestClient(app) as client:
        response = client.get("/app")
    assert response.status_code == 200
    assert "Personal training decision assistant" in response.text
    assert "Lock my decision &amp; get StrideAI" in response.text or "Lock my decision & get StrideAI" in response.text
