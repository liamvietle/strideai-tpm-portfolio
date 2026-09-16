from app.engine import evaluate_workout
from app.models import AutonomyMode, RecommendationAction, RiskLevel, WorkoutInput


def test_normal_recovery_maintains_plan():
    result = evaluate_workout(
        WorkoutInput(
            athlete_id="test",
            planned_distance_km=10,
            planned_intensity="easy",
            recent_load_ratio=1.05,
            hrv_vs_baseline_pct=-2,
            resting_hr_delta_bpm=1,
            sleep_hours=7.5,
            soreness_0_10=2,
        )
    )
    assert result.action == RecommendationAction.maintain
    assert result.risk_level == RiskLevel.low
    assert result.autonomy_mode == AutonomyMode.automatic


def test_multi_signal_fatigue_reduces_training():
    result = evaluate_workout(
        WorkoutInput(
            athlete_id="test",
            planned_distance_km=16,
            planned_intensity="threshold",
            recent_load_ratio=1.4,
            hrv_vs_baseline_pct=-15,
            resting_hr_delta_bpm=7,
            sleep_hours=5.5,
            soreness_0_10=6,
        )
    )
    assert result.action in {RecommendationAction.reduce_volume, RecommendationAction.recovery_only}
    assert result.risk_level in {RiskLevel.moderate, RiskLevel.high}
    assert len(result.decision_factors) >= 4


def test_pain_blocks_automatic_training():
    result = evaluate_workout(
        WorkoutInput(
            athlete_id="test",
            planned_distance_km=8,
            planned_intensity="interval",
            recent_load_ratio=1.0,
            hrv_vs_baseline_pct=0,
            resting_hr_delta_bpm=0,
            sleep_hours=8,
            soreness_0_10=2,
            pain_flag=True,
        )
    )
    assert result.action == RecommendationAction.recovery_only
    assert result.autonomy_mode == AutonomyMode.human_review
    assert "pain_reported" in result.safety_flags


def test_missing_data_prevents_automatic_change():
    result = evaluate_workout(
        WorkoutInput(
            athlete_id="test",
            planned_distance_km=8,
            planned_intensity="easy",
            sleep_hours=7,
        )
    )
    assert result.action == RecommendationAction.no_change_due_to_missing_data
    assert result.autonomy_mode == AutonomyMode.human_review
