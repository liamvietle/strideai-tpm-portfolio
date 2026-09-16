from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from app.models import CoachingRecommendation, HistoricalCase, RetrievedCase, WorkoutInput

DEFAULT_HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "history.json"


def load_history(path: Path = DEFAULT_HISTORY_PATH) -> list[HistoricalCase]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [HistoricalCase.model_validate(item) for item in raw]


def _score_case(
    case: HistoricalCase,
    workout: WorkoutInput,
    recommendation: CoachingRecommendation,
) -> float:
    current_codes = {factor.code for factor in recommendation.decision_factors}
    historical_codes = set(case.factor_codes)
    overlap = len(current_codes & historical_codes)

    score = overlap * 2.0
    if case.planned_intensity == workout.planned_intensity:
        score += 1.5
    if case.action == recommendation.action:
        score += 1.0
    if case.athlete_id == workout.athlete_id:
        score += 0.5
    return score


def retrieve_similar_history(
    workout: WorkoutInput,
    recommendation: CoachingRecommendation,
    *,
    history: Iterable[HistoricalCase] | None = None,
    limit: int = 3,
) -> list[RetrievedCase]:
    cases = list(history) if history is not None else load_history()
    ranked: list[RetrievedCase] = []

    for case in cases:
        score = _score_case(case, workout, recommendation)
        if score <= 0:
            continue
        ranked.append(
            RetrievedCase(
                **case.model_dump(),
                similarity_score=round(score, 2),
            )
        )

    ranked.sort(key=lambda case: (case.similarity_score, case.session_date), reverse=True)
    return ranked[:limit]
