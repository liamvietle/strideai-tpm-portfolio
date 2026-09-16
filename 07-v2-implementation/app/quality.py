from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from app.engine import evaluate_workout
from app.explanation import build_evidence_package, fallback_explanation, validate_explanation
from app.models import (
    AutonomyMode,
    EvidencePackage,
    ExplanationQuality,
    ExplanationQualitySummary,
    QualityEvaluationSummary,
    RecommendationAction,
    RegressionComparison,
    WorkoutInput,
)

NUMBER_RE = re.compile(r"[+-]?\d+(?:\.\d+)?%?")
TOKEN_RE = re.compile(r"[a-zA-Z]{4,}")
STOPWORDS = {
    "above", "after", "approved", "baseline", "because", "below", "current",
    "evidence", "from", "into", "only", "planned", "recommendation", "reported",
    "should", "similar", "that", "the", "this", "training", "was", "with", "workout",
}


def _numbers(text: str) -> set[str]:
    return {match.group(0).lstrip("+") for match in NUMBER_RE.finditer(text)}


def _tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(text)
        if token.lower() not in STOPWORDS
    }


def evaluate_explanation_quality(text: str, evidence: EvidencePackage) -> ExplanationQuality:
    action_consistent = validate_explanation(text, evidence.approved_action)

    allowed_numbers = _numbers(evidence.model_dump_json())
    claimed_numbers = _numbers(text)
    unsupported = sorted(claimed_numbers - allowed_numbers)

    explanation_tokens = _tokens(text)
    if evidence.factor_details:
        supported = 0
        for factor in evidence.factor_details:
            factor_tokens = _tokens(factor)
            if not factor_tokens or factor_tokens & explanation_tokens:
                supported += 1
        evidence_support_rate = round(supported / len(evidence.factor_details), 4)
    else:
        evidence_support_rate = 1.0

    numeric_score = 1.0 if not unsupported else 0.0
    score = round(
        0.45 * float(action_consistent)
        + 0.30 * numeric_score
        + 0.25 * evidence_support_rate,
        4,
    )
    grounded = action_consistent and not unsupported and evidence_support_rate >= 0.5

    return ExplanationQuality(
        action_consistent=action_consistent,
        evidence_support_rate=evidence_support_rate,
        unsupported_numeric_claims=unsupported,
        groundedness_score=score,
        grounded=grounded,
    )


def summarize_explanation_records(records: list[dict]) -> ExplanationQualitySummary:
    results: list[ExplanationQuality] = []
    for record in records:
        try:
            evidence = EvidencePackage(**json.loads(record["evidence_json"]))
            results.append(evaluate_explanation_quality(record["explanation"], evidence))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

    count = len(results)
    grounded = sum(result.grounded for result in results)
    action_consistent = sum(result.action_consistent for result in results)
    unsupported = sum(len(result.unsupported_numeric_claims) for result in results)
    average_score = round(sum(result.groundedness_score for result in results) / count, 4) if count else 0.0

    return ExplanationQualitySummary(
        evaluated=count,
        grounded=grounded,
        groundedness_rate=round(grounded / count, 4) if count else 0.0,
        action_consistent=action_consistent,
        action_consistency_rate=round(action_consistent / count, 4) if count else 0.0,
        unsupported_numeric_claims=unsupported,
        average_groundedness_score=average_score,
    )


def run_quality_evaluation(cases: list[dict]) -> QualityEvaluationSummary:
    correct = 0
    safety_violations = 0
    human_review_cases = 0
    grounded = 0
    action_consistent = 0
    unsupported_numbers = 0

    for case in cases:
        workout = WorkoutInput(**case["input"])
        recommendation = evaluate_workout(workout)
        expected = RecommendationAction(case["expected_action"])
        if recommendation.action == expected:
            correct += 1
        if case.get("safety_case") and recommendation.action != RecommendationAction.recovery_only:
            safety_violations += 1
        if recommendation.autonomy_mode == AutonomyMode.human_review:
            human_review_cases += 1

        evidence = build_evidence_package(workout, recommendation, [])
        explanation = fallback_explanation(evidence)
        result = evaluate_explanation_quality(explanation, evidence)
        grounded += int(result.grounded)
        action_consistent += int(result.action_consistent)
        unsupported_numbers += len(result.unsupported_numeric_claims)

    count = len(cases)
    return QualityEvaluationSummary(
        cases=count,
        correct_actions=correct,
        action_accuracy=round(correct / count, 4) if count else 0.0,
        safety_violations=safety_violations,
        human_review_cases=human_review_cases,
        explanations_grounded=grounded,
        explanation_groundedness_rate=round(grounded / count, 4) if count else 0.0,
        action_consistency_rate=round(action_consistent / count, 4) if count else 0.0,
        unsupported_numeric_claims=unsupported_numbers,
    )


def compare_with_baseline(
    candidate: QualityEvaluationSummary,
    baseline: dict,
    *,
    candidate_label: str = "milestone-4",
) -> RegressionComparison:
    baseline_accuracy = float(baseline["action_accuracy"])
    baseline_safety = int(baseline["safety_violations"])
    reasons: list[str] = []

    if candidate.action_accuracy < baseline_accuracy - 0.02:
        reasons.append("action accuracy regressed by more than 2 percentage points")
    if candidate.safety_violations > baseline_safety:
        reasons.append("safety violations increased")
    if candidate.explanation_groundedness_rate < 0.90:
        reasons.append("explanation groundedness is below 90%")
    if candidate.action_consistency_rate < 0.99:
        reasons.append("explanation action consistency is below 99%")

    return RegressionComparison(
        baseline_label=str(baseline.get("label", "baseline")),
        candidate_label=candidate_label,
        baseline_action_accuracy=baseline_accuracy,
        candidate_action_accuracy=candidate.action_accuracy,
        action_accuracy_delta=round(candidate.action_accuracy - baseline_accuracy, 4),
        baseline_safety_violations=baseline_safety,
        candidate_safety_violations=candidate.safety_violations,
        safety_violation_delta=candidate.safety_violations - baseline_safety,
        explanation_groundedness_rate=candidate.explanation_groundedness_rate,
        gate_passed=not reasons,
        reasons=reasons,
    )


def load_json(path: str | Path):
    return json.loads(Path(path).read_text())


if __name__ == "__main__":
    cases_path = sys.argv[1] if len(sys.argv) > 1 else "evaluation/cases.json"
    baseline_path = sys.argv[2] if len(sys.argv) > 2 else "evaluation/baseline-m3.json"
    summary = run_quality_evaluation(load_json(cases_path))
    comparison = compare_with_baseline(summary, load_json(baseline_path))
    print(json.dumps({
        "summary": summary.model_dump(mode="json"),
        "comparison": comparison.model_dump(mode="json"),
    }, indent=2))
    if not comparison.gate_passed:
        raise SystemExit(1)
