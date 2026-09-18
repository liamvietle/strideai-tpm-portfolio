"""Persistent pre-run prediction → decision → execution → evaluation → plan update."""

import json
import sqlite3
from datetime import date, datetime, timedelta
from statistics import mean, median, pstdev

from fastapi import HTTPException

from app import athlete_store as store
from app.accumulated_fatigue import evaluate_workout_v21
from app.athlete_learning import can_relax, comparable, health_points, learn
from app.coach_reasoning import choose
from app.models import RecoverySnapshot
from app.personal_models import DailyCheckInInput
from app.personal_service import build_accumulated_input
from app.storage import connect
from app.training_plan import get_goal


def change(c, row, updated, reason, source_id):
    if json.loads(row["current_json"]) == updated:
        return
    c.execute(
        "INSERT INTO coach_plan_changes(athlete_id,workout_id,source_workout_id,before_json,after_json,reason,created_at) VALUES(?,?,?,?,?,?,?)",
        (
            row["athlete_id"],
            row["id"],
            source_id,
            row["current_json"],
            json.dumps(updated),
            reason,
            store.now(),
        ),
    )
    c.execute(
        "UPDATE coach_workouts SET current_json=? WHERE id=?",
        (json.dumps(updated), row["id"]),
    )


def cut(w, factor, easy=False):
    result = {
        **w,
        "distance_km": round(w["distance_km"] * factor, 2),
        "duration_minutes": round(w["duration_minutes"] * factor, 1),
    }
    if factor == 0:
        result.update(
            strength_session=False,
            strength_minutes=0,
            strength_instructions=None,
            kind="rest",
            key_session=False,
            pace_target=None,
            hr_target=None,
            rpe_target=[0, 1],
            instructions="Recovery only. Reassess symptoms before returning to running.",
        )
    elif easy:
        result.update(
            kind="easy",
            key_session=False,
            pace_target=None,
            hr_target=None,
            rpe_target=[2, 3],
            instructions="Easy conversational effort. Stop if symptoms develop; do not chase the original pace.",
        )
    return result


def week_effect(c, row, recommended):
    d = date.fromisoformat(row["date"])
    end = (d + timedelta(days=6 - d.weekday())).isoformat()
    original = json.loads(row["current_json"])
    factor = (
        recommended["distance_km"] / original["distance_km"]
        if original["distance_km"]
        else 1
    )
    effect = [
        {
            "workout_id": row["id"],
            "date": row["date"],
            "before_km": original["distance_km"],
            "after_km": recommended["distance_km"],
            "reason": "Today’s recommended target",
            "workout": recommended,
        }
    ]
    for r in c.execute(
        "SELECT * FROM coach_workouts WHERE athlete_id=? AND active=1 AND date>? AND date<=? AND state='planned' ORDER BY date",
        (row["athlete_id"], row["date"], end),
    ):
        w = json.loads(r["current_json"])
        revised = w
        if factor < 1 and w["kind"] != "race":
            if factor == 0:
                revised = cut(w, 0)
            elif w["key_session"]:
                revised = cut(w, 0.85, easy=True)
        effect.append(
            {
                "workout_id": r["id"],
                "date": r["date"],
                "before_km": w["distance_km"],
                "after_km": revised["distance_km"],
                "reason": "Recovery protection; no catch-up mileage"
                if revised != w
                else "Unchanged; no redistribution of missed distance",
                "workout": revised,
            }
        )
    return effect


