import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.engine import evaluate_workout
from app.explanation import build_evidence_package, fallback_explanation
from app.main import app
from app.models import ExplanationTrace, OutcomeInput, RecommendationAction, WorkoutInput
from app.quality import compare_with_baseline, evaluate_explanation_quality, run_quality_evaluation
from app.storage import get_deployment_metrics, init_db, save_outcome, save_recommendation


def _workout(athlete_id="viet", fatigued=False):
    if fatigued:
        return WorkoutInput(
            athlete_id=athlete_id,
            planned_distance_km=16,
            planned_intensity="threshold",
            recent_load_ratio=1.4,
            hrv_vs_baseline_pct=-15,
            resting_hr_delta_bpm=7,
            sleep_hours=5.5,
            soreness_0_10=6,
        )
    return WorkoutInput(
        athlete_id=athlete_id,
        planned_distance_km=10,
        planned_intensity="easy",
        recent_load_ratio=1.0,
        hrv_vs_baseline_pct=0,
        resting_hr_delta_bpm=0,
        sleep_hours=8,
        soreness_0_10=1,
    )


def _trace(request_id):
    return ExplanationTrace(
        request_id=request_id,
        provider="deterministic_fallback",
        model="none",
        prompt_version="test",
        latency_ms=0,
        retrieval_count=0,
        guardrail_passed=True,
        used_fallback=True,
    )


def test_groundedness_accepts_evidence_bound_fallback():
    workout = _workout(fatigued=True)
    recommendation = evaluate_workout(workout)
    evidence = build_evidence_package(workout, recommendation, [])
    result = evaluate_explanation_quality(fallback_explanation(evidence), evidence)
    assert result.action_consistent is True
    assert result.unsupported_numeric_claims == []
    assert result.grounded is True
    assert result.groundedness_score == 1.0


def test_groundedness_rejects_wrong_action_and_unsupported_number():
    workout = _workout(fatigued=True)
    recommendation = evaluate_workout(workout)
    evidence = build_evidence_package(workout, recommendation, [])

    wrong_action = evaluate_explanation_quality(
        "Approved action: maintain. Continue as planned.", evidence
    )
    assert wrong_action.action_consistent is False
    assert wrong_action.grounded is False

    invented_number = evaluate_explanation_quality(
        f"Approved action: {recommendation.action.value}. Lactate increased by 37%, so follow the approved change.",
        evidence,
    )
    assert "37%" in invented_number.unsupported_numeric_claims
    assert invented_number.grounded is False


def test_deployment_metrics_separate_acceptance_from_outcome_coverage(tmp_path):
    db = tmp_path / "m4.db"
    init_db(db)

    normal = _workout()
    normal_rec = evaluate_workout(normal)
    normal_evidence = build_evidence_package(normal, normal_rec, [])
    normal_id = save_recommendation(
        normal,
        normal_rec,
        _trace("normal"),
        path=db,
        explanation=fallback_explanation(normal_evidence),
        evidence=normal_evidence,
    )

    fatigued = _workout(fatigued=True)
    fatigued_rec = evaluate_workout(fatigued)
    fatigued_evidence = build_evidence_package(fatigued, fatigued_rec, [])
    fatigued_id = save_recommendation(
        fatigued,
        fatigued_rec,
        _trace("fatigued"),
        path=db,
        explanation=fallback_explanation(fatigued_evidence),
        evidence=fatigued_evidence,
    )

    save_outcome(
        normal_id,
        OutcomeInput(
            completed=True,
            perceived_effort_0_10=4,
            pain_after=False,
            followed_recommendation=True,
        ),
        path=db,
    )
    save_outcome(
        fatigued_id,
        OutcomeInput(
            completed=True,
            perceived_effort_0_10=6,
            pain_after=True,
            followed_recommendation=False,
            override_action=RecommendationAction.reduce_volume,
        ),
        path=db,
    )

    metrics = get_deployment_metrics("viet", path=db)
    assert metrics.total_recommendations == 2
    assert metrics.outcome_coverage_rate == 1.0
    assert metrics.follow_status_recorded == 2
    assert metrics.acceptance_rate == 0.5
    assert metrics.override_rate == 0.5
    assert metrics.completion_rate == 1.0
    assert metrics.pain_after_rate == 0.5
    assert metrics.trace_coverage_rate == 1.0
    assert metrics.guardrail_pass_rate == 1.0
    assert metrics.fallback_rate == 1.0


def test_regression_gate_compares_against_m3_baseline():
    root = Path(__file__).parents[1]
    cases = json.loads((root / "evaluation" / "cases.json").read_text())
    baseline = json.loads((root / "evaluation" / "baseline-m3.json").read_text())
    summary = run_quality_evaluation(cases)
    comparison = compare_with_baseline(summary, baseline)

    assert summary.action_accuracy == 1.0
    assert summary.safety_violations == 0
    assert summary.explanation_groundedness_rate == 1.0
    assert comparison.gate_passed is True


def test_dashboard_and_empty_metrics_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "api.db"))
    client = TestClient(app)
    assert client.get("/dashboard").status_code == 200

    response = client.get("/v4/metrics")
    assert response.status_code == 200
    assert response.json()["total_recommendations"] == 0

    quality = client.get("/v4/quality/explanations")
    assert quality.status_code == 200
    assert quality.json()["evaluated"] == 0
