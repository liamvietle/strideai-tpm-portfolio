from __future__ import annotations

import json
import sys
from pathlib import Path

from app.accumulated_fatigue import evaluate_workout_v21
from app.models import (
    AccumulatedWorkoutInput,
    OutcomeAssessment,
    RealValidationSummary,
    RecommendationAction,
    RecoverySnapshot,
)


def _snapshot(case: dict) -> RecoverySnapshot:
    return RecoverySnapshot(
        day_index=case["day_index"],
        sleep_hours=case.get("sleep_hours"),
        hrv_ms=case.get("hrv_ms"),
        hrv_baseline_low=case.get("hrv_baseline_low"),
        hrv_baseline_high=case.get("hrv_baseline_high"),
        resting_hr_bpm=case.get("resting_hr_bpm"),
        soreness_0_10=case.get("soreness_0_10"),
        pain_flag=case.get("pain_flag", False),
        subjective_fatigue=case.get("subjective_fatigue", "normal"),
        recent_load_ratio=case.get("recent_load_ratio"),
    )


def _input(case: dict, history: list[RecoverySnapshot]) -> AccumulatedWorkoutInput:
    return AccumulatedWorkoutInput(
        athlete_id="sanitized-validation-athlete",
        day_index=case["day_index"],
        planned_distance_km=case["planned_distance_km"],
        planned_intensity=case["planned_intensity"],
        recent_load_ratio=case.get("recent_load_ratio"),
        sleep_hours=case.get("sleep_hours"),
        soreness_0_10=case.get("soreness_0_10"),
        pain_flag=case.get("pain_flag", False),
        hrv_ms=case.get("hrv_ms"),
        hrv_baseline_low=case.get("hrv_baseline_low"),
        hrv_baseline_high=case.get("hrv_baseline_high"),
        resting_hr_bpm=case.get("resting_hr_bpm"),
        subjective_fatigue=case.get("subjective_fatigue", "normal"),
        days_until_event=case.get("days_until_event"),
        recovery_history=list(history),
    )


def run_real_validation(payload: dict) -> RealValidationSummary:
    cases = payload.get("cases", [])
    history: list[RecoverySnapshot] = []
    exact = 0
    warnings = 0
    action_changes = 0
    useful_cases = 0
    useful_detected = 0
    missed = 0
    false_alarms = 0

    for case in cases:
        workout = _input(case, history)
        recommendation, assessment = evaluate_workout_v21(workout)
        human_action = RecommendationAction(case["human_action_at_time"])
        outcome = OutcomeAssessment(case["outcome_assessment"])

        exact += int(recommendation.action == human_action)
        warnings += int(assessment.has_warning)
        action_changes += int(recommendation.action != RecommendationAction.maintain)

        if outcome == OutcomeAssessment.warning_useful_directionally:
            useful_cases += 1
            useful_detected += int(assessment.has_warning)
            missed += int(not assessment.has_warning)
        elif outcome == OutcomeAssessment.false_alarm:
            false_alarms += int(assessment.has_warning)

        history.append(_snapshot(case))

    count = len(cases)
    return RealValidationSummary(
        cases=count,
        human_exact_agreement=exact,
        human_agreement_rate=round(exact / count, 4) if count else 0.0,
        warnings_issued=warnings,
        action_changes=action_changes,
        useful_warning_cases=useful_cases,
        useful_warnings_detected=useful_detected,
        outcome_aligned_warning_rate=round(useful_detected / useful_cases, 4) if useful_cases else 0.0,
        missed_deterioration=missed,
        false_alarms=false_alarms,
    )


def load_validation(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "evaluation/real-validation-sanitized.json"
    summary = run_real_validation(load_validation(path))
    print(summary.model_dump_json(indent=2))
    if summary.useful_warning_cases and summary.outcome_aligned_warning_rate < 0.8:
        raise SystemExit("Outcome-aligned warning rate fell below 80%")