def predict(wid, athlete):
    p = store.profile(athlete)
    goal = get_goal(athlete)
    with connect() as c:
        row = store.workout(c, wid, athlete)
        saved = c.execute(
            "SELECT prediction_json FROM coach_predictions WHERE workout_id=?", (wid,)
        ).fetchone()
        if saved:
            return json.loads(saved[0])
        if not goal or row["race_id"] != goal["id"]:
            raise HTTPException(
                409,
                "This workout belongs to an earlier race. Generate the active race plan first.",
            )
        if not row["active"] or row["state"] != "planned":
            raise HTTPException(
                409, "This workout is no longer available for prediction."
            )
        check = c.execute(
            "SELECT * FROM daily_checkins WHERE athlete_id=? AND checkin_date=?",
            (athlete, row["date"]),
        ).fetchone()
        if not check:
            raise HTTPException(409, "Save today’s daily recovery check-in first.")
        check = dict(check)
    if row["date"] != store.today(athlete).isoformat():
        raise HTTPException(
            409, "Predictions can only be locked on the workout day, before running."
        )
    if any(r["date"] == row["date"] for r in store.runs(athlete)):
        raise HTTPException(
            409,
            "A run is already recorded today. Evaluate it without a retrospective prediction.",
        )
    w = json.loads(row["current_json"])
    if not w["distance_km"]:
        raise HTTPException(
            409, "Recovery day: use the daily check-in; no run prediction is needed."
        )
    state = {
        k: check[k]
        for k in [
            "sleep_hours",
            "hrv_ms",
            "hrv_baseline_low",
            "hrv_baseline_high",
            "resting_hr_bpm",
            "soreness_0_10",
            "pain_flag",
            "subjective_fatigue",
            "recent_load_ratio",
        ]
    }
    state["pain_flag"] = bool(state["pain_flag"] or p.active_injury)
    if state["recent_load_ratio"] is None:
        state["recent_load_ratio"] = check["calculated_load_ratio"]
    payload = DailyCheckInInput(
        athlete_id=athlete,
        checkin_date=row["date"],
        planned_distance_km=w["distance_km"],
        planned_intensity="threshold"
        if w["kind"] == "threshold"
        else ("race" if w["kind"] == "race" else "easy"),
        human_decision="maintain",
        **state,
    )
    accumulated, _ = build_accumulated_input(payload)
    prior_health = health_points(athlete, store.today(athlete))
    timeline = {h.day_index: h for h in accumulated.recovery_history}
    for h in prior_health:
        age = (date.fromisoformat(row["date"]) - date.fromisoformat(h["date"])).days
        ordinal = date.fromisoformat(h["date"]).toordinal()
        if 0 < age <= 7 and ordinal not in timeline:
            timeline[ordinal] = RecoverySnapshot(
                day_index=ordinal,
                sleep_hours=h.get("sleep_hours"),
                hrv_ms=h.get("hrv_ms"),
                resting_hr_bpm=h.get("resting_hr"),
            )
    accumulated = accumulated.model_copy(
        update={"recovery_history": list(timeline.values())}
    )
    rec, fatigue = evaluate_workout_v21(accumulated)
    factors = [f.code for f in rec.decision_factors]
    obs = store.observations(athlete)
    matches = comparable(obs, w, state, factors)
    health = health_points(athlete, store.today(athlete))
    traits = learn(athlete)
    # Hard envelope: repeated debt, injury and severe fatigue can never be relaxed.
    relaxed = (
        w["kind"] == "easy"
        and rec.action.value == "reduce_intensity"
        and fatigue.score <= 4
        and not rec.safety_flags
        and not any(
            f.startswith(("ROLLING_", "REPEATED_", "LOAD_", "HRV_STEEPLY", "RHR_"))
            for f in factors
        )
        and can_relax(matches, health)
    )
    recommended = cut(
        w, 1 + rec.volume_change_pct / 100, easy=rec.action.value == "reduce_intensity"
    )
    weather = None
    with connect() as c:
        if check["recommendation_id"]:
            weather_row = c.execute(
                "SELECT weather_json FROM run_weather_decisions WHERE recommendation_id=?",
                (check["recommendation_id"],),
            ).fetchone()
            weather = json.loads(weather_row[0]) if weather_row else None
    if weather and weather.get("action") == "reschedule_or_indoor":
        recommended = cut(w, 0)
        relaxed = False
    elif weather and weather.get("action") == "easy_effort":
        recommended = cut(recommended, 1, easy=True)
        relaxed = False
    candidates = {"baseline": recommended}
    default = "baseline"
    if relaxed:
        candidates["learned_easy"] = w
        default = "learned_easy"
    if recommended["distance_km"] > 0:
        candidates["extra_recovery"] = cut(recommended, 0.8, easy=True)
    context = {
        "athlete_profile": p.model_dump(
            mode="json",
            exclude={"gender", "injury_history", "constraints", "health_history"},
        ),
        "daily_state": state,
        "race": get_goal(athlete),
        "planned_workout": w,
        "learned_traits": traits,
        "comparable_outcomes": matches,
        "recent_outcomes": obs[-8:],
        "recent_load": state["recent_load_ratio"],
        "race_phase": w["phase"],
        "weather": weather,
        "safety": {
            "flags": rec.safety_flags,
            "fatigue_score": fatigue.score,
            "relaxation_eligible": relaxed,
        },
    }
    selected, trace = choose(context, candidates, default)
    selected_workout = candidates[selected]

    # Expectations are for the ORIGINAL session as well as the selected session.
    # This permits an honest comparison if the athlete declines a safe reduction.
    def expectation(target):
        prior = [
            o
            for o in obs
            if target["kind"] != "custom"
            and o["date"] < row["date"]
            and o["workout"]["kind"] == target["kind"]
            and o["evaluation"].get("actual_pace")
            and not o["execution"]["pain"]
            and 0.8
            <= target["distance_km"] / max(o["execution"]["distance_km"], 0.1)
            <= 1.2
        ]
        if len(prior) >= 3:
            pace = median([o["evaluation"]["actual_pace"] for o in prior[-12:]])
            hrs = [
                o["execution"]["average_hr"]
                for o in prior[-12:]
                if o["execution"].get("average_hr")
            ]
            effort = [
                o["execution"]["rpe"]
                for o in prior[-12:]
                if o["execution"].get("rpe") is not None
            ]
            return {
                "pace": round(pace, 1),
                "hr": round(median(hrs), 1) if hrs else None,
                "rpe": round(median(effort), 1) if effort else None,
                "samples": len(prior),
                "basis": "Comparable evaluated sessions",
                "quality": "completion_expected" if fatigue.score <= 2 else "uncertain",
            }
        # Mixed sessions have segment targets but no defensible whole-run pace prediction yet.
        return {
            "pace": mean(target["pace_target"])
            if target.get("pace_target") and target["kind"] not in {"threshold", "race"}
            else None,
            "hr": mean(target["hr_target"])
            if target.get("hr_target") and target["kind"] not in {"threshold", "race"}
            else None,
            "rpe": mean(target["rpe_target"]) if target.get("rpe_target") else None,
            "samples": 0,
            "basis": "Provisional target-based estimate; not yet calibrated",
            "quality": "uncertain",
        }

    with connect() as c:
        effects = week_effect(c, row, selected_workout)
    result = {
        "workout_id": wid,
        "created_at": store.now(),
        "base_action": rec.action.value,
        "selected_candidate": selected,
        "planned": w,
        "recommended": selected_workout,
        "planned_expectation": expectation(w),
        "recommended_expectation": expectation(selected_workout),
        "factor_codes": factors,
        "safety_flags": rec.safety_flags,
        "hard_stop": selected_workout["distance_km"] == 0,
        "warnings": [f.detail for f in rec.decision_factors]
        + (
            ["Stop for pain, dizziness or unusual breathlessness."]
            if selected_workout["distance_km"]
            else []
        ),
        "week_effect": effects,
        "context": context,
        "ai_trace": trace,
        "reason": "Repeated comparable successful outcomes permit maintaining this easy run."
        if selected == "learned_easy"
        else "Targets stay within the current recovery and safety limits.",
    }
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        current = store.workout(c, wid, athlete)
        existing = c.execute(
            "SELECT prediction_json FROM coach_predictions WHERE workout_id=?", (wid,)
        ).fetchone()
        if existing:
            return json.loads(existing[0])
        if (
            current["state"] != "planned"
            or current["current_json"] != row["current_json"]
            or not current["active"]
        ):
            raise HTTPException(409, "Plan changed; reload before predicting.")
        c.execute(
            "INSERT INTO coach_predictions VALUES(?,?,?,?)",
            (wid, check["recommendation_id"], json.dumps(result), result["created_at"]),
        )
        c.execute(
            "UPDATE coach_workouts SET state='recommended_adjustment' WHERE id=?",
            (wid,),
        )
    return result


