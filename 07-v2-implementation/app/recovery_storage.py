from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.personal_models import DailyCheckInInput
from app.personal_storage import init_personal_app_db
from app.storage import connect


def upsert_recovery_day(
    payload: DailyCheckInInput,
    *,
    calculated_load_ratio: Optional[float],
    path: str | Path | None = None,
) -> int:
    """Persist a non-running check-in against both old and new SQLite schemas.

    Older production databases created planned_intensity and human_decision as
    NOT NULL. Internal sentinel values keep those legacy constraints satisfied;
    the application treats these rows as recovery-only because they have no
    recommendation_id and carry planned_activity_type != 'run'.
    """
    init_personal_app_db(path)
    stored_intensity = payload.planned_intensity or "recovery"
    stored_decision = "n/a"
    with connect(path) as conn:
        existing = conn.execute(
            "SELECT id, recommendation_id FROM daily_checkins WHERE athlete_id=? AND checkin_date=?",
            (payload.athlete_id, payload.checkin_date),
        ).fetchone()
        if existing and existing["recommendation_id"] is not None:
            raise ValueError("A running recommendation is already locked for this date.")

        values = (
            payload.planned_activity_type.value,
            payload.planned_activity_note,
            payload.planned_distance_km,
            stored_intensity,
            payload.sleep_hours,
            payload.hrv_ms,
            payload.hrv_baseline_low,
            payload.hrv_baseline_high,
            payload.resting_hr_bpm,
            payload.soreness_0_10,
            int(payload.pain_flag),
            payload.subjective_fatigue.value,
            payload.recent_load_ratio,
            payload.days_until_event,
            calculated_load_ratio,
            stored_decision,
        )
        if existing:
            conn.execute("""
                UPDATE daily_checkins SET
                    planned_activity_type=?, planned_activity_note=?, planned_distance_km=?,
                    planned_intensity=?, sleep_hours=?, hrv_ms=?, hrv_baseline_low=?,
                    hrv_baseline_high=?, resting_hr_bpm=?, soreness_0_10=?, pain_flag=?,
                    subjective_fatigue=?, recent_load_ratio=?, days_until_event=?,
                    calculated_load_ratio=?, human_decision=?, recommendation_id=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (*values, existing["id"]))
            return int(existing["id"])

        cursor = conn.execute("""
            INSERT INTO daily_checkins (
                athlete_id, checkin_date, planned_activity_type, planned_activity_note,
                planned_distance_km, planned_intensity, sleep_hours, hrv_ms,
                hrv_baseline_low, hrv_baseline_high, resting_hr_bpm, soreness_0_10,
                pain_flag, subjective_fatigue, recent_load_ratio, days_until_event,
                calculated_load_ratio, human_decision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (payload.athlete_id, payload.checkin_date, *values))
        return int(cursor.lastrowid)
