from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from pydantic import BaseModel, Field, model_validator

from app.storage import connect, init_db


class AppleHealthDailySummary(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    timezone: str = Field(min_length=1, max_length=80)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    sleep_sample_count: int = Field(default=0, ge=0, le=10_000)
    hrv_ms: float | None = Field(default=None, ge=0, le=1_000)
    hrv_sample_count: int = Field(default=0, ge=0, le=10_000)
    resting_hr_bpm: float | None = Field(default=None, ge=20, le=220)
    resting_hr_sample_count: int = Field(default=0, ge=0, le=10_000)
    source_names: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_summary(self):
        parsed = date.fromisoformat(self.date)
        if parsed > date.today() + timedelta(days=1):
            raise ValueError("Apple Health summary date cannot be in the future.")
        if self.sleep_hours is None and self.hrv_ms is None and self.resting_hr_bpm is None:
            raise ValueError("Each Apple Health summary must contain at least one recovery metric.")
        self.source_names = sorted({name.strip() for name in self.source_names if name.strip()})[:20]
        return self


class AppleHealthSyncInput(BaseModel):
    athlete_id: str = Field(default="viet", min_length=1, max_length=100)
    device_id: str = Field(min_length=8, max_length=100)
    app_version: str | None = Field(default=None, max_length=40)
    generated_at: datetime
    summaries: list[AppleHealthDailySummary] = Field(min_length=1, max_length=90)

    @model_validator(mode="after")
    def validate_sync(self):
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must include a timezone offset.")
        dates = [item.date for item in self.summaries]
        if len(dates) != len(set(dates)):
            raise ValueError("Apple Health sync cannot contain duplicate summary dates.")
        return self


class AppleHealthSyncResult(BaseModel):
    received: int
    inserted: int
    updated: int
    latest_date: str
    synced_at: str


def init_apple_health_db(path: str | Path | None = None) -> None:
    init_db(path)
    with connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS apple_health_daily (
                athlete_id TEXT NOT NULL,
                health_date TEXT NOT NULL,
                timezone TEXT NOT NULL,
                sleep_hours REAL,
                sleep_sample_count INTEGER NOT NULL DEFAULT 0,
                hrv_ms REAL,
                hrv_sample_count INTEGER NOT NULL DEFAULT 0,
                resting_hr_bpm REAL,
                resting_hr_sample_count INTEGER NOT NULL DEFAULT 0,
                source_names_json TEXT NOT NULL DEFAULT '[]',
                device_id TEXT NOT NULL,
                app_version TEXT,
                generated_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (athlete_id, health_date)
            );
            CREATE INDEX IF NOT EXISTS idx_apple_health_athlete_date
                ON apple_health_daily(athlete_id, health_date);
            """
        )


def upsert_apple_health(
    payload: AppleHealthSyncInput,
    path: str | Path | None = None,
) -> AppleHealthSyncResult:
    init_apple_health_db(path)
    inserted = 0
    updated = 0
    generated_at = payload.generated_at.astimezone(timezone.utc).isoformat()
    with connect(path) as conn:
        for item in payload.summaries:
            existing = conn.execute(
                "SELECT 1 FROM apple_health_daily WHERE athlete_id=? AND health_date=?",
                (payload.athlete_id, item.date),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO apple_health_daily (
                    athlete_id, health_date, timezone, sleep_hours, sleep_sample_count,
                    hrv_ms, hrv_sample_count, resting_hr_bpm, resting_hr_sample_count,
                    source_names_json, device_id, app_version, generated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(athlete_id, health_date) DO UPDATE SET
                    timezone=excluded.timezone,
                    sleep_hours=excluded.sleep_hours,
                    sleep_sample_count=excluded.sleep_sample_count,
                    hrv_ms=excluded.hrv_ms,
                    hrv_sample_count=excluded.hrv_sample_count,
                    resting_hr_bpm=excluded.resting_hr_bpm,
                    resting_hr_sample_count=excluded.resting_hr_sample_count,
                    source_names_json=excluded.source_names_json,
                    device_id=excluded.device_id,
                    app_version=excluded.app_version,
                    generated_at=excluded.generated_at,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    payload.athlete_id,
                    item.date,
                    item.timezone,
                    item.sleep_hours,
                    item.sleep_sample_count,
                    item.hrv_ms,
                    item.hrv_sample_count,
                    item.resting_hr_bpm,
                    item.resting_hr_sample_count,
                    json.dumps(item.source_names, separators=(",", ":")),
                    payload.device_id,
                    payload.app_version,
                    generated_at,
                ),
            )
            if existing:
                updated += 1
            else:
                inserted += 1

    synced_at = datetime.now(timezone.utc).isoformat()
    return AppleHealthSyncResult(
        received=len(payload.summaries),
        inserted=inserted,
        updated=updated,
        latest_date=max(item.date for item in payload.summaries),
        synced_at=synced_at,
    )


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def hrv_baseline(
    athlete_id: str,
    before_date: str,
    path: str | Path | None = None,
) -> tuple[float | None, float | None, int]:
    init_apple_health_db(path)
    start = (date.fromisoformat(before_date) - timedelta(days=42)).isoformat()
    with connect(path) as conn:
        rows = conn.execute(
            """
            SELECT hrv_ms FROM apple_health_daily
            WHERE athlete_id=? AND health_date>=? AND health_date<? AND hrv_ms IS NOT NULL
            ORDER BY health_date DESC LIMIT 28
            """,
            (athlete_id, start, before_date),
        ).fetchall()
    values = [float(row["hrv_ms"]) for row in rows]
    if len(values) < 7:
        return None, None, len(values)
    return round(_percentile(values, 0.10), 1), round(_percentile(values, 0.90), 1), len(values)


def daily_state(
    athlete_id: str,
    health_date: str,
    path: str | Path | None = None,
) -> dict | None:
    date.fromisoformat(health_date)
    init_apple_health_db(path)
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM apple_health_daily WHERE athlete_id=? AND health_date=?",
            (athlete_id, health_date),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    low, high, baseline_days = hrv_baseline(athlete_id, health_date, path)
    result["date"] = result.pop("health_date")
    result["source_names"] = json.loads(result.pop("source_names_json") or "[]")
    result["hrv_baseline_low"] = low
    result["hrv_baseline_high"] = high
    result["hrv_baseline_days"] = baseline_days
    result["source"] = "apple_health"
    result.pop("device_id", None)
    return result


def health_rows(
    athlete_id: str,
    start_date: str,
    end_date: str,
    path: str | Path | None = None,
) -> list[dict]:
    init_apple_health_db(path)
    with connect(path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM apple_health_daily
            WHERE athlete_id=? AND health_date>=? AND health_date<?
            ORDER BY health_date
            """,
            (athlete_id, start_date, end_date),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["checkin_date"] = item["health_date"]
        low, high, _ = hrv_baseline(athlete_id, item["health_date"], path)
        item["hrv_baseline_low"] = low
        item["hrv_baseline_high"] = high
        result.append(item)
    return result


def apple_health_status(athlete_id: str, path: str | Path | None = None) -> dict:
    init_apple_health_db(path)
    with connect(path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS days, MIN(health_date) AS first_date,
                   MAX(health_date) AS latest_date, MAX(updated_at) AS last_sync_at
            FROM apple_health_daily WHERE athlete_id=?
            """,
            (athlete_id,),
        ).fetchone()
    return {
        "connected": bool(row["days"]),
        "days": int(row["days"]),
        "first_date": row["first_date"],
        "latest_date": row["latest_date"],
        "last_sync_at": row["last_sync_at"],
        "metrics": ["sleep", "resting_heart_rate", "hrv_sdnn"],
    }


def delete_apple_health(athlete_id: str, path: str | Path | None = None) -> int:
    init_apple_health_db(path)
    with connect(path) as conn:
        cursor = conn.execute("DELETE FROM apple_health_daily WHERE athlete_id=?", (athlete_id,))
    return int(cursor.rowcount)


def enrich_with_apple_health(payload, path: str | Path | None = None):
    state = daily_state(payload.athlete_id, payload.checkin_date, path)
    if not state:
        return payload
    updates = {}
    for field in ("sleep_hours", "hrv_ms", "resting_hr_bpm", "hrv_baseline_low", "hrv_baseline_high"):
        if getattr(payload, field) is None and state.get(field) is not None:
            updates[field] = state[field]
    return payload.model_copy(update=updates) if updates else payload
