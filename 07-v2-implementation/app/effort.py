"""Effort measures retain their source and units; no score-to-rating conversion."""
from statistics import median


def reported(execution):
    return (execution.get('effort') or {}).get('perceived', execution.get('rpe'))


def relative(execution):
    return (execution.get('effort') or {}).get('relative')


def expected_effort(runs, target):
    # Distance and pace matching happen upstream. Further match duration, because
    # Relative Effort is accumulated workload, not a 1–10 intensity rating.
    duration = target.get('duration_minutes',0)*60
    values = [relative(r) for r in runs if relative(r) is not None and
              r.get('duration_seconds') and duration and .8 <= duration/r['duration_seconds'] <= 1.2]
    center = median(values) if len(values)>=3 else None
    spread = max(5,median(abs(v-center) for v in values)*1.4826) if center is not None else None
    return {'relative':round(center,1) if center is not None else None,
            'range':[round(max(0,center-spread),1),round(center+spread,1)] if center is not None else None,
            'samples':len(values),'source':'strava','unit':'Relative Effort score',
            'basis':'Earlier runs matched by distance, pace and duration. Workload comparison, not perceived exertion.'}


def controlled(execution,evaluation,max_hr=None):
    rating=reported(execution)
    if rating is not None: return rating<=4
    # Missing rating is not missing physiology. Use a conservative HR screen for
    # descriptive easy-run traits, without calling HR-derived effort subjective.
    return bool(max_hr and execution.get('average_hr') and execution['average_hr']<=max_hr*.8
                and not execution.get('pain') and (evaluation.get('hr_drift_pct') is None or evaluation['hr_drift_pct']<=7))


def effort_supported_success(execution,evaluation):
    rating=reported(execution)
    if rating is not None: return rating<=4
    forecast=(evaluation.get('expected') or {}).get('effort') or {}
    actual=relative(execution)
    bounds=forecast.get('range')
    return bool(actual is not None and forecast.get('samples',0)>=3 and bounds and actual<=bounds[1])
