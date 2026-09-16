from app.engine import evaluate_workout
from app.explanation import build_evidence_package, fallback_explanation
from app.models import ExplanationTrace, OutcomeInput, RecommendationAction, WorkoutInput
from app.persisted_history import load_persisted_history
from app.storage import init_db, save_outcome, save_recommendation


def test_persisted_outcome_becomes_retrievable_historical_case(tmp_path):
    db = tmp_path / "history.db"
    init_db(db)
    workout = WorkoutInput(
        athlete_id="viet",
        planned_distance_km=16,
        planned_intensity="threshold",
        recent_load_ratio=1.4,
        hrv_vs_baseline_pct=-15,
        resting_hr_delta_bpm=7,
        sleep_hours=5.5,
        soreness_0_10=6,
    )
    recommendation = evaluate_workout(workout)
    evidence = build_evidence_package(workout, recommendation, [])
    trace = ExplanationTrace(
        request_id="history-test",
        provider="deterministic_fallback",
        model="none",
        prompt_version="test",
        latency_ms=0,
        retrieval_count=0,
        guardrail_passed=True,
        used_fallback=True,
    )
    recommendation_id = save_recommendation(
        workout,
        recommendation,
        trace,
        path=db,
        explanation=fallback_explanation(evidence),
        evidence=evidence,
    )
    save_outcome(
        recommendation_id,
        OutcomeInput(
            completed=True,
            perceived_effort_0_10=6,
            pain_after=False,
            followed_recommendation=False,
            override_action=RecommendationAction.reduce_volume,
        ),
        path=db,
    )

    history = load_persisted_history("viet", path=db)
    assert len(history) == 1
    case = history[0]
    assert case.planned_intensity == "threshold"
    assert case.action == recommendation.action
    assert len(case.factor_codes) >= 4
    assert "followed=False" in case.outcome
    assert "override_action=reduce_volume" in case.outcome
