"""Descriptive athlete traits and bounded personalization from observed outcomes."""

import json
from datetime import date, timedelta
from statistics import mean, median, pstdev

from app import athlete_store as store
from app.storage import connect


def health_points(athlete, as_of):
    p = store.profile(athlete)
    points = {
        h.date.isoformat(): h.model_dump(mode="json")
        for h in p.health_history
        if h.date <= as_of
    }
    with connect() as c:
        for row in c.execute(
            "SELECT * FROM daily_checkins WHERE athlete_id=? AND checkin_date<=? ORDER BY checkin_date",
            (athlete, as_of.isoformat()),
        ):
            d = dict(row)
            point = points.setdefault(d["checkin_date"], {"date": d["checkin_date"]})
            for key, source in [
                ("resting_hr", "resting_hr_bpm"),
                ("sleep_hours", "sleep_hours"),
                ("hrv_ms", "hrv_ms"),
                ("pain", "pain_flag"),
                ("soreness", "soreness_0_10"),
            ]:
                if d.get(source) is not None:
                    point[key] = d[source]
    return sorted(points.values(), key=lambda p: p["date"])


def learn(athlete, as_of=None, persist=True):
    as_of = as_of or store.today(athlete)
    obs = [o for o in store.observations(athlete) if o["date"] <= as_of.isoformat()]
    health = health_points(athlete, as_of)
    traits = {}

    def trait(name, value, n, evidence, minimum=5):
        traits[name] = {
            "value": value,
            "samples": n,
            "confidence": "moderate" if n >= minimum else "low",
            "evidence": evidence,
            "status": "observed" if n >= minimum else "collecting",
            "as_of": as_of.isoformat(),
        }

    from app.effort import controlled, relative
    max_hr = store.profile(athlete).max_hr
    easy = [
        o
        for o in obs
        if o["workout"]["kind"] == "easy"
        and not o["execution"]["pain"]
        and controlled(o["execution"],o["evaluation"],max_hr)
        and o["evaluation"].get("actual_pace")
        and o["execution"].get("average_hr")
    ]
    trait(
        "easy_hr_pace",
        {
            "pace_seconds_km": round(
                median([o["evaluation"]["actual_pace"] for o in easy]), 1
            ),
            "hr_bpm": round(median([o["execution"]["average_hr"] for o in easy]), 1),
        }
        if easy
        else None,
        len(easy),
        "Easy sessions screened by reported effort or available HR; descriptive paired medians, not a causal curve.",
    )
    hrv = [h["hrv_ms"] for h in health[-42:] if h.get("hrv_ms")]
    trait(
        "hrv_variability",
        {"mean_ms": round(mean(hrv), 1), "sd_ms": round(pstdev(hrv), 1)}
        if len(hrv) >= 2
        else None,
        len(hrv),
        "Recent observed days; missing days excluded.",
        14,
    )
    for name, kind in [
        ("long_run_durability", "long"),
        ("threshold_tolerance", "threshold"),
        ("race_hr_patterns", "race"),
    ]:
        selected = [o for o in obs if o["workout"]["kind"] == kind]
        hr = [
            o["execution"]["average_hr"]
            for o in selected
            if o["execution"].get("average_hr")
        ]
        drift = [
            o["evaluation"]["hr_drift_pct"]
            for o in selected
            if o["evaluation"].get("hr_drift_pct") is not None
        ]
        trait(
            name,
            {
                "completed_rate": round(
                    mean(
                        [
                            o["evaluation"]["completion_ratio"] >= 0.9
                            and not o["execution"]["pain"]
                            for o in selected
                        ]
                    ),
                    2,
                ),
                "median_hr": median(hr) if hr else None,
                "median_drift_pct": median(drift) if drift else None,
            }
            if selected
            else None,
            len(selected),
            "Confirmed outcomes; unknown drift remains unknown.",
        )
    poor, normal = [], []
    for o in obs:
        pred = o["prediction"]
        if not pred or pred["context"]["daily_state"].get("sleep_hours") is None:
            continue
        (poor if pred["context"]["daily_state"]["sleep_hours"] < 6 else normal).append(
            o["evaluation"]["completion_ratio"]
        )
    trait(
        "poor_sleep_response",
        {
            "poor_sleep_completion": round(mean(poor), 2),
            "normal_sleep_completion": round(mean(normal), 2),
        }
        if poor and normal
        else None,
        min(len(poor), len(normal)),
        "Completion under <6h vs ≥6h sleep; association only.",
    )
    historical = [r for r in store.runs(athlete) if r["date"] <= as_of.isoformat()]
    effort_runs = [r for r in historical if relative(r) is not None and r.get('duration_seconds')]
    trait('relative_effort_load', {'median_score':median(relative(r) for r in effort_runs),
        'median_score_per_minute':round(median(relative(r)/(r['duration_seconds']/60) for r in effort_runs),2)} if effort_runs else None,
        len(effort_runs), 'Strava workload scores; not subjective effort ratings or independent HR evidence.')
    weeks = {}
    for r in historical:
        d = date.fromisoformat(r["date"])
        start = d - timedelta(days=d.weekday())
        if start + timedelta(days=6) < as_of:
            weeks[start] = weeks.get(start, 0) + (r["distance_km"] or 0)
    recent_weeks = sorted(weeks)[-8:]
    trait(
        "mileage_tolerance",
        {"median_completed_km": round(median([weeks[w] for w in recent_weeks]), 1)}
        if recent_weeks
        else None,
        len(recent_weeks),
        "Observed completed volume, not proof that a higher load is safe.",
        4,
    )
    recoveries = []
    for o in obs:
        if o["workout"]["kind"] != "long":
            continue
        following = [
            h
            for h in health
            if 1
            <= (date.fromisoformat(h["date"]) - date.fromisoformat(o["date"])).days
            <= 2
            and h.get("soreness") is not None
        ]
        recoveries.extend(h["soreness"] for h in following)
    trait(
        "post_long_run_recovery",
        {"mean_soreness_0_10": round(mean(recoveries), 1)} if recoveries else None,
        len(recoveries),
        "Check-ins one to two days after evaluated long runs.",
    )
    for name, why in [
        ("heat_sensitivity", "Needs matched terrain, effort and weather observations."),
        (
            "hrv_readiness_reliability",
            "Needs more paired pre-run HRV and prospective physiological outcomes.",
        ),
        ("recovery_patterns", "Continue daily check-ins including rest days."),
    ]:
        trait(name, None, 0, why)
    if persist:
        with connect() as c:
            for name, t in traits.items():
                c.execute(
                    "INSERT INTO coach_traits VALUES(?,?,?,?) ON CONFLICT(athlete_id,name) DO UPDATE SET trait_json=excluded.trait_json,updated_at=excluded.updated_at",
                    (athlete, name, json.dumps(t), store.now()),
                )
    return traits


