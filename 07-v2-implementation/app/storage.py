from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Iterable

from app.models import (
    ActivityRecord,
    CoachingRecommendation,
    DeploymentMetrics,
    EvidencePackage,
    ExplanationTrace,
    OutcomeInput,
    WorkoutInput,
)

SCHEMA_VERSION = 3


def db_path() -> Path:
    return Path(os.getenv("STRIDEAI_DB_PATH", "data/strideai.db"))


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = Path(path) if path else db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


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

        CREATE TABLE IF NOT EXISTS activity_weather (
            activity_id INTEGER PRIMARY KEY,
            fingerprint TEXT NOT NULL,
            status TEXT NOT NULL,
            weather_json TEXT,
            attempted_at REAL NOT NULL,
            FOREIGN KEY(activity_id) REFERENCES activities(id)
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

        for column, declaration in (
            ("explanation", "TEXT"),
            ("evidence_json", "TEXT"),
            ("provider", "TEXT"),
            ("model", "TEXT"),
            ("prompt_version", "TEXT"),
            ("latency_ms", "INTEGER"),
            ("guardrail_passed", "INTEGER"),
            ("used_fallback", "INTEGER"),
        ):
            _ensure_column(conn, "recommendations", column, declaration)

        _ensure_column(conn, "outcomes", "followed_recommendation", "INTEGER")
        _ensure_column(conn, "outcomes", "override_action", "TEXT")
        conn.execute("UPDATE schema_meta SET version=?", (SCHEMA_VERSION,))
        conn.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_athlete ON recommendations(athlete_id)")


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
    *,
    explanation: str | None = None,
    evidence: EvidencePackage | None = None,
) -> int:
    with connect(path) as conn:
        cursor = conn.execute("""
            INSERT INTO recommendations (
                athlete_id, request_json, recommendation_json, trace_id,
                explanation, evidence_json, provider, model, prompt_version,
                latency_ms, guardrail_passed, used_fallback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request.athlete_id,
            json.dumps(request.model_dump(mode="json"), separators=(",", ":")),
            json.dumps(recommendation.model_dump(mode="json"), separators=(",", ":")),
            trace.request_id if trace else None,
            explanation,
            json.dumps(evidence.model_dump(mode="json"), separators=(",", ":")) if evidence else None,
            trace.provider if trace else None,
            trace.model if trace else None,
            trace.prompt_version if trace else None,
            trace.latency_ms if trace else None,
            int(trace.guardrail_passed) if trace else None,
            int(trace.used_fallback) if trace else None,
        ))
        return int(cursor.lastrowid)


def save_outcome(recommendation_id: int, outcome: OutcomeInput, path: str | Path | None = None) -> None:
    with connect(path) as conn:
        conn.execute("""
            INSERT INTO outcomes (
                recommendation_id, completed, perceived_effort_0_10, pain_after,
                followed_recommendation, override_action, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recommendation_id) DO UPDATE SET
                completed=excluded.completed,
                perceived_effort_0_10=excluded.perceived_effort_0_10,
                pain_after=excluded.pain_after,
                followed_recommendation=excluded.followed_recommendation,
                override_action=excluded.override_action,
                notes=excluded.notes
        """, (
            recommendation_id,
            int(outcome.completed),
            outcome.perceived_effort_0_10,
            int(outcome.pain_after),
            int(outcome.followed_recommendation) if outcome.followed_recommendation is not None else None,
            outcome.override_action.value if outcome.override_action else None,
            outcome.notes,
        ))


def get_outcome(recommendation_id: int, path: str | Path | None = None) -> dict | None:
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM outcomes WHERE recommendation_id=?",
            (recommendation_id,),
        ).fetchone()
    return dict(row) if row else None


def list_explanation_records(
    athlete_id: str | None = None,
    limit: int = 100,
    path: str | Path | None = None,
) -> list[dict]:
    query = """
        SELECT id, athlete_id, recommendation_json, explanation, evidence_json, provider,
               model, prompt_version, latency_ms, guardrail_passed, used_fallback, created_at
        FROM recommendations
        WHERE explanation IS NOT NULL AND evidence_json IS NOT NULL
    """
    params: list[object] = []
    if athlete_id is not None:
        query += " AND athlete_id=?"
        params.append(athlete_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect(path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_deployment_metrics(
    athlete_id: str | None = None,
    path: str | Path | None = None,
) -> DeploymentMetrics:
    query = """
        SELECT r.recommendation_json, r.provider, r.latency_ms, r.guardrail_passed, r.used_fallback,
               o.recommendation_id AS outcome_id, o.completed, o.perceived_effort_0_10,
               o.pain_after, o.followed_recommendation, o.override_action
        FROM recommendations r
        LEFT JOIN outcomes o ON o.recommendation_id=r.id
    """
    params: list[object] = []
    if athlete_id is not None:
        query += " WHERE r.athlete_id=?"
        params.append(athlete_id)
    with connect(path) as conn:
        rows = [dict(row) for row in conn.execute(query, params).fetchall()]

    total = len(rows)
    outcome_rows = [row for row in rows if row["outcome_id"] is not None]
    follow_rows = [row for row in outcome_rows if row["followed_recommendation"] is not None]
    trace_rows = [row for row in rows if row["provider"] is not None]
    guardrail_rows = [row for row in trace_rows if row["guardrail_passed"] is not None]
    effort_values = [row["perceived_effort_0_10"] for row in outcome_rows if row["perceived_effort_0_10"] is not None]

    followed = sum(1 for row in follow_rows if row["followed_recommendation"] == 1)
    overridden = sum(1 for row in follow_rows if row["followed_recommendation"] == 0)
    completed = sum(1 for row in outcome_rows if row["completed"] == 1)
    pain_after = sum(1 for row in outcome_rows if row["pain_after"] == 1)
    human_review = 0
    for row in rows:
        try:
            recommendation = json.loads(row["recommendation_json"])
            human_review += int(recommendation.get("autonomy_mode") == "human_review")
        except (TypeError, json.JSONDecodeError):
            continue

    def rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    return DeploymentMetrics(
        athlete_id=athlete_id,
        total_recommendations=total,
        outcomes_recorded=len(outcome_rows),
        outcome_coverage_rate=round(len(outcome_rows) / total, 4) if total else 0.0,
        follow_status_recorded=len(follow_rows),
        followed_count=followed,
        overridden_count=overridden,
        acceptance_rate=rate(followed, len(follow_rows)),
        override_rate=rate(overridden, len(follow_rows)),
        completed_count=completed,
        completion_rate=rate(completed, len(outcome_rows)),
        pain_after_count=pain_after,
        pain_after_rate=rate(pain_after, len(outcome_rows)),
        average_perceived_effort=round(sum(effort_values) / len(effort_values), 2) if effort_values else None,
        human_review_recommendations=human_review,
        human_review_rate=round(human_review / total, 4) if total else 0.0,
        trace_coverage_rate=round(len(trace_rows) / total, 4) if total else 0.0,
        guardrail_pass_rate=rate(sum(1 for row in guardrail_rows if row["guardrail_passed"] == 1), len(guardrail_rows)),
        fallback_rate=rate(sum(1 for row in trace_rows if row["used_fallback"] == 1), len(trace_rows)),
        average_latency_ms=(
            round(sum(row["latency_ms"] for row in trace_rows if row["latency_ms"] is not None) /
                  len([row for row in trace_rows if row["latency_ms"] is not None]), 2)
            if any(row["latency_ms"] is not None for row in trace_rows) else None
        ),
    )
