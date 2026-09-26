"""Provisional race-equivalence estimates; no fitness gains invented from adherence."""
import json
from datetime import date
from statistics import median
import math

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
    same = [e for e in evidence if abs(e['distance_km']/goal['distance_km']-1)<=.03 and (today-date.fromisoformat(e['date'])).days<=90]
    if evidence:
        newest = date.fromisoformat(evidence[0]['date'])
        evidence = [e for e in evidence if (newest-date.fromisoformat(e['date'])).days <= 42]
    anchors = same[:1] or evidence
    history = [r for r in store.runs(athlete) if 0 <= (today-date.fromisoformat(r['date'])).days <= 84]
    observations = training_observations(history, observations, p.max_hr)
    observations = [o for o in observations if (today-date.fromisoformat(o['date'])).days <= 42]
    progress = training_progress([o for o in observations if anchors and o['date'] > anchors[0]['date']], p.active_injury, p.max_hr)
    support = training_support(history, today, goal['distance_km'])
    result = {'status': 'estimated' if evidence else 'unavailable', 'as_of': today.isoformat(),
              'goal_seconds': round(goal['goal_minutes']*60), 'evidence': anchors, 'other_recent_performances': [e for e in evidence if e not in anchors],
              'weather': weather, 'confidence': 'provisional', 'training_support': support, 'forecast_version':'race-outlook-2', 'weather_training_context':weather_training_context(history,weather,p.max_hr), 'training_progress': progress, 'evaluated_sessions_42d': len(observations),
              'method': 'Recent dated performance equivalence, exponent 1.06. Not a validated race forecast.',
              'reason': 'Add a dated recent race/PB in Athlete. Ordinary training runs are not treated as maximal races.',
              'limitations': 'Current evidence projects to the race distance without assuming future fitness gains. Course and race-specific endurance are not numerically modeled. Weather affects the planning range only. Race-labelled sessions may have been submaximal. This is not a calibrated confidence interval.'}
    if evidence:
        # Prefer a recent same-distance result. Otherwise downweight distant extrapolation.
        weights = [math.exp(-(today-date.fromisoformat(e['date'])).days/90) / (1+abs(math.log(goal['distance_km']/e['distance_km']))) for e in anchors]
        estimate = round(sum(e['estimate']*w for e,w in zip(anchors,weights))/sum(weights))
        anchor_estimate = estimate
        if progress['status'] == 'comparable':
            estimate = round(estimate * (1 + progress['adjustment_fraction']))
        adjusted_range, weather_note = weather_range(estimate, weather)
        age=(today-date.fromisoformat(anchors[0]['date'])).days
        extra=min(.10, max(0,age-42)/180*.04 + (.04 if not same and goal['distance_km']>=40 else 0))
        disagreement=(max(e['estimate'] for e in anchors)-min(e['estimate'] for e in anchors))/estimate
        extra=min(.15, extra+disagreement/2)
        adjusted_range=[round(min(adjusted_range[0],estimate*(.93-extra))),round(max(adjusted_range[1],estimate*(1.10+extra)))]
        result['uncertainty_factors']={'anchor_age_days':age,'same_distance_anchor':bool(same),'extra_range_fraction':round(extra,3),'calibrated_probability':False}
        result['weather_explanation'] = weather_note
        result['drivers']=[f"Performance anchor: {anchors[0]['date']} ({anchors[0]['distance_km']:g} km).",progress['reason'],support['summary'],weather_note]
        result.update(anchor_seconds=anchor_estimate, predicted_seconds=estimate, range_seconds=adjusted_range,
                      reason='A recent same-distance performance is preferred; otherwise race equivalents are weighted by recency and distance similarity. Matched recent training can adjust the estimate by up to 3%. This is a planning estimate, not a validated prediction.')
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS coach_race_forecasts (athlete_id TEXT, race_id INTEGER, as_of TEXT, forecast_json TEXT, PRIMARY KEY(athlete_id,race_id,as_of))')
        c.execute('INSERT INTO coach_race_forecasts VALUES(?,?,?,?) ON CONFLICT(athlete_id,race_id,as_of) DO UPDATE SET forecast_json=excluded.forecast_json',
                  (athlete, goal['id'], today.isoformat(), json.dumps(result)))
        history = [json.loads(r[0]) for r in c.execute('SELECT forecast_json FROM coach_race_forecasts WHERE athlete_id=? AND race_id=? ORDER BY as_of', (athlete, goal['id']))]
    previous = next((h for h in reversed(history) if h.get('as_of','') < today.isoformat() and h.get('predicted_seconds')), None)
    result['change_since_previous'] = {'date':previous['as_of'], 'seconds':result['predicted_seconds']-previous['predicted_seconds']} if previous and result.get('predicted_seconds') else None
    return {**result, 'history': history[-30:]}


