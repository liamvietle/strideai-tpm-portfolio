from __future__ import annotations

import json
import sys
from pathlib import Path

from app.engine import evaluate_workout
from app.models import AutonomyMode, EvaluationSummary, RecommendationAction, WorkoutInput


def run_evaluation(cases: list[dict]) -> EvaluationSummary:
    correct = 0
    safety_violations = 0
    human_review_cases = 0

    for case in cases:
        workout = WorkoutInput(**case["input"])
        result = evaluate_workout(workout)
        expected = RecommendationAction(case["expected_action"])
        if result.action == expected:
            correct += 1
        if case.get("safety_case") and result.action != RecommendationAction.recovery_only:
            safety_violations += 1
        if result.autonomy_mode == AutonomyMode.human_review:
            human_review_cases += 1

    count = len(cases)
    return EvaluationSummary(
        cases=count,
        correct_actions=correct,
        action_accuracy=round(correct / count, 4) if count else 0,
        safety_violations=safety_violations,
        human_review_cases=human_review_cases,
    )


def load_cases(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text())


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "evaluation/cases.json"
    print(run_evaluation(load_cases(path)).model_dump_json(indent=2))