def decide(wid, payload, athlete):
    store.init_athlete_db()
    decision_day = store.today(athlete).isoformat()
    ran_today = any(r["date"] == decision_day for r in store.runs(athlete))
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row = store.workout(c, wid, athlete)
        pred = c.execute(
            "SELECT prediction_json FROM coach_predictions WHERE workout_id=?", (wid,)
        ).fetchone()
        if not pred:
            raise HTTPException(409, "Save a pre-run prediction first.")
        if row["date"] != decision_day:
            raise HTTPException(
                409, "Record decisions on the workout day, before running."
            )
        if row["state"] in {"executed", "evaluated"}:
            raise HTTPException(409, "Execution is already recorded.")
        existing = c.execute(
            "SELECT choice FROM coach_decisions WHERE workout_id=?", (wid,)
        ).fetchone()
        if existing:
            if existing[0] == payload.choice:
                return {"choice": existing[0]}
            raise HTTPException(
                409,
                "Pre-run choice is locked; record what actually happened after the run.",
            )
        if ran_today:
            raise HTTPException(
                409,
                "A run is already recorded today. Record actual execution without a retrospective choice.",
            )
        pred = json.loads(pred[0])
        c.execute(
            "INSERT INTO coach_decisions VALUES(?,?,?)",
            (wid, payload.choice, store.now()),
        )
        if payload.choice == "accept":
            for effect in pred["week_effect"]:
                other = store.workout(c, effect["workout_id"], athlete)
                if other["active"] and (
                    other["state"] == "planned" or other["id"] == wid
                ):
                    current_target = json.loads(other["current_json"])
                    # An older proposal must never undo a later recovery reduction.
                    if (
                        effect["workout"]["distance_km"]
                        <= current_target["distance_km"]
                    ):
                        change(c, other, effect["workout"], effect["reason"], wid)
    return {
        "choice": payload.choice,
        "safety_warning": "Recovery-only advice remains in force even if declined."
        if pred["hard_stop"]
        else None,
    }


