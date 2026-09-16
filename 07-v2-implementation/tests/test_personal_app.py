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
        planned_activity_type="run",
        planned_distance_km=8.0,
        planned_intensity="easy",
        planned_activity_note=None,
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
    assert response.accumulated_fatigue is not None
    assert response.accumulated_fatigue.observed_days_7 == 3
    assert response.recommendation is not None
    assert response.recommendation.action != RecommendationAction.maintain


def test_rest_day_is_saved_and_feeds_next_run(monkeypatch, tmp_path: Path):
    db = tmp_path / "strideai.db"
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(db))
    init_personal_app_db()

    rest = _payload(
        "2026-09-01",
        planned_activity_type="rest",
        planned_distance_km=0,
        planned_intensity=None,
        human_decision=None,
        sleep_hours=5.25,
        subjective_fatigue="slightly_tired",
    )
    response = create_personal_recommendation(rest)
    assert response.mode == "recovery_only_checkin"
    assert response.recommendation is None

    accumulated, _ = build_accumulated_input(_payload("2026-09-02", sleep_hours=6.0))
    assert len(accumulated.recovery_history) == 1
    assert accumulated.recovery_history[0].sleep_hours == 5.25

    rows = list_personal_history("viet")
    assert rows[0]["planned_activity_type"] == "rest"
    assert rows[0]["recommendation"] is None


def test_non_running_activity_is_stored_without_run_recommendation(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "strideai.db"))
    response = create_personal_recommendation(
        _payload(
            "2026-09-04",
            planned_activity_type="tennis",
            planned_distance_km=0,
            planned_intensity="moderate",
            planned_activity_note="90 min tennis",
            human_decision=None,
        )
    )
    assert response.mode == "recovery_only_checkin"
    rows = list_personal_history("viet")
    assert rows[0]["planned_activity_type"] == "tennis"
    assert rows[0]["planned_activity_note"] == "90 min tennis"


def test_recent_load_is_derived_from_imported_runs_only(monkeypatch, tmp_path: Path):
    db = tmp_path / "strideai.db"
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(db))
    init_personal_app_db()
    activities = [
        ActivityRecord(
            source="strava",
            source_activity_id=f"r{i}",
            athlete_id="viet",
            start_time=f"2026-09-{i:02d}T06:00:00",
            activity_type="Run",
            distance_km=10.0,
            duration_seconds=3600,
            average_hr=140,
            max_hr=160,
            raw_format="test",
        )
        for i in range(1, 9)
    ]
    activities.append(
        ActivityRecord(
            source="strava",
            source_activity_id="ride",
            athlete_id="viet",
            start_time="2026-09-08T12:00:00",
            activity_type="Ride",
            distance_km=100.0,
            duration_seconds=7200,
            raw_format="test",
        )
    )
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


def test_personal_app_shell_has_daily_recovery_controls(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "strideai.db"))
    with TestClient(app) as client:
        response = client.get("/app")
    assert response.status_code == 200
    assert "Personal training decision assistant" in response.text
    assert "Planned activity" in response.text
    assert "Rest / recovery day" in response.text
    assert "Sleep (HH:MM)" in response.text
    assert "Auto from Strava running history" in response.text