def comparable(obs, w, state, factors):
    target = set(factors)
    matches = []
    for o in obs:
        pred = o["prediction"]
        if not pred or o["date"] >= w["date"] or o["workout"]["kind"] != w["kind"]:
            continue
        prior = set(pred["factor_codes"])
        if prior != target:
            continue
        km = o["workout"]["distance_km"]
        if not 0.8 <= w["distance_km"] / max(km, 0.1) <= 1.2:
            continue
        old = pred["context"]["daily_state"]
        if any(
            (state.get(k) is None) != (old.get(k) is None)
            or (state.get(k) is not None and abs(state[k] - old[k]) > delta)
            for k, delta in [("sleep_hours", 1), ("recent_load_ratio", 0.2)]
        ):
            continue
        matches.append(o)
    return matches[-12:]


def can_relax(matches, health):
    """Require independent prospective successes plus next-day evidence; never learn from choice alone."""
    if len(matches) < 5:
        return False
    from app.effort import effort_supported_success
    successful = []
    for o in matches:
        e = o["evaluation"]
        x = o["execution"]
        pred = o["prediction"]
        following = next(
            (
                h
                for h in health
                if h["date"]
                == (date.fromisoformat(o["date"]) + timedelta(days=1)).isoformat()
            ),
            None,
        )
        ok = (
            o["choice"] == "decline"
            and pred["base_action"] == "reduce_intensity"
            and e["completion_ratio"] >= 0.95
            and e["comparison"] in {"within", "better"}
            and e["hr_error_bpm"] is not None
            and abs(e["hr_error_bpm"]) <= 5
            and effort_supported_success(x,e)
            and not x["pain"]
            and following is not None
            and following.get("soreness") is not None
            and following["soreness"] <= 3
            and not following.get("pain")
            and (following.get("sleep_hours") or 0) >= 6
        )
        successful.append(ok)
    return sum(successful) >= 5 and mean(successful) >= 0.8
