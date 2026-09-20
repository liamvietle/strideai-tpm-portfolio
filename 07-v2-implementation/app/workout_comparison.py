"""Display target comparisons without treating plan targets as predictions."""
from statistics import mean


def comparison_metrics(workout):
    execution = workout.get('execution') or {}
    prediction = workout.get('prediction') or {}
    valid = bool(execution.get('prediction_valid') and prediction)
    accepted = workout.get('choice') == 'accept'
    forecast = prediction.get('recommended_expectation' if accepted else 'planned_expectation', {}) if valid else {}
    target = execution.get('target_snapshot') or (
        prediction.get('recommended' if accepted else 'planned') if valid else None
    ) or workout.get('execution_target') or workout['original']
    retrospective = workout.get("historical_review_estimate") or {}
    result = []
    for metric, actual, target_key in (
        ('Distance', execution.get('distance_km'), 'distance_km'),
        ('Duration', execution.get('duration_seconds'), 'duration_minutes'),
        ('Pace', execution.get('duration_seconds', 0) / execution['distance_km'] if execution.get('distance_km') else None, 'pace_target'),
        ('HR', execution.get('average_hr'), 'hr_target'),
        ('RPE', execution.get('rpe'), 'rpe_target'),
    ):
        expected = forecast.get(metric.lower()) if metric in ('Pace', 'HR', 'RPE') else None
        basis = 'Pre-run prediction' if expected is not None else 'Plan target'
        bounds = None
        if expected is None:
            value = target.get(target_key)
            if isinstance(value, list):
                bounds = value or None
                expected = mean(value) if value else None
            else:
                expected = value * 60 if metric == 'Duration' and value is not None else value
        samples = None
        if expected is None and metric in ('Pace','HR','RPE'):
            key = metric.lower()
            samples = retrospective.get('metric_samples', {}).get(key, 0)
            if samples >= 3 and retrospective.get(key) is not None:
                expected = retrospective[key]
                basis = 'Historical estimate (retrospective)'
        result.append(dict(samples=samples, metric=metric, expected=expected, target_range=bounds,
            actual=actual, difference=round(actual-expected, 2) if actual is not None and expected is not None else None,
            basis=basis if expected is not None else 'No saved target'))
    return result
