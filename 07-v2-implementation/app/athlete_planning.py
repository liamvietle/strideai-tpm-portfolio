"""First-pass plans and evidence-based targets, independent of race aspirations."""

import json
from datetime import date, timedelta
from statistics import median

from fastapi import HTTPException

from app import athlete_store as store
from app.storage import connect
from app.training_plan import PlanDay, PlanImport, get_goal, save_plan


def pace_anchor(p, historical, as_of):
    if p.threshold_pace:
        return p.threshold_pace * 1.25, "Reported threshold pace", 0
    recent = [
        r["pace"]
        for r in historical
        if r.get("pace")
        and 180 <= r["pace"] <= 1200
        and 0 < (as_of - date.fromisoformat(r["date"])).days <= 42
    ]
    if len(recent) >= 3:
        return (
            median(recent) * 1.05,
            "Recent running pace; intensity labels incomplete",
            len(recent),
        )
    fresh_pb = [pb for pb in p.pbs if pb.date and 0 <= (as_of - pb.date).days <= 180]
    if fresh_pb:
        pb = max(fresh_pb, key=lambda pb: pb.date)
        return (
            pb.time_seconds / pb.distance_km * 1.3,
            "Recent reported PB; provisional easy pace",
            1,
        )
    return None, "Use conversational effort until pace evidence is available", 0


def targets(p, kind, easy_pace, km):
    pace = easy_pace * (0.84 if kind == "threshold" else 1)
    pace_range = [round(pace * 0.95), round(pace * 1.08)] if easy_pace else None
    hr = None
    if p.threshold_hr:
        hr = [
            round(p.threshold_hr * (0.94 if kind == "threshold" else 0.75)),
            round(p.threshold_hr * (1 if kind == "threshold" else 0.87)),
        ]
    elif p.max_hr:
        hr = [
            round(p.max_hr * (0.82 if kind == "threshold" else 0.65)),
            round(p.max_hr * (0.9 if kind == "threshold" else 0.78)),
        ]
    return {
        "pace_target": pace_range,
        "hr_target": hr,
        "rpe_target": [6, 7] if kind == "threshold" else [2, 4],
        "duration_minutes": round(km * (pace or 480) / 60, 1),
        "distance_km": round(km, 2),
    }


def plan_setup(athlete):
    goal = get_goal(athlete)
    if not goal:
        raise HTTPException(409, "Save a target race first.")
    today = store.today(athlete)
    finish = date.fromisoformat(goal['race_date'])
    weeks = 16 if goal['distance_km'] >= 40 else 12 if goal['distance_km'] >= 20 else 10 if goal['distance_km'] >= 9 else 8
    return {'today': today.isoformat(), 'race_date': finish.isoformat(), 'recommended_weeks': weeks,
            'recommended_start': max(today, finish - timedelta(weeks=weeks) + timedelta(days=1)).isoformat(),
            'note': 'Suggested duration is a starting heuristic, not a guarantee of race readiness. A short window does not justify cramming training.'}


