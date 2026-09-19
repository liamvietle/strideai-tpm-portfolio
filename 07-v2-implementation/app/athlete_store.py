"""Additive athlete-loop migration. Existing ingestion and decision tables are untouched."""

import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.athlete_models import AthleteProfile
from app.personal_storage import init_personal_app_db
from app.storage import connect
from app.training_plan import get_goal, init_plan_db


def init_athlete_db():
    init_personal_app_db()
    init_plan_db()
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS athlete_loop_migrations(version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS athlete_profiles(athlete_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS coach_workouts(
            id INTEGER PRIMARY KEY, athlete_id TEXT NOT NULL, race_id INTEGER NOT NULL,
            date TEXT NOT NULL, original_json TEXT NOT NULL, current_json TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'planned', active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE UNIQUE INDEX IF NOT EXISTS coach_active_day ON coach_workouts(athlete_id,date) WHERE active=1;
        CREATE TABLE IF NOT EXISTS coach_predictions(
            workout_id INTEGER PRIMARY KEY, recommendation_id INTEGER,
            prediction_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS coach_decisions(
            workout_id INTEGER PRIMARY KEY, choice TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS coach_executions(
            workout_id INTEGER PRIMARY KEY, athlete_id TEXT NOT NULL, activity_id INTEGER,
            execution_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS coach_activity_once ON coach_executions(athlete_id,activity_id) WHERE activity_id IS NOT NULL;
        CREATE TABLE IF NOT EXISTS coach_evaluations(
            workout_id INTEGER PRIMARY KEY, evaluation_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS coach_traits(
            athlete_id TEXT NOT NULL, name TEXT NOT NULL, trait_json TEXT NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY(athlete_id,name));
        CREATE TABLE IF NOT EXISTS coach_plan_changes(
            id INTEGER PRIMARY KEY, athlete_id TEXT NOT NULL, workout_id INTEGER NOT NULL,
            source_workout_id INTEGER, before_json TEXT NOT NULL, after_json TEXT NOT NULL,
            reason TEXT NOT NULL, created_at TEXT NOT NULL);
        INSERT OR IGNORE INTO athlete_loop_migrations(version) VALUES(1);
        """)


def now():
    return datetime.now(timezone.utc).isoformat()


def today(athlete="viet"):
    goal = get_goal(athlete)
    return datetime.now(
        ZoneInfo(goal["timezone"] if goal else "Asia/Ho_Chi_Minh")
    ).date()


def profile(athlete="viet"):
    init_athlete_db()
    with connect() as c:
        row = c.execute(
            "SELECT profile_json FROM athlete_profiles WHERE athlete_id=?", (athlete,)
        ).fetchone()
    return AthleteProfile.model_validate_json(row[0]) if row else AthleteProfile()


def patch_profile(data: dict, athlete="viet"):
    current = profile(athlete).model_dump(mode="json")
    current.update(data)
    p = AthleteProfile.model_validate(current)
    with connect() as c:
        c.execute(
            "INSERT INTO athlete_profiles VALUES(?,?,?) ON CONFLICT(athlete_id) DO UPDATE SET profile_json=excluded.profile_json, updated_at=excluded.updated_at",
            (athlete, p.model_dump_json(), now()),
        )
    return p


def workout(c, wid, athlete):
    row = c.execute(
        "SELECT * FROM coach_workouts WHERE id=? AND athlete_id=?", (wid, athlete)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Workout not found.")
    return dict(row)


def runs(athlete):
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM activities WHERE athlete_id=? AND lower(activity_type) IN ('run','running','trailrun','virtualrun') ORDER BY start_time",
            (athlete,),
        ).fetchall()
    result = []
    zone = ZoneInfo((get_goal(athlete) or {}).get("timezone", "Asia/Ho_Chi_Minh"))
    for row in rows:
        r = dict(row)
        try:
            raw = json.loads(r.get("raw_payload") or "{}")
            raw = raw if isinstance(raw, dict) else {}
        except ValueError:
            raw = {}
        try:
            start = datetime.fromisoformat(r["start_time"].replace("Z", "+00:00"))
            r["date"] = (
                raw.get("start_date_local")
                or (
                    start.astimezone(zone).isoformat()
                    if start.tzinfo
                    else start.isoformat()
                )
            )[:10]
            date.fromisoformat(r["date"])
        except (ValueError, TypeError):
            continue
        r["pace"] = (
            r["duration_seconds"] / r["distance_km"]
            if r.get("duration_seconds") and r.get("distance_km")
            else None
        )
        # Raw wearable payloads and locations do not enter the AI evidence package.
        result.append({k: v for k, v in r.items() if k != "raw_payload"})
    return result


def observations(athlete):
    with connect() as c:
        rows = c.execute(
            """SELECT w.date,w.original_json,w.current_json,p.prediction_json,d.choice,
            x.execution_json,e.evaluation_json FROM coach_workouts w
            JOIN coach_evaluations e ON e.workout_id=w.id
            JOIN coach_executions x ON x.workout_id=w.id
            LEFT JOIN coach_predictions p ON p.workout_id=w.id
            LEFT JOIN coach_decisions d ON d.workout_id=w.id
            WHERE w.athlete_id=? ORDER BY w.date,w.id""",
            (athlete,),
        ).fetchall()
    result = []
    for r in rows:
        pred = json.loads(r["prediction_json"]) if r["prediction_json"] else None
        # Keep retrieved cases flat: embedding full prior context recursively grows exponentially.
        summary = (
            {k: pred[k] for k in ("base_action", "factor_codes", "created_at")}
            if pred
            else None
        )
        if summary is not None:
            summary["context"] = {"daily_state": pred["context"]["daily_state"]}
        planned = (
            (pred.get("planned") or json.loads(r["original_json"]))
            if pred
            else json.loads(r["current_json"])
        )
        performed = pred["recommended"] if pred and r["choice"] == "accept" else planned
        result.append(
            {
                "date": r["date"],
                "workout": performed,
                "prediction": summary,
                "choice": r["choice"],
                "execution": json.loads(r["execution_json"]),
                "evaluation": json.loads(r["evaluation_json"]),
            }
        )
    return result
