from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from app.personal_models import DailyCheckInInput
from app.storage import connect, init_db


def init_personal_app_db(path: str | Path | None = None) -> None:
    init_db(path)
    with connect(path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS daily_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id TEXT NOT NULL,
            checkin_date TEXT NOT NULL,
            planned_distance_km REAL NOT NULL,
            planned_intensity TEXT NOT NULL,
            sleep_hours REAL,
            hrv_ms REAL,
            hrv_baseline_low REAL,
            hrv_baseline_high REAL,
            resting_hr_bpm REAL,
            soreness_0_10 INTEGER,
            pain_flag INTEGER NOT NULL DEFAULT 0,
            subjective_fatigue TEXT NOT NULL,
            recent_load_ratio REAL,
            days_until_event INTEGER,
            human_decision TEXT NOT NULL,
            recommendation_id INTEGER,
            calculated_load_ratio REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(athlete_id, checkin_date)
        );
        CREATE INDEX IF NOT EXISTS idx_daily_checkins_athlete_date
            ON daily_checkins(athlete_id, checkin_date);
        """)


def upsert_checkin(
    payload: DailyCheckInInput,
    *,
    calculated_load_ratio: Optional[float],
    path: str | Path | None = None,
) -> int:
    init_personal_app_db(path)
    with connect(path) as conn:
        existing = conn.execute(
            "SELECT id FROM daily_checkins WHERE athlete_id=? AND checkin_date=?",
            (payload.athlete_id, payload.checkin_date),
        ).fetchone()
        values = (
            payload.planned_distance_km,
            payload.planned_intensity,
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
            payload.human_decision.value,
            calculated_load_ratio,
        )
        if existing:
            conn.execute("""
                UPDATE daily_checkins SET
                    planned_distance_km=?, planned_intensity=?, sleep_hours=?, hrv_ms=?,
                    hrv_baseline_low=?, hrv_baseline_high=?, resting_hr_bpm=?, soreness_0_10=?,
                    pain_flag=?, subjective_fatigue=?, recent_load_ratio=?, days_until_event=?,
                    human_decision=?, calculated_load_ratio=?, recommendation_id=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (*values, existing["id"]))
            return int(existing["id"])

        cursor = conn.execute("""
            INSERT INTO daily_checkins (
                athlete_id, checkin_date, planned_distance_km, planned_intensity,
                sleep_hours, hrv_ms, hrv_baseline_low, hrv_baseline_high,
                resting_hr_bpm, soreness_0_10, pain_flag, subjective_fatigue,
                recent_load_ratio, days_until_event, human_decision, calculated_load_ratio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.athlete_id,
            payload.checkin_date,
            payload.planned_distance_km,
            payload.planned_intensity,
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
            payload.human_decision.value,
            calculated_load_ratio,
        ))
        return int(cursor.lastrowid)


def attach_recommendation(
    checkin_id: int,
    recommendation_id: int,
    path: str | Path | None = None,
) -> None:
    with connect(path) as conn:
        conn.execute(
            "UPDATE daily_checkins SET recommendation_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (recommendation_id, checkin_id),
        )


def list_checkins(
    athlete_id: str,
    *,
    limit: int = 30,
    path: str | Path | None = None,
) -> list[dict]:
    init_personal_app_db(path)
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM daily_checkins WHERE athlete_id=? ORDER BY checkin_date DESC LIMIT ?",
            (athlete_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def prior_checkins(
    athlete_id: str,
    checkin_date: str,
    *,
    days: int = 7,
    path: str | Path | None = None,
) -> list[dict]:
    init_personal_app_db(path)
    target = date.fromisoformat(checkin_date)
    start = (target - timedelta(days=days)).isoformat()
    with connect(path) as conn:
        rows = conn.execute("""
            SELECT * FROM daily_checkins
            WHERE athlete_id=? AND checkin_date>=? AND checkin_date<?
            ORDER BY checkin_date ASC
        """, (athlete_id, start, checkin_date)).fetchall()
    return [dict(row) for row in rows]


def calculate_recent_load_ratio(
    athlete_id: str,
    checkin_date: str,
    path: str | Path | None = None,
) -> Optional[float]:
    """7-day distance divided by 28-day weekly-average distance."""
    init_personal_app_db(path)
    target = date.fromisoformat(checkin_date)
    start7 = (target - timedelta(days=7)).isoformat()
    start28 = (target - timedelta(days=28)).isoformat()

    with connect(path) as conn:
        acute = conn.execute("""
            SELECT COALESCE(SUM(distance_km), 0) AS total
            FROM activities
            WHERE athlete_id=? AND substr(start_time, 1, 10)>=? AND substr(start_time, 1, 10)<?
              AND lower(activity_type) LIKE '%run%'
        """, (athlete_id, start7, checkin_date)).fetchone()["total"]
        chronic_total = conn.execute("""
            SELECT COALESCE(SUM(distance_km), 0) AS total
            FROM activities
            WHERE athlete_id=? AND substr(start_time, 1, 10)>=? AND substr(start_time, 1, 10)<?
              AND lower(activity_type) LIKE '%run%'
        """, (athlete_id, start28, checkin_date)).fetchone()["total"]

    if not chronic_total or chronic_total <= 0:
        return None
    weekly_average = chronic_total / 4.0
    if weekly_average <= 0:
        return None
    return round(float(acute) / float(weekly_average), 2)