def training_progress(observations, active_injury=False, max_hr=None):
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
                and km and seconds and hr and ((rpe is not None and 2 <= rpe <= 4) or (rpe is None and max_hr and hr <= .8*max_hr))
                and seconds >= 1200):
            eligible.append((date.fromisoformat(o['date']), seconds/km, hr, rpe, seconds, o.get('conditions') or {}))
    if len(eligible) < 6:
        return unknown
    eligible.sort(key=lambda r:r[0])
    # Require separated weeks, rather than treating multiple same-day entries as a trend.
    if (eligible[-1][0] - eligible[0][0]).days < 21:
        return unknown
    middle = eligible[0][0] + (eligible[-1][0] - eligible[0][0]) / 2
    before = [r for r in eligible if r[0] <= middle]
    after = [r for r in eligible if r[0] > middle]
    if len({r[0] for r in before}) < 3 or len({r[0] for r in after}) < 3:
        return unknown
    hr_anchor, duration = [median(r[i] for r in before) for i in (2, 4)]
    ratings=[r[3] for r in before if r[3] is not None]
    effort=median(ratings) if ratings else None
    def conditions_match(row):
        for key,tolerance in [('feels_like_c',3),('ascent_per_km',3)]:
            values=[r[5][key] for r in before if r[5].get(key) is not None]
            if len(values)>=3 and (row[5].get(key) is None or abs(row[5][key]-median(values))>tolerance): return False
        return True
    matched = lambda rows: [r for r in rows if abs(r[2]-hr_anchor) <= 5 and (r[3] is None or effort is None or abs(r[3]-effort) <= .5) and .8 <= r[4]/duration <= 1.2 and conditions_match(r)]
    before, after = matched(before), matched(after)
    if len(before) < 3 or len(after) < 3:
        return unknown
    if len({r[0] for r in before})<3 or len({r[0] for r in after})<3: return unknown
    change = median(r[1] for r in after) / median(r[1] for r in before) - 1
    adjustment = max(-.03, min(.03, change * .5))
    return {'status': 'comparable', 'adjustment_fraction': round(adjustment, 4),
            'pace_change_percent': round(change*100, 1),
            'samples_before': len(before), 'samples_after': len(after),
            'reason': 'Matched easy-run HR and duration, plus reported effort when available. Available weather and ascent are matched. Half the observed pace change is applied, capped at 3%; missing conditions and effort can still confound this experimental estimate.'}


def training_observations(runs, observations, max_hr):
    """Include synced easy-like history without requiring a manual rating; avoid double counting."""
    result=list(observations)
    linked={o['execution'].get('activity_id') for o in observations}
    lookup={r['id']:r for r in runs}
    for o in result:
        r=lookup.get(o['execution'].get('activity_id'),{})
        o['conditions']={'feels_like_c':(r.get('weather') or {}).get('feels_like_c'),
                         'ascent_per_km':r['elevation_gain_m']/r['distance_km'] if r.get('elevation_gain_m') is not None and r.get('distance_km') else None}
    for r in runs:
        hr=r.get('average_hr');rating=r.get('rpe')
        if r['id'] in linked or r.get('session_kind')=='race' or not max_hr or not hr or hr>.8*max_hr or (rating is not None and rating>4): continue
        result.append({'date':r['date'],'workout':{'kind':'easy'},
                       'execution':{**{k:r.get(k) for k in ('distance_km','duration_seconds','average_hr','rpe')},'completed':True,'pain':False},
                       'conditions':{'feels_like_c':(r.get('weather') or {}).get('feels_like_c'),
                                     'ascent_per_km':r['elevation_gain_m']/r['distance_km'] if r.get('elevation_gain_m') is not None and r.get('distance_km') else None}})
    return result


def training_support(runs, today, race_km):
    recent=[r for r in runs if 0<=(today-date.fromisoformat(r['date'])).days<42]
    weekly=[round(sum(r.get('distance_km') or 0 for r in recent if i*7<=(today-date.fromisoformat(r['date'])).days<(i+1)*7),1) for i in range(6)]
    longest=max((r.get('distance_km') or 0 for r in recent),default=0)
    return {'weekly_km_newest_first':weekly,'recorded_runs':len(recent),'longest_run_km':round(longest,1),
            'summary':f"Recorded training: {len(recent)} runs in six weeks, longest {longest:.1f} km. Missing imports can understate training. Volume and long runs provide context, not guaranteed time gains."}


def weather_training_context(runs, weather, max_hr):
    if weather.get('status')!='available':
        return {'status':'unavailable','reason':'Race weather is unavailable; no historical conditions comparison.'}
    feels=weather['values']['apparent_temperature']
    pool=[r for r in runs if r.get('average_hr') and max_hr and r['average_hr']<=max_hr*.8 and r.get('pace') and r.get('session_kind')!='race']
    matched=[r for r in pool if (r.get('weather') or {}).get('feels_like_c') is not None and abs(r['weather']['feels_like_c']-feels)<=3]
    return {'status':'observed' if len(matched)>=3 else 'insufficient_data', 'matched_runs':len(matched),
            'race_feels_like_c':feels, 'median_easy_pace':round(median(r['pace'] for r in matched),1) if len(matched)>=3 else None,
            'reason':f"{len(matched)} recorded easy-like runs were within 3°C of the race-period feels-like estimate. These describe experience in similar conditions, not a personal race heat penalty."}
