"""Robust descriptive estimates from prior runs; never use the current run."""
from datetime import date, timedelta
from statistics import median, mean


def estimate(target, day, runs, observations, max_hr=None, intensity=None, conditions=None):
    kind = intensity if target['kind'] == 'custom' else target['kind']
    cutoff = (date.fromisoformat(day) - timedelta(days=180)).isoformat()
    evaluated = {o['execution'].get('activity_id'): o for o in observations if o['execution'].get('activity_id')}
    runs = list(runs)
    for i, obs in enumerate(observations):
        x = obs['execution']
        if x.get('activity_id') or not x.get('distance_km') or x.get('pain'):
            continue
        runs.append(dict(id=f'manual-{i}', date=obs['date'], distance_km=x['distance_km'],
                         pace=x['duration_seconds']/x['distance_km'], average_hr=x.get('average_hr'),
                         rpe=x.get('rpe'), session_kind=obs['workout']['kind']))
    pool = []
    for run in runs:
        if not cutoff <= run['date'] < day or not run.get('pace') or not run.get('distance_km'):
            continue
        if not .8 <= target['distance_km'] / run['distance_km'] <= 1.2:
            continue
        obs = evaluated.get(run['id'])
        rpe = obs['execution'].get('rpe') if obs else run.get('rpe')
        known_kind = obs['workout']['kind'] if obs else run.get('session_kind')
        if obs and obs['execution'].get('pain'):
            continue
        if kind not in ('easy', 'long') and known_kind != kind:
            continue
        if kind in ('easy', 'long'):
            if known_kind in ('race','threshold','interval') or (rpe is not None and rpe > 5):
                continue
            if max_hr and run.get('average_hr') and run['average_hr'] > .85 * max_hr:
                continue
        pool.append({**run, 'rpe': rpe, 'session_kind': known_kind})
    pool = sorted(pool, key=lambda r:r['date'])[-20:]
    pace_target = mean(target['pace_target']) if target.get('pace_target') else None
    if pace_target:
        pool = [r for r in pool if abs(r['pace'] / pace_target - 1) <= .15]
    pace = median([r['pace'] for r in pool]) if len(pool) >= 3 else None
    # HR and effort must refer to runs near the expected execution pace.
    similar = [r for r in pool if pace is not None and abs(r['pace']/pace-1) <= .15]
    values = {'pace':[r['pace'] for r in pool],
              'hr':[r['average_hr'] for r in similar if r.get('average_hr') is not None],
              'rpe':[r['rpe'] for r in similar if r.get('rpe') is not None]}
    result = {'samples':len(pool), 'basis':'Historical runs matched by distance, intensity evidence and pace',
              'metric_samples':{}, 'metric_basis':{}, 'ranges':{}, 'activity_ids':[r['id'] for r in pool],
              'limitations':['Conditions matching is descriptive, not a causal or clinically calibrated adjustment. Wind direction, surface and today’s health are not numerically modelled.',
                              'Unlabelled historical runs use HR/effort filters; session type may be uncertain.']}
    for metric, vals in values.items():
        result['metric_samples'][metric] = len(vals)
        if len(vals) >= 3:
            center = median(vals)
            spread = max(median([abs(v-center) for v in vals])*1.4826, {'pace':10,'hr':3,'rpe':1}[metric])
            result[metric] = round(center,1)
            result['ranges'][metric] = [round(max(0,center-spread),1), round(min(10,center+spread) if metric=='rpe' else center+spread,1)]
            result['metric_basis'][metric] = 'Historical observations'
        else:
            limits = target.get({'pace':'pace_target','hr':'hr_target','rpe':'rpe_target'}[metric])
            allowed = metric=='rpe' or kind not in ('threshold','interval','race')
            result[metric] = mean(limits) if limits and allowed else None
            result['metric_basis'][metric] = 'Provisional plan target' if result[metric] is not None else 'Insufficient history'
    result['conditions'] = conditions or {}
    result['condition_adjustments'] = {}
    if conditions:
        feels = conditions.get('feels_like_c')
        gain = conditions.get('elevation_gain_m')
        matches = pool
        if feels is not None:
            matches = [r for r in matches if isinstance(r.get('weather'), dict)
                       and r['weather'].get('feels_like_c') is not None
                       and abs(r['weather']['feels_like_c']-feels) <= 3]
        if gain is not None and target['distance_km'] > 0:
            density = gain / target['distance_km']
            matches = [r for r in matches if r.get('elevation_gain_m') is not None
                       and abs(r['elevation_gain_m']/r['distance_km']-density) <= max(3, density*.3)]
        if feels is not None or gain is not None:
            adjusted = estimate(target, day, matches, [], max_hr, intensity)
            for metric in ('pace','hr','rpe'):
                count = adjusted['metric_samples'][metric]
                applied = count >= 3 and adjusted[metric] is not None
                result['condition_adjustments'][metric] = dict(
                    applied=applied, samples=count, baseline=result[metric],
                    delta=round(adjusted[metric]-result[metric],1) if applied and result[metric] is not None else None,
                    activity_ids=adjusted['activity_ids'],
                    reason='Similar weather/terrain observations' if applied else 'Too few matching observations; baseline retained')
                if applied:
                    result[metric] = adjusted[metric]
                    result['ranges'][metric] = adjusted['ranges'][metric]
                    result['metric_samples'][metric] = count
                    result['metric_basis'][metric] = 'Historical observations in similar conditions'
        if feels is None:
            result['limitations'].append('No run-time forecast supplied: weather matching unavailable.')
        if gain is None:
            result['limitations'].append('Route ascent unknown: terrain matching unavailable.')
    else:
        result['limitations'].append('No expected weather or route ascent supplied; baseline retained.')
    result['quality'] = 'uncertain'
    return result