def generate(payload, athlete):
    p = store.profile(athlete)
    goal = get_goal(athlete)
    if not goal:
        raise HTTPException(
            409, "Save a target race first. Your profile can remain incomplete."
        )
    finish = date.fromisoformat(goal["race_date"])
    today = store.today(athlete)
    start = payload.start_date
    if payload.start_mode == 'today':
        start = today
    elif payload.start_mode == 'next_monday':
        start = today + timedelta(days=7 - today.weekday())
    elif payload.start_mode == 'recommended':
        weeks = payload.duration_weeks or plan_setup(athlete)['recommended_weeks']
        start = max(today, finish - timedelta(weeks=weeks) + timedelta(days=1))
    if start is None:
        raise HTTPException(422, 'Choose a start date or start option.')
    if start < store.today(athlete) or not 0 < (finish - start).days <= 365:
        raise HTTPException(
            422, "Start today or later, with a race within the following 365 days."
        )
    history = store.runs(athlete)
    recent = [
        r for r in history if 0 < (start - date.fromisoformat(r["date"])).days <= 28
    ]
    # At least three observed weeks before estimating chronic volume.
    span = (start - date.fromisoformat(recent[0]["date"])).days if recent else 0
    baseline = (
        sum(r["distance_km"] or 0 for r in recent) / 4
        if span >= 21
        else p.recent_weekly_km
    )
    baseline = baseline if baseline is not None else 9.0
    easy, source, n = pace_anchor(p, history, start)
    days = p.available_days
    minutes_per_km = (easy or 480) / 60
    baseline = min(baseline, len(days) * p.max_session_minutes / minutes_per_km)
    if p.active_injury:
        baseline = 0
    result = []
    for offset in range((finish - start).days + 1):
        d = start + timedelta(days=offset)
        week = offset // 7
        remaining = (finish - d).days
        factor = min(1.3, 1.05**week) * (0.8 if week % 4 == 3 else 1)
        if remaining < 14:
            factor *= (0.6 if remaining < 7 else 0.8) if p.race_priority == "A" else 0.9
        kind = "rest"
        km = 0
        phase = "taper" if remaining < 14 else ("base" if week < 3 else "build")
        if d.weekday() in days and baseline > 0 and d != finish:
            long_day = p.long_run_day if p.long_run_day is not None else days[-1]
            candidates = [day for day in days if min((day-long_day)%7, (long_day-day)%7) >= 2]
            key_day = min(candidates, key=lambda day: abs((long_day-day)%7-3)) if len(days) >= 4 and candidates else None
            kind = "long" if d.weekday() == long_day and len(days) >= 3 else "easy"
            if (
                d.weekday() == key_day
                and week >= 3
                and remaining >= 10
                and (p.running_years or 0) >= 1
                and baseline >= 25
            ):
                kind = "threshold"
            # Adjacent days never both carry key sessions.
            if result and result[-1]["key_session"] and kind == "threshold":
                kind = "easy"
            share = (
                0.3
                if kind == "long"
                else (0.7 / (len(days) - 1) if len(days) >= 3 else 1 / len(days))
            )
            km = min(baseline * factor * share, p.max_session_minutes / minutes_per_km)
            if kind == "long":
                km = min(km, 30)
        purpose = {
            "rest": "Recovery and adaptation",
            "easy": "Aerobic consistency at conversational effort",
            "long": "Aerobic durability without racing",
            "threshold": "Controlled sustained effort",
        }[kind]
        w = {
            "date": d.isoformat(),
            "kind": kind,
            "phase": phase,
            "purpose": purpose,
            "key_session": kind in {"long", "threshold"},
            **targets(p, kind, easy or 0, km),
            "pace_basis": source,
            "pace_samples": n,
            "instructions": "Keep it conversational; slow down if HR or effort rises.",
        }
        if kind == "threshold" and w["duration_minutes"] < 35:
            kind = "easy"
            w.update(
                kind="easy",
                purpose="Aerobic consistency at conversational effort",
                key_session=False,
                **targets(p, "easy", easy or 0, km),
            )
        if kind == "threshold":
            w["instructions"] = (
                "Warm up easily for 15 minutes, run 2 × 6 minutes at RPE 6–7 with 3 minutes easy between, then cool down. Pace/HR targets apply to the work portions."
            )
            w["segments"] = [
                {"purpose": "warmup", "minutes": 15, "rpe": [2, 3]},
                {"purpose": "work", "repeats": 2, "minutes": 6, "rpe": [6, 7]},
                {"purpose": "recovery", "minutes": 3, "rpe": [2, 3]},
            ]
        if kind == "rest":
            w.update(
                pace_target=None,
                hr_target=None,
                rpe_target=[0, 1],
                instructions="Rest or gentle movement if comfortable.",
            )
        if d == finish:
            w.update(
                kind="race",
                purpose="Target event; reassess readiness before committing",
                key_session=True,
                distance_km=goal["distance_km"],
                duration_minutes=goal["goal_minutes"],
                pace_target=None,
                hr_target=None,
                rpe_target=None,
                instructions="Your finish-time goal is an aspiration. Review recent training and recovery before choosing a race effort.",
            )
        w['strength_session'] = bool(p.include_strength and d.weekday() in p.strength_days and remaining >= 7 and not p.active_injury)
        w['strength_minutes'] = min(30, max(0, p.max_session_minutes - w['duration_minutes'])) if w['strength_session'] else 0
        w['strength_session'] = w['strength_minutes'] >= 10
        w['strength_instructions'] = 'Optional familiar runner-strength exercises at comfortable effort; stop with pain. Omitted in race week and during active injury.' if w['strength_session'] else None
        if w["strength_session"] and w["distance_km"] == 0:
            w["purpose"] = "Strength training; no run scheduled"
            w["instructions"] = "Keep the effort comfortable. If also playing tennis or another sport, account for that effort and shorten or skip strength if tired."
        result.append(w)
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        existing = c.execute(
            "SELECT id FROM coach_workouts WHERE athlete_id=? AND active=1", (athlete,)
        ).fetchone()
        if existing and not payload.replace_existing:
            raise HTTPException(
                409,
                "A living plan exists. Select replace future plan to generate a new revision.",
            )
        locked = {
            r["date"]
            for r in c.execute(
                "SELECT date FROM coach_workouts WHERE athlete_id=? AND active=1 AND (state!='planned' OR date<?)",
                (athlete, start.isoformat()),
            )
        }
        c.execute(
            "UPDATE coach_workouts SET active=0 WHERE athlete_id=? AND active=1 AND state='planned' AND date>=?",
            (athlete, start.isoformat()),
        )
        for w in result:
            if w["date"] in locked:
                continue
            c.execute(
                "INSERT INTO coach_workouts(athlete_id,race_id,date,original_json,current_json) VALUES(?,?,?,?,?)",
                (athlete, goal["id"], w["date"], json.dumps(w), json.dumps(w)),
            )
    # Retain interoperability with the pre-existing Plan view.
    with connect() as c:
        snapshot = [
            json.loads(r[0])
            for r in c.execute(
                "SELECT current_json FROM coach_workouts WHERE athlete_id=? AND race_id=? AND active=1 ORDER BY date",
                (athlete, goal["id"]),
            )
        ]
    save_plan(
        PlanImport(
            race_id=goal["id"],
            source="Athlete profile first-pass plan",
            days=[
                PlanDay(
                    date=w["date"],
                    distance_km=w["distance_km"],
                    activity=("other" if w.get("strength_session") else "rest") if w["kind"] == "rest" else "run",
                    note=w["purpose"],
                )
                for w in snapshot
            ],
        ),
        athlete,
    )
    return {
        'start_date': start.isoformat(),
        'duration_weeks': ((finish-start).days + 7)//7,
        "workouts": len(result),
        "baseline_weekly_km": round(baseline, 1),
        "assumptions": [
            source,
            "Availability and maximum session time cap training volume.",
            "No catch-up mileage. Race ambition does not increase training targets.",
            "Active injury blocks automatic running."
            if p.active_injury
            else "Unknown training history starts with low volume.",
        ],
        "race_feasibility": "Needs review"
        if goal["distance_km"] > baseline or (finish - start).days < 28
        else "Not a finish-time prediction",
    }
