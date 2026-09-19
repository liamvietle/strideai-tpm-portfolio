"""Athlete-loop endpoints share the existing app-key middleware and SQLite volume."""

import json
from datetime import date, timedelta
from statistics import mean, median

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app import athlete_store as store
from app.athlete_coach import decide, evaluate, execute, predict
from app.athlete_learning import health_points, learn
from app.athlete_models import Decision, Execution, GeneratePlan
from app.athlete_planning import generate, plan_setup
from app.race_prediction import race_prediction
from app.session_changes import SessionChange, edit_session
from app.storage import connect
from app.training_plan import get_goal

router = APIRouter(prefix="/app/api/coach", tags=["Athlete loop"])


@router.get('/plan-setup')
def setup_plan(athlete_id: str = 'viet'):
    return plan_setup(athlete_id)


@router.get('/race-prediction')
def forecast_race(athlete_id: str = 'viet'):
    return race_prediction(athlete_id)


@router.get("/profile")
def get_profile(athlete_id: str = "viet"):
    p = store.profile(athlete_id)
    history = store.runs(athlete_id)
    goal = get_goal(athlete_id)
    return {
        "profile": p.model_dump(mode="json"),
        "goal": goal,
        "historical_runs": len(history),
        "missing": [
            f
            for f in [
                "age",
                "running_years",
                "recent_weekly_km",
                "resting_hr",
                "hrv_ms",
                "threshold_pace",
                "threshold_hr",
                "max_hr",
            ]
            if getattr(p, f) is None
        ],
        "today": store.today(athlete_id).isoformat(),
    }


@router.patch("/profile")
def update_profile(payload: dict, athlete_id: str = "viet"):
    try:
        return store.patch_profile(payload, athlete_id)
    except ValidationError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/plan")
def generate_plan(payload: GeneratePlan, athlete_id: str = "viet"):
    return generate(payload, athlete_id)


@router.get("/workouts")
def workouts(athlete_id: str = "viet"):
    store.init_athlete_db()
    with connect() as c:
        rows = c.execute(
            """SELECT w.*,p.prediction_json,d.choice,x.execution_json,e.evaluation_json
            FROM coach_workouts w LEFT JOIN coach_predictions p ON p.workout_id=w.id
            LEFT JOIN coach_decisions d ON d.workout_id=w.id
            LEFT JOIN coach_executions x ON x.workout_id=w.id
            LEFT JOIN coach_evaluations e ON e.workout_id=w.id
            WHERE w.athlete_id=? AND w.active=1 ORDER BY w.date""",
            (athlete_id,),
        ).fetchall()
    result = []
    for row in rows:
        r = dict(row)
        for key in ("original", "current", "prediction", "execution", "evaluation"):
            raw = r.pop(key + "_json")
            r[key] = json.loads(raw) if raw else None
        if r["prediction"]:
            # UI needs evidence summary, not a duplicated longitudinal payload.
            r["prediction"].pop("context", None)
        result.append(r)
    return result


@router.post("/workouts/{wid}/change")
def change_session(wid: int, payload: SessionChange, athlete_id: str = "viet"):
    return edit_session(wid, payload, athlete_id)


@router.post("/workouts/{wid}/predict")
def predict_workout(wid: int, athlete_id: str = "viet"):
    return predict(wid, athlete_id)


@router.post("/workouts/{wid}/decision")
def choose_workout(wid: int, payload: Decision, athlete_id: str = "viet"):
    return decide(wid, payload, athlete_id)


@router.post("/workouts/{wid}/execution")
def execute_workout(wid: int, payload: Execution, athlete_id: str = "viet"):
    return execute(wid, payload, athlete_id)


@router.post("/workouts/{wid}/evaluate")
def evaluate_workout(wid: int, athlete_id: str = "viet"):
    return evaluate(wid, athlete_id)


@router.get("/activities")
def candidate_activities(day: date, athlete_id: str = "viet"):
    store.init_athlete_db()
    return [
        {
            k: r[k]
            for k in [
                "id",
                "date",
                "name",
                "distance_km",
                "duration_seconds",
                "average_hr",
                "source",
            ]
        }
        for r in store.runs(athlete_id)
        if r["date"] == day.isoformat()
    ]


@router.get("/intelligence")
def intelligence(athlete_id: str = "viet"):
    return learn(athlete_id)


