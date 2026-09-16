from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Iterable

from app.models import ActivityRecord, CoachingRecommendation, ExplanationTrace, OutcomeInput, WorkoutInput

SCHEMA_VERSION = 1


def db_path() -> Path:
    return Path(os.getenv("STRIDEAI_DB_PATH", "data/strideai.db"))


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str | Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER NOT NULL
        );
        INSERT INTO schema_meta(version)
        SELECT 1 WHERE NOT EXISTS (SELECT 1 FROM schema_meta);

        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_activity_id TEXT NOT NULL,
            athlete_id TEXT NOT NULL,
            start_time TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            name TEXT,
            distance_km REAL,
            duration_seconds INTEGER,
            average_hr REAL,
            max_hr REAL,
            calories REAL,
            raw_format TEXT NOT NULL,
            raw_payload TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, source_activity_id, athlete_id)
        );

        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id TEXT NOT NULL,
            request_json TEXT NOT NULL,
            recommendation_json TEXT NOT NULL,
            trace_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS outcomes (
            recommendation_id INTEGER PRIMARY KEY,
            completed INTEGER NOT NULL,
            perceived_effort_0_10 INTEGER,
            pain_after INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(recommendation_id) REFERENCES recommendations(id)
        );
        """)


def upsert_activities(records: Iterable[ActivityRecord], path: str | Path | None = None) -> tuple[int, int]:
    inserted = updated = 0
    with connect(path) as conn:
        for record in records:
            exists = conn.execute(
                "SELECT id FROM activities WHERE source=? AND source_activity_id=? AND athlete_id=?",
                (record.source, record.source_activity_id, record.athlete_id),
            ).fetchone()
            if exists:
                conn.execute("""
                    UPDATE activities SET start_time=?, activity_type=?, name=?, distance_km=?,
                    duration_seconds=?, average_hr=?, max_hr=?, calories=?, raw_format=?, raw_payload=?,
                    updated_at=CURRENT_TIMESTAMP WHERE id=?
                """, (
                    record.start_time, record.activity_type, record.name, record.distance_km,
                    record.duration_seconds, record.average_hr, record.max_hr, record.calories,
                    record.raw_format, record.raw_payload, exists["id"],
                ))
                updated += 1
            else:
                conn.execute("""
                    INSERT INTO activities (
                        source, source_activity_id, athlete_id, start_time, activity_type, name,
                        distance_km, duration_seconds, average_hr, max_hr, calories, raw_format, raw_payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.source, record.source_activity_id, record.athlete_id, record.start_time,
                    record.activity_type, record.name, record.distance_km, record.duration_seconds,
                    record.average_hr, record.max_hr, record.calories, record.raw_format, record.raw_payload,
                ))
                inserted += 1
    return inserted, updated


def list_activities(athlete_id: str, limit: int = 100, path: str | Path | None = None) -> list[dict]:
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT * FROM activities WHERE athlete_id=? ORDER BY start_time DESC LIMIT ?",
            (athlete_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def save_recommendation(
    request: WorkoutInput,
    recommendation: CoachingRecommendation,
    trace: ExplanationTrace | None = None,
    path: str | Path | None = None,
) -> int:
    with connect(path) as conn:
        cursor = conn.execute(
            "INSERT INTO recommendations (athlete_id, request_json, recommendation_json, trace_id) VALUES (?, ?, ?, ?)",
            (
                request.athlete_id,
                json.dumps(request.model_dump(mode="json"), separators=(",", ":")),
                json.dumps(recommendation.model_dump(mode="json"), separators=(",", ":")),
                trace.request_id if trace else None,
            ),
        )
        return int(cursor.lastrowid)


def save_outcome(recommendation_id: int, outcome: OutcomeInput, path: str | Path | None = None) -> None:
    with connect(path) as conn:
        conn.execute("""
            INSERT INTO outcomes (recommendation_id, completed, perceived_effort_0_10, pain_after, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(recommendation_id) DO UPDATE SET
                completed=excluded.completed,
                perceived_effort_0_10=excluded.perceived_effort_0_10,
                pain_after=excluded.pain_after,
                notes=excluded.notes
        """, (
            recommendation_id,
            int(outcome.completed),
            outcome.perceived_effort_0_10,
            int(outcome.pain_after),
            outcome.notes,
        ))


def get_outcome(recommendation_id: int, path: str | Path | None = None) -> dict | None:
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM outcomes WHERE recommendation_id=?",
            (recommendation_id,),
        ).fetchone()
    return dict(row) if row else None
