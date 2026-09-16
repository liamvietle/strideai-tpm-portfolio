from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from app.models import ActivityRecord
from app.storage import connect, init_db, upsert_activities

STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"


def _client_id() -> str:
    return os.getenv("STRAVA_CLIENT_ID", "").strip()


def _client_secret() -> str:
    return os.getenv("STRAVA_CLIENT_SECRET", "").strip()


def _redirect_uri() -> str:
    return os.getenv("STRAVA_REDIRECT_URI", "").strip()


def strava_configured() -> bool:
    return bool(_client_id() and _client_secret() and _redirect_uri())


def init_strava_db() -> None:
    init_db()
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS strava_connections (
            athlete_id TEXT PRIMARY KEY,
            strava_athlete_id TEXT NOT NULL,
            athlete_name TEXT,
            access_token TEXT NOT NULL,
            refresh_token TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            scope TEXT,
            last_sync_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS strava_oauth_states (
            state TEXT PRIMARY KEY,
            athlete_id TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL
        );
        """)


def _connection(athlete_id: str) -> dict | None:
    init_strava_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM strava_connections WHERE athlete_id=?",
            (athlete_id,),
        ).fetchone()
    return dict(row) if row else None


def strava_status(athlete_id: str = "viet") -> dict[str, object]:
    row = _connection(athlete_id)
    return {
        "configured": strava_configured(),
        "connected": row is not None,
        "athlete_name": row.get("athlete_name") if row else None,
        "scope": row.get("scope") if row else None,
        "last_sync_at": row.get("last_sync_at") if row else None,
        "token_expires_at": row.get("expires_at") if row else None,
    }


def create_authorization_url(athlete_id: str = "viet") -> str:
    if not strava_configured():
        raise RuntimeError("Strava credentials are not configured on the server.")

    state = secrets.token_urlsafe(32)
    now = int(time.time())
    init_strava_db()
    with connect() as conn:
        conn.execute("DELETE FROM strava_oauth_states WHERE created_at_epoch < ?", (now - 900,))
        conn.execute(
            "INSERT INTO strava_oauth_states(state, athlete_id, created_at_epoch) VALUES (?, ?, ?)",
            (state, athlete_id, now),
        )

    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "approval_prompt": "auto",
        "scope": "read,activity:read_all",
        "state": state,
    }
    return f"{STRAVA_AUTHORIZE_URL}?{urlencode(params)}"


def _consume_state(state: str) -> str:
    now = int(time.time())
    init_strava_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT athlete_id, created_at_epoch FROM strava_oauth_states WHERE state=?",
            (state,),
        ).fetchone()
        conn.execute("DELETE FROM strava_oauth_states WHERE state=?", (state,))
    if not row or now - int(row["created_at_epoch"]) > 900:
        raise RuntimeError("Invalid or expired Strava authorization state.")
    return str(row["athlete_id"])


def complete_authorization(*, code: str, state: str, scope: str | None = None) -> dict[str, object]:
    athlete_id = _consume_state(state)
    if not strava_configured():
        raise RuntimeError("Strava credentials are not configured on the server.")

    response = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    athlete = payload.get("athlete") or {}
    athlete_name = " ".join(
        part for part in [athlete.get("firstname"), athlete.get("lastname")] if part
    ) or None

    with connect() as conn:
        conn.execute("""
            INSERT INTO strava_connections (
                athlete_id, strava_athlete_id, athlete_name, access_token,
                refresh_token, expires_at, scope, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(athlete_id) DO UPDATE SET
                strava_athlete_id=excluded.strava_athlete_id,
                athlete_name=excluded.athlete_name,
                access_token=excluded.access_token,
                refresh_token=excluded.refresh_token,
                expires_at=excluded.expires_at,
                scope=excluded.scope,
                updated_at=CURRENT_TIMESTAMP
        """, (
            athlete_id,
            str(athlete.get("id", "")),
            athlete_name,
            payload["access_token"],
            payload["refresh_token"],
            int(payload["expires_at"]),
            scope,
        ))

    return {"athlete_id": athlete_id, "athlete_name": athlete_name}


def _refresh_connection(athlete_id: str, row: dict) -> dict:
    response = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "grant_type": "refresh_token",
            "refresh_token": row["refresh_token"],
        },
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    with connect() as conn:
        conn.execute("""
            UPDATE strava_connections SET
                access_token=?, refresh_token=?, expires_at=?, updated_at=CURRENT_TIMESTAMP
            WHERE athlete_id=?
        """, (
            payload["access_token"],
            payload["refresh_token"],
            int(payload["expires_at"]),
            athlete_id,
        ))
    row = dict(row)
    row.update(
        access_token=payload["access_token"],
        refresh_token=payload["refresh_token"],
        expires_at=int(payload["expires_at"]),
    )
    return row


def _valid_connection(athlete_id: str) -> dict:
    row = _connection(athlete_id)
    if not row:
        raise RuntimeError("Strava is not connected.")
    if not strava_configured():
        raise RuntimeError("Strava credentials are not configured on the server.")
    if int(row["expires_at"]) <= int(time.time()) + 300:
        row = _refresh_connection(athlete_id, row)
    return row


def _activity_record(athlete_id: str, activity: dict) -> ActivityRecord:
    activity_type = activity.get("sport_type") or activity.get("type") or "Activity"
    return ActivityRecord(
        source="strava",
        source_activity_id=str(activity["id"]),
        athlete_id=athlete_id,
        start_time=activity.get("start_date") or activity.get("start_date_local") or datetime.now(timezone.utc).isoformat(),
        activity_type=str(activity_type),
        name=activity.get("name"),
        distance_km=round(float(activity.get("distance", 0.0)) / 1000.0, 4),
        duration_seconds=int(activity.get("moving_time") or activity.get("elapsed_time") or 0),
        average_hr=activity.get("average_heartrate"),
        max_hr=activity.get("max_heartrate"),
        calories=activity.get("calories"),
        raw_format="strava-api-summary",
        raw_payload=json.dumps(activity, separators=(",", ":")),
    )


def sync_strava_activities(athlete_id: str = "viet", *, max_pages: int = 2) -> dict[str, object]:
    row = _valid_connection(athlete_id)
    headers = {"Authorization": f"Bearer {row['access_token']}"}
    records: list[ActivityRecord] = []
    fetched = 0

    for page in range(1, max_pages + 1):
        response = httpx.get(
            STRAVA_ACTIVITIES_URL,
            headers=headers,
            params={"page": page, "per_page": 100},
            timeout=20.0,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        fetched += len(batch)
        for activity in batch:
            activity_type = str(activity.get("sport_type") or activity.get("type") or "")
            if "run" in activity_type.lower():
                records.append(_activity_record(athlete_id, activity))
        if len(batch) < 100:
            break

    inserted, updated = upsert_activities(records)
    synced_at = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute(
            "UPDATE strava_connections SET last_sync_at=?, updated_at=CURRENT_TIMESTAMP WHERE athlete_id=?",
            (synced_at, athlete_id),
        )

    return {
        "fetched": fetched,
        "running_activities": len(records),
        "inserted": inserted,
        "updated": updated,
        "last_sync_at": synced_at,
    }


def disconnect_strava(athlete_id: str = "viet") -> None:
    init_strava_db()
    with connect() as conn:
        conn.execute("DELETE FROM strava_connections WHERE athlete_id=?", (athlete_id,))
