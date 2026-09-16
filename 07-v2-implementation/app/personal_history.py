from __future__ import annotations

import json
from pathlib import Path

from app.personal_storage import init_personal_app_db
from app.storage import connect


def list_personal_history(
    athlete_id: str,
    *,
    limit: int = 30,
    path: str | Path | None = None,
) -> list[dict]:
    init_personal_app_db(path)
    with connect(path) as conn:
        rows = conn.execute("""
            SELECT
                c.*,
                r.recommendation_json,
                r.explanation,
                o.completed,
                o.perceived_effort_0_10,
                o.pain_after,
                o.followed_recommendation,
                o.override_action,
                o.notes AS outcome_notes
            FROM daily_checkins c
            LEFT JOIN recommendations r ON r.id=c.recommendation_id
            LEFT JOIN outcomes o ON o.recommendation_id=c.recommendation_id
            WHERE c.athlete_id=?
            ORDER BY c.checkin_date DESC
            LIMIT ?
        """, (athlete_id, limit)).fetchall()

    result: list[dict] = []
    for raw in rows:
        row = dict(raw)
        recommendation_json = row.pop("recommendation_json", None)
        recommendation = None
        if recommendation_json:
            try:
                recommendation = json.loads(recommendation_json)
            except json.JSONDecodeError:
                recommendation = None
        row["recommendation"] = recommendation
        for key in ("pain_flag", "completed", "pain_after", "followed_recommendation"):
            if row.get(key) is not None:
                row[key] = bool(row[key])
        result.append(row)
    return result