@router.get("/review")
def weekly_review(week: date | None = None, athlete_id: str = "viet"):
    store.init_athlete_db()
    today = store.today(athlete_id)
    day = week or today
    start = day - timedelta(days=day.weekday())
    end = start + timedelta(days=6)
    through = min(end, today)
    if start > today:
        raise HTTPException(422, "Choose the current week or an earlier week.")
    ws = [
        w
        for w in workouts(athlete_id)
        if start.isoformat() <= w["date"] <= end.isoformat()
    ]
    obs = [
        o
        for o in store.observations(athlete_id)
        if start.isoformat() <= o["date"] <= through.isoformat()
    ]
    all_runs = [
        r
        for r in store.runs(athlete_id)
        if start.isoformat() <= r["date"] <= through.isoformat()
    ]
    synced_km = sum(r["distance_km"] or 0 for r in all_runs)
    with connect() as c:
        manual = c.execute(
            """SELECT w.date,x.execution_json FROM coach_executions x JOIN coach_workouts w ON w.id=x.workout_id
             WHERE x.athlete_id=? AND x.activity_id IS NULL AND w.date>=? AND w.date<=?""",
            (athlete_id, start.isoformat(), through.isoformat()),
        ).fetchall()
        changes = [
            dict(r)
            for r in c.execute(
                """SELECT pc.*,w.date FROM coach_plan_changes pc JOIN coach_workouts w ON w.id=pc.workout_id
            JOIN coach_workouts src ON src.id=pc.source_workout_id
            WHERE pc.athlete_id=? AND src.date>=? AND src.date<=? ORDER BY pc.id""",
                (athlete_id, start.isoformat(), through.isoformat()),
            )
        ]
    # Avoid counting manual executions again if a later sync supplies the day's run.
    manual_km = sum(
        json.loads(r["execution_json"])["distance_km"]
        for r in manual
        if not any(a["date"] == r["date"] for a in all_runs)
    )
    health = health_points(athlete_id, through)
    sleeps = [
        h["sleep_hours"]
        for h in health
        if start.isoformat() <= h["date"] <= through.isoformat()
        and h.get("sleep_hours") is not None
    ]
    previous = [
        h["sleep_hours"]
        for h in health
        if (start - timedelta(days=7)).isoformat() <= h["date"] < start.isoformat()
        and h.get("sleep_hours") is not None
    ]
    recovery = "Insufficient paired weekly recovery data"
    if len(sleeps) >= 3 and len(previous) >= 3:
        delta = mean(sleeps) - mean(previous)
        recovery = f"Observed sleep {delta:+.1f} h/night versus previous week ({len(sleeps)} observed nights)"
    after_traits = learn(athlete_id, through, persist=False)
    before_traits = learn(athlete_id, start - timedelta(days=1), persist=False)
    learning = []
    for name, trait in after_traits.items():
        before = before_traits[name]
        if trait["samples"] > before["samples"] and trait["value"] is not None:
            values = ", ".join(
                f"{k.replace('_', ' ')}: {v}"
                for k, v in trait["value"].items()
                if v is not None
            )
            learning.append(
                f"{name.replace('_', ' ')}: {values}. {trait['samples']} observations; {trait['confidence']} confidence."
            )
    fitness = "Insufficient controlled evidence to estimate fitness change; track matched easy-run pace/HR over multiple weeks."
    all_obs = store.observations(athlete_id)
    easy = [
        o
        for o in all_obs
        if o["workout"]["kind"] == "easy"
        and o["evaluation"].get("actual_pace")
        and o["execution"].get("average_hr")
        and o["execution"].get("rpe") is not None
        and o["execution"]["rpe"] <= 4
        and not o["execution"]["pain"]
    ]
    a = [
        o
        for o in easy
        if (start - timedelta(days=14)).isoformat() <= o["date"] < start.isoformat()
    ]
    b = [o for o in easy if start.isoformat() <= o["date"] <= through.isoformat()]
    if (
        len(a) >= 3
        and len(b) >= 3
        and abs(
            median(o["execution"]["average_hr"] for o in a)
            - median(o["execution"]["average_hr"] for o in b)
        )
        <= 3
    ):
        delta = (
            median(o["evaluation"]["actual_pace"] for o in b)
            / median(o["evaluation"]["actual_pace"] for o in a)
            - 1
        ) * 100
        fitness = f"Easy-run pace changed {delta:+.1f}% at similar HR (negative means faster). This is an observational fitness proxy; weather and terrain are not controlled."
    planned_load = sum(
        w["original"]["duration_minutes"] * mean(w["original"]["rpe_target"])
        for w in ws
        if w["original"].get("rpe_target")
    )
    completed_load = sum(
        o["execution"]["duration_seconds"] / 60 * o["execution"]["rpe"]
        for o in obs
        if o["execution"].get("rpe") is not None
    )
    return {
        "week": start.isoformat(),
        "through": through.isoformat(),
        "planned_km": round(sum(w["original"]["distance_km"] for w in ws), 1),
        "current_plan_km": round(sum(w["current"]["distance_km"] for w in ws), 1),
        "completed_km": round(synced_km + manual_km, 1),
        "planned_load_minutes_rpe": round(planned_load),
        "recorded_load_minutes_rpe": round(completed_load),
        "load_coverage": f"{sum(o['execution'].get('rpe') is not None for o in obs)} of {len(all_runs) + len(manual)} recorded runs have evaluated RPE; incomplete load is not zero load.",
        "key_sessions": [
            {
                "date": w["date"],
                "purpose": w["original"]["purpose"],
                "quality": (w["evaluation"] or {}).get("quality", "Not evaluated"),
            }
            for w in ws
            if w["original"]["key_session"]
        ],
        "fitness_trend": fitness,
        "recovery_trend": recovery,
        "learned_this_week": [
            f"{len(obs)} new evaluated sessions; {sum(o['evaluation']['prediction_valid'] for o in obs)} with usable prospective comparisons.",
            f"{sum(o['evaluation']['comparison'] == 'worse' for o in obs)} sessions below saved expectations.",
            *learning,
        ],
        "next_week_changes": [
            {
                "date": r["date"],
                "before_km": json.loads(r["before_json"])["distance_km"],
                "after_km": json.loads(r["after_json"])["distance_km"],
                "reason": r["reason"],
            }
            for r in changes
            if r["date"] > end.isoformat()
        ],
        "plan_changes": [{"date": r["date"], "reason": r["reason"]} for r in changes],
        "next_week_reason": "Recovery-driven changes are listed above. Otherwise keep the current progression; missing observations do not justify increasing volume.",
    }