def execute(wid, payload, athlete):
    store.init_athlete_db()
    with connect() as c:
        row = store.workout(c, wid, athlete)
        if not row["active"]:
            raise HTTPException(
                409, "This workout was superseded. Use the active plan."
            )
        pred = c.execute(
            "SELECT prediction_json,created_at FROM coach_predictions WHERE workout_id=?",
            (wid,),
        ).fetchone()
    if row["date"] > store.today(athlete).isoformat():
        raise HTTPException(409, "Cannot record a future execution.")
    x = payload.model_dump(mode="json")
    if payload.activity_id:
        activity = next(
            (r for r in store.runs(athlete) if r["id"] == payload.activity_id), None
        )
        if not activity or activity["date"] != row["date"]:
            raise HTTPException(
                422,
                "Choose a running activity belonging to this athlete on the workout date.",
            )
        x.update(
            distance_km=activity["distance_km"],
            duration_seconds=activity["duration_seconds"],
            average_hr=activity["average_hr"],
            source="synced_activity",
        )
        if x["distance_km"] is None or x["duration_seconds"] is None:
            raise HTTPException(422, "Activity lacks distance or duration.")
        if pred:
            start = datetime.fromisoformat(
                activity["start_time"].replace("Z", "+00:00")
            )
            if start.tzinfo is None or start < datetime.fromisoformat(
                pred["created_at"]
            ):
                x["prediction_valid"] = False
            else:
                x["prediction_valid"] = True
    else:
        x.update(source="manual", prediction_valid=bool(pred))
    if x["distance_km"] > 0 and x["duration_seconds"] <= 0:
        raise HTTPException(422, "A run requires a positive duration.")
    if x["splits"]:
        if abs(sum(s["distance_km"] for s in x["splits"]) - x["distance_km"]) > max(
            0.1, x["distance_km"] * 0.03
        ) or abs(
            sum(s["duration_seconds"] for s in x["splits"]) - x["duration_seconds"]
        ) > max(10, x["duration_seconds"] * 0.03):
            raise HTTPException(
                422,
                "Splits must cover the full run and match distance and duration within 3%.",
            )
    try:
        with connect() as c:
            c.execute("BEGIN IMMEDIATE")
            prior = c.execute(
                "SELECT execution_json FROM coach_executions WHERE workout_id=?", (wid,)
            ).fetchone()
            if prior:
                if json.loads(prior[0]) == x:
                    return {"state": "executed", "workout_id": wid}
                raise HTTPException(
                    409, "Execution is already recorded and cannot be overwritten."
                )
            c.execute(
                "INSERT INTO coach_executions VALUES(?,?,?,?,?)",
                (wid, athlete, payload.activity_id, json.dumps(x), store.now()),
            )
            c.execute("UPDATE coach_workouts SET state='executed' WHERE id=?", (wid,))
    except sqlite3.IntegrityError as e:
        raise HTTPException(409, "This activity is already linked to a workout.") from e
    return {"state": "executed", "workout_id": wid}


