from __future__ import annotations

import json
from pathlib import Path

from app.models import HistoricalCase, RecommendationAction
from app.storage import connect


def load_persisted_history(
    athlete_id: str,
    *,
    limit: int = 200,
    path: str | Path | None = None,
) -> list[HistoricalCase]:
    with connect(path) as conn:
        rows = conn.execute("""
            SELECT r.athlete_id, r.request_json, r.recommendation_json, r.created_at,
                   o.completed, o.perceived_effort_0_10, o.pain_after,
                   o.followed_recommendation, o.override_action
            FROM recommendations r
            JOIN outcomes o ON o.recommendation_id=r.id
            WHERE r.athlete_id=?
            ORDER BY r.id DESC
            LIMIT ?
        """, (athlete_id, limit)).fetchall()

    cases: list[HistoricalCase] = []
    for row in rows:
        try:
            request = json.loads(row["request_json"])
            recommendation = json.loads(row["recommendation_json"])
            factor_codes = [
                factor["code"]
                for factor in recommendation.get("decision_factors", [])
                if isinstance(factor, dict) and factor.get("code")
            ]
            outcome_parts = [
                f"completed={bool(row['completed'])}",
                f"pain_after={bool(row['pain_after'])}",
            ]
            if row["followed_recommendation"] is not None:
                outcome_parts.append(f"followed={bool(row['followed_recommendation'])}")
            if row["override_action"]:
                outcome_parts.append(f"override_action={row['override_action']}")
            if row["perceived_effort_0_10"] is not None:
                outcome_parts.append(f"perceived_effort={row['perceived_effort_0_10']}/10")

            cases.append(HistoricalCase(
                athlete_id=row["athlete_id"],
                session_date=str(row["created_at"]).split(" ", 1)[0],
                planned_intensity=request["planned_intensity"],
                factor_codes=factor_codes,
                action=RecommendationAction(recommendation["action"]),
                outcome="; ".join(outcome_parts),
            ))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return cases
