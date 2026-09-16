from app.engine import evaluate_workout
from app.models import HistoricalCase, RecommendationAction, WorkoutInput
from app.retrieval import retrieve_similar_history


def test_retrieval_prioritizes_matching_factors_and_intensity():
    workout = WorkoutInput(
        athlete_id="viet-demo",
        planned_distance_km=16,
        planned_intensity="threshold",
        recent_load_ratio=1.4,
        hrv_vs_baseline_pct=-15,
        resting_hr_delta_bpm=7,
        sleep_hours=5.5,
        soreness_0_10=6,
    )
    recommendation = evaluate_workout(workout)
    history = [
        HistoricalCase(
            athlete_id="viet-demo",
            session_date="2026-08-18",
            planned_intensity="threshold",
            factor_codes=["HRV_BELOW_BASELINE", "SLEEP_LOW", "LOAD_ELEVATED"],
            action=RecommendationAction.recovery_only,
            outcome="Relevant case.",
        ),
        HistoricalCase(
            athlete_id="viet-demo",
            session_date="2026-08-20",
            planned_intensity="easy",
            factor_codes=["SORENESS_ELEVATED"],
            action=RecommendationAction.maintain,
            outcome="Less relevant case.",
        ),
    ]

    results = retrieve_similar_history(workout, recommendation, history=history)

    assert results[0].session_date == "2026-08-18"
    assert results[0].similarity_score > results[1].similarity_score
