"""Provisional race-equivalence estimates; no fitness gains invented from adherence."""
import json
from datetime import date
from statistics import median

from app import athlete_store as store
from app.storage import connect
from app.training_plan import get_goal


def race_prediction(athlete='viet'):
    p = store.profile(athlete)
    goal = get_goal(athlete)
    if not goal:
        return {'status': 'unavailable', 'reason': 'Save a race goal first.'}
    today = store.today(athlete)
    evidence = []
    seen = set()
    for pb in p.pbs:
        if pb.date is None or not 0 <= (today-pb.date).days <= 180:
            continue
        key = (pb.date, pb.distance_km, pb.time_seconds)
        if key in seen:
            continue
        seen.add(key)
        evidence.append({'date': pb.date.isoformat(), 'distance_km': pb.distance_km,
                         'time_seconds': pb.time_seconds,
                         'estimate': pb.time_seconds * (goal['distance_km']/pb.distance_km)**1.06})
    # Newer performances replace older anchors, rather than averaging every old PB forever.
    evidence.sort(key=lambda e: e['date'], reverse=True)
    if evidence:
        newest = date.fromisoformat(evidence[0]['date'])
        evidence = [e for e in evidence if (newest-date.fromisoformat(e['date'])).days <= 42]
    observations = [o for o in store.observations(athlete) if 0 <= (today-date.fromisoformat(o['date'])).days <= 42]
    result = {'status': 'estimated' if evidence else 'unavailable', 'as_of': today.isoformat(),
              'goal_seconds': round(goal['goal_minutes']*60), 'evidence': evidence,
              'confidence': 'provisional', 'evaluated_sessions_42d': len(observations),
              'method': 'Recent dated performance equivalence, exponent 1.06. Not a validated race forecast.',
              'reason': 'Add a dated recent race/PB in Athlete. Ordinary training runs are not treated as maximal races.',
              'limitations': 'Course, weather and race-specific endurance are not modeled. Completion alone does not prove a faster race time.'}
    if evidence:
        estimate = round(median(e['estimate'] for e in evidence))
        result.update(predicted_seconds=estimate, range_seconds=[round(estimate*.93), round(estimate*1.10)],
                      reason='Updates when new dated race performances are saved. Range is a heuristic uncertainty band, not a calibrated confidence interval.')
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS coach_race_forecasts (athlete_id TEXT, race_id INTEGER, as_of TEXT, forecast_json TEXT, PRIMARY KEY(athlete_id,race_id,as_of))')
        c.execute('INSERT INTO coach_race_forecasts VALUES(?,?,?,?) ON CONFLICT(athlete_id,race_id,as_of) DO UPDATE SET forecast_json=excluded.forecast_json',
                  (athlete, goal['id'], today.isoformat(), json.dumps(result)))
        history = [json.loads(r[0]) for r in c.execute('SELECT forecast_json FROM coach_race_forecasts WHERE athlete_id=? AND race_id=? ORDER BY as_of', (athlete, goal['id']))]
    return {**result, 'history': history}