def evaluate(wid, athlete):
    store.init_athlete_db()
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row = store.workout(c, wid, athlete)
        saved = c.execute(
            "SELECT evaluation_json FROM coach_evaluations WHERE workout_id=?", (wid,)
        ).fetchone()
        if saved:
            return json.loads(saved[0])
        execution = c.execute(
            "SELECT execution_json FROM coach_executions WHERE workout_id=?", (wid,)
        ).fetchone()
        if not execution:
            raise HTTPException(409, "Record the executed workout first.")
        x = json.loads(execution[0])
        w = json.loads(row["original_json"])
        current = json.loads(row["current_json"])
        prediction = c.execute(
            "SELECT prediction_json FROM coach_predictions WHERE workout_id=?", (wid,)
        ).fetchone()
        decision = c.execute(
            "SELECT choice FROM coach_decisions WHERE workout_id=?", (wid,)
        ).fetchone()
        pred = json.loads(prediction[0]) if prediction else None
        accepted = decision and decision[0] == "accept"
        expected = (
            pred["recommended_expectation" if accepted else "planned_expectation"]
            if pred and x.get("prediction_valid")
            else None
        )
        target = (
            pred["recommended"]
            if pred and accepted
            else (pred.get("planned", w) if pred else current)
        )
        pace = x["duration_seconds"] / x["distance_km"] if x["distance_km"] else None
        completion = (
            x["distance_km"] / target["distance_km"]
            if target["distance_km"]
            else (1 if x["distance_km"] == 0 else 0)
        )

        def error(actual, key):
            return (
                round(actual - expected[key], 2)
                if expected and expected.get(key) is not None and actual is not None
                else None
            )

        pace_error = error(pace, "pace")
        hr_error = error(x["average_hr"], "hr")
        rpe_error = error(x["rpe"], "rpe")
        splits = x["splits"]
        drift = consistency = None
        if len(splits) >= 4:
            paces = [s["duration_seconds"] / s["distance_km"] for s in splits]
            consistency = round(pstdev(paces) / mean(paces) * 100, 2)
            half = len(splits) // 2
            a, b = splits[:half], splits[half:]
            # Report decoupling only for steady sessions with complete HR and stable pace.
            if (
                w["kind"] in {"easy", "long"}
                and consistency <= 10
                and all(s["average_hr"] for s in splits)
            ):

                def efficiency(group):
                    duration = sum(s["duration_seconds"] for s in group)
                    hr = (
                        sum(s["average_hr"] * s["duration_seconds"] for s in group)
                        / duration
                    )
                    return sum(s["distance_km"] for s in group) / duration / hr

                drift = round((1 - efficiency(b) / efficiency(a)) * 100, 2)
        abnormal = (
            x["pain"]
            or not x["completed"]
            or completion < 0.9
            or (hr_error is not None and hr_error > 8)
            or (rpe_error is not None and rpe_error > 1.5)
            or (drift is not None and drift > 7)
        )
        enough = (
            expected
            and pace_error is not None
            and hr_error is not None
            and rpe_error is not None
        )
        pace_matched = (
            pace_error is not None
            and expected
            and abs(pace_error) <= expected["pace"] * 0.10
        )
        comparison = (
            "worse"
            if expected and abnormal
            else (
                "insufficient_data"
                if not enough
                else ("within" if pace_matched else "different_execution")
            )
        )
        if (
            enough
            and not abnormal
            and rpe_error <= -1
            and hr_error <= 0
            and abs(pace_error) <= expected["pace"] * 0.05
        ):
            comparison = "better"
        quality = (
            "recovery_concern"
            if x["pain"]
            else (
                "incomplete_or_strained"
                if abnormal
                else ("completed" if x["completed"] else "unknown")
            )
        )
        result = {
            "workout_id": wid,
            "actual_pace": round(pace, 2) if pace else None,
            "expected": expected,
            "pace_error_seconds_km": pace_error,
            "hr_error_bpm": hr_error,
            "rpe_error": rpe_error,
            "pace_error_pct": round(pace_error / expected["pace"] * 100, 2)
            if pace_error is not None and expected["pace"]
            else None,
            "planned_pace_target": target.get("pace_target"),
            "planned_hr_target": target.get("hr_target"),
            "pace_vs_target_seconds_km": round(pace - mean(target["pace_target"]), 2)
            if pace
            and target.get("pace_target")
            and target["kind"] not in {"threshold", "race"}
            else None,
            "completion_ratio": round(completion, 3),
            "original_completion_ratio": round(x["distance_km"] / w["distance_km"], 3)
            if w["distance_km"]
            else None,
            "hr_drift_pct": drift,
            "pace_consistency_cv_pct": consistency,
            "comparison": comparison,
            "quality": quality,
            "prediction_valid": bool(expected),
            "explanation": {
                "worse": "Below the saved expectation: completion, effort or physiological response raised a concern.",
                "within": "Within the saved athlete-specific expectation.",
                "better": "Lower effort than expected with normal HR and controlled pace.",
                "different_execution": "Pace differed from the saved expectation; HR and effort did not show a clear worse response. Review execution and conditions.",
                "insufficient_data": "Outcome recorded; not enough prospective pace, HR and RPE evidence for an expectation verdict.",
            }[comparison],
            "limitations": [
                "HR drift requires at least four full-run splits with HR and steady pacing.",
                "Faster alone is not better. Terrain and weather can confound comparisons.",
            ],
            "next_changes": [],
        }
        # Atomic, monotonic recovery adjustment: never increase or cram future volume.
        if x["pain"]:
            saved_profile = c.execute(
                "SELECT profile_json FROM athlete_profiles WHERE athlete_id=?",
                (athlete,),
            ).fetchone()
            profile_data = json.loads(saved_profile[0]) if saved_profile else {}
            profile_data["active_injury"] = True
            c.execute(
                "INSERT INTO athlete_profiles VALUES(?,?,?) ON CONFLICT(athlete_id) DO UPDATE SET profile_json=excluded.profile_json,updated_at=excluded.updated_at",
                (athlete, json.dumps(profile_data), store.now()),
            )
        if abnormal:
            end = (date.fromisoformat(row["date"]) + timedelta(days=7)).isoformat()
            future = list(
                c.execute(
                    "SELECT * FROM coach_workouts WHERE athlete_id=? AND active=1 AND date>? AND date<=? AND state='planned'",
                    (athlete, row["date"], end),
                )
            )
            for r in future:
                future_w = json.loads(r["current_json"])
                if future_w["kind"] == "rest" and not (x["pain"] and future_w.get("strength_session")):
                    continue
                revised = cut(future_w, 0 if x["pain"] else 0.85, easy=True)
                reason = (
                    "Pain after running: pause and reassess before resuming."
                    if x["pain"]
                    else "Incomplete or strained session: ease the next seven days; do not make up missed mileage."
                )
                change(c, r, revised, reason, wid)
                result["next_changes"].append(
                    {
                        "date": r["date"],
                        "before_km": future_w["distance_km"],
                        "after_km": revised["distance_km"],
                        "reason": reason,
                    }
                )
        if pred:
            legacy = c.execute(
                "SELECT recommendation_id FROM coach_predictions WHERE workout_id=?",
                (wid,),
            ).fetchone()
            if legacy and legacy[0]:
                # Add coverage to existing metrics without overwriting an independently recorded outcome.
                c.execute(
                    """INSERT OR IGNORE INTO outcomes(recommendation_id,completed,perceived_effort_0_10,pain_after,notes,followed_recommendation,override_action)
                    VALUES(?,?,?,?,?,?,?)""",
                    (
                        legacy[0],
                        int(x["completed"]),
                        round(x["rpe"]) if x["rpe"] is not None else None,
                        int(x["pain"]),
                        x["notes"],
                        int(accepted) if decision else None,
                        "maintain" if decision and not accepted else None,
                    ),
                )
        c.execute(
            "INSERT INTO coach_evaluations VALUES(?,?,?)",
            (wid, json.dumps(result), store.now()),
        )
        c.execute("UPDATE coach_workouts SET state='evaluated' WHERE id=?", (wid,))
    learn(athlete)
    return result
