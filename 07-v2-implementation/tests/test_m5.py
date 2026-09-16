import json
from pathlib import Path

from app.accumulated_fatigue import assess_accumulated_fatigue, evaluate_workout_v21
from app.models import (
    AccumulatedFatigueState,
    AccumulatedWorkoutInput,
    RecommendationAction,
    RecoverySnapshot,
)
from app.real_validation import run_real_validation


def _input(**overrides):
    values = dict(
        athlete_id="test",
        day_index=0,
        planned_distance_km=10,
        planned_intensity="easy",
        recent_load_ratio=1.0,
        sleep_hours=8.0,
        soreness_0_10=1,
        pain_flag=False,
        hrv_ms=60,
        hrv_baseline_low=46,
        hrv_baseline_high=77,
        resting_hr_bpm=48,
        subjective_fatigue="normal",
        days_until_event=10,
        recovery_history=[],
    )
    values.update(overrides)
    return AccumulatedWorkoutInput(**values)


def test_isolated_bad_night_warns_without_automatic_cut():
    workout = _input(sleep_hours=3.0)
    recommendation, assessment = evaluate_workout_v21(workout)

    assert assessment.state == AccumulatedFatigueState.elevated
    assert assessment.has_warning is True
    assert recommendation.action == RecommendationAction.maintain
    assert "CURRENT_SLEEP_VERY_LOW" in assessment.contributors


def test_repeated_bad_sleep_escalates_to_training_change():
    history = [
        RecoverySnapshot(day_index=0, sleep_hours=3.0, hrv_ms=60, hrv_baseline_low=46, hrv_baseline_high=77),
        RecoverySnapshot(day_index=1, sleep_hours=4.0, hrv_ms=59, hrv_baseline_low=46, hrv_baseline_high=77),
    ]
    workout = _input(
        day_index=2,
        sleep_hours=4.5,
        recovery_history=history,
    )
    recommendation, assessment = evaluate_workout_v21(workout)

    assert assessment.state in {AccumulatedFatigueState.high, AccumulatedFatigueState.critical}
    assert recommendation.action != RecommendationAction.maintain
    assert "REPEATED_VERY_LOW_SLEEP" in assessment.contributors


def test_hrv_uses_baseline_range_not_midpoint():
    inside = assess_accumulated_fatigue(_input(hrv_ms=49, hrv_baseline_low=46, hrv_baseline_high=77))
    below = assess_accumulated_fatigue(_input(hrv_ms=43, hrv_baseline_low=46, hrv_baseline_high=77))

    assert inside.hrv_status == "within_baseline"
    assert "HRV_BELOW_BASELINE" not in inside.contributors
    assert below.hrv_status == "below_baseline"
    assert "HRV_BELOW_BASELINE" in below.contributors


def test_pain_remains_hard_safety_override():
    recommendation, assessment = evaluate_workout_v21(_input(pain_flag=True))

    assert assessment.has_warning is True
    assert recommendation.action == RecommendationAction.recovery_only
    assert recommendation.autonomy_mode.value == "human_review"
    assert "pain_reported" in recommendation.safety_flags


def test_sanitized_real_sequence_detects_outcome_aligned_warning():
    root = Path(__file__).parents[1]
    payload = json.loads((root / "evaluation" / "real-validation-sanitized.json").read_text())
    summary = run_real_validation(payload)

    assert summary.cases == 9
    assert summary.outcome_aligned_warning_rate >= 0.8
    assert summary.missed_deterioration <= 1
    assert summary.action_changes >= 5
    assert summary.human_agreement_rate < 1.0


def test_real_validation_file_contains_no_calendar_dates():
    root = Path(__file__).parents[1]
    text = (root / "evaluation" / "real-validation-sanitized.json").read_text()
    payload = json.loads(text)

    assert "2026-" not in text
    assert all("date" not in case for case in payload["cases"])
    assert "not a raw wearable export" in payload["metadata"]["privacy"]
