"""Provisional race-equivalence estimates; no fitness gains invented from adherence."""
import json
from datetime import date
from statistics import median

from app import athlete_store as store
from app.storage import connect
from app.training_plan import get_goal
from app.race_weather import race_weather, weather_range


def race_prediction(athlete='viet'):
    p = store.profile(athlete)
    goal = get_goal(athlete)
    if not goal:
        return {'status': 'unavailable', 'reason': 'Save a race goal first.'}
    today = store.today(athlete)
    weather = race_weather(goal, today)
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
    observations = [o for o in store.observations(athlete) if 0 <= (today-date.fromisoformat(o['date'])).days <= 180]
    # Only explicitly planned, completed races are performance anchors.
    # Easy runs and threshold work are never mistaken for maximal efforts.
    for o in observations:
        x = o['execution']
        km, seconds = x.get('distance_km'), x.get('duration_seconds')
        if (o['workout']['kind'] != 'race' or not x.get('completed')
                or x.get('pain') or not km or not seconds):
            continue
        planned_km = o['workout']['distance_km']
        if not planned_km or abs(km / planned_km - 1) > .03:
            continue
        key = (date.fromisoformat(o['date']), km, seconds)
        if key in seen:
            continue
        seen.add(key)
        evidence.append({'date': o['date'], 'distance_km': km,
                         'time_seconds': seconds, 'source': 'completed race',
                         'estimate': seconds * (goal['distance_km']/km)**1.06})
    # Newer performances replace older anchors, rather than averaging every old PB forever.
    evidence.sort(key=lambda e: e['date'], reverse=True)
    if evidence:
        newest = date.fromisoformat(evidence[0]['date'])
        evidence = [e for e in evidence if (newest-date.fromisoformat(e['date'])).days <= 42]
    observations = [o for o in observations if (today-date.fromisoformat(o['date'])).days <= 42]
    progress = training_progress([o for o in observations if evidence and o['date'] > evidence[0]['date']], p.active_injury)
    result = {'status': 'estimated' if evidence else 'unavailable', 'as_of': today.isoformat(),
              'goal_seconds': round(goal['goal_minutes']*60), 'evidence': evidence,
              'weather': weather, 'confidence': 'provisional', 'training_progress': progress, 'evaluated_sessions_42d': len(observations),
              'method': 'Recent dated performance equivalence, exponent 1.06. Not a validated race forecast.',
              'reason': 'Add a dated recent race/PB in Athlete. Ordinary training runs are not treated as maximal races.',
              'limitations': 'Course and race-specific endurance are not modeled. Weather affects the planning range only. Completion alone does not prove a faster race time.'}
    if evidence:
        estimate = round(median(e['estimate'] for e in evidence))
        anchor_estimate = estimate
        if progress['status'] == 'comparable':
            estimate = round(estimate * (1 + progress['adjustment_fraction']))
        adjusted_range, weather_note = weather_range(estimate, weather)
        result['weather_explanation'] = weather_note
        result.update(anchor_seconds=anchor_estimate, predicted_seconds=estimate, range_seconds=adjusted_range,
                      reason='Updates with dated PBs and completed races; comparable easy sessions can apply a provisional adjustment capped at 3%. Range is heuristic, not a calibrated confidence interval.')
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS coach_race_forecasts (athlete_id TEXT, race_id INTEGER, as_of TEXT, forecast_json TEXT, PRIMARY KEY(athlete_id,race_id,as_of))')
        c.execute('INSERT INTO coach_race_forecasts VALUES(?,?,?,?) ON CONFLICT(athlete_id,race_id,as_of) DO UPDATE SET forecast_json=excluded.forecast_json',
                  (athlete, goal['id'], today.isoformat(), json.dumps(result)))
        history = [json.loads(r[0]) for r in c.execute('SELECT forecast_json FROM coach_race_forecasts WHERE athlete_id=? AND race_id=? ORDER BY as_of', (athlete, goal['id']))]
    return {**result, 'history': history}


def training_progress(observations, active_injury=False):
    """A bounded hypothesis from matched effort, not proof of race performance."""
    unknown = {'status': 'insufficient_data', 'adjustment_fraction': 0,
               'reason': 'Needs three comparable easy runs in each half of the last six weeks. Training adherence alone does not change the estimate.'}
    if active_injury:
        return {**unknown, 'reason': 'Training-based adjustment paused during active injury.'}
    eligible = []
    for o in observations:
        x = o['execution']
        km, seconds, hr, rpe = (x.get(k) for k in ('distance_km', 'duration_seconds', 'average_hr', 'rpe'))
        if (o['workout']['kind'] == 'easy' and x.get('completed') and not x.get('pain')
                and km and seconds and hr and rpe is not None and 2 <= rpe <= 4
                and seconds >= 1200):
            eligible.append((date.fromisoformat(o['date']), seconds/km, hr, rpe, seconds))
    if len(eligible) < 6:
        return unknown
    eligible.sort()
    # Require separated weeks, rather than treating multiple same-day entries as a trend.
    if (eligible[-1][0] - eligible[0][0]).days < 21:
        return unknown
    middle = eligible[0][0] + (eligible[-1][0] - eligible[0][0]) / 2
    before = [r for r in eligible if r[0] <= middle]
    after = [r for r in eligible if r[0] > middle]
    if len({r[0] for r in before}) < 3 or len({r[0] for r in after}) < 3:
        return unknown
    hr_anchor, effort, duration = [median(r[i] for r in before) for i in (2, 3, 4)]
    matched = lambda rows: [r for r in rows if abs(r[2]-hr_anchor) <= 5 and abs(r[3]-effort) <= .5 and .8 <= r[4]/duration <= 1.2]
    before, after = matched(before), matched(after)
    if len(before) < 3 or len(after) < 3:
        return unknown
    change = median(r[1] for r in after) / median(r[1] for r in before) - 1
    adjustment = max(-.03, min(.03, change * .5))
    return {'status': 'comparable', 'adjustment_fraction': round(adjustment, 4),
            'pace_change_percent': round(change*100, 1),
            'samples_before': len(before), 'samples_after': len(after),
            'reason': 'Matched easy-run HR, RPE and duration. Half the observed pace change is applied, capped at 3%; terrain and weather may still confound this experimental estimate.'}
