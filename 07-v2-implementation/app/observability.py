from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.models import ExplanationTrace, RecommendationAction

DEFAULT_TRACE_PATH = Path(__file__).resolve().parent.parent / "logs" / "requests.jsonl"


def write_trace(
    trace: ExplanationTrace,
    *,
    athlete_id: str,
    approved_action: RecommendationAction,
    path: Path = DEFAULT_TRACE_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "athlete_id": athlete_id,
        "approved_action": approved_action.value,
        **trace.model_dump(),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
