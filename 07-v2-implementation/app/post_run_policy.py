"""Conservative product heuristics, not clinical cutoffs."""


def recovery_response(execution, completion, hr_error, rpe_error, drift):
    reason = execution.get('shortened_reason') or 'unspecified'
    short = not execution['completed'] or completion < .9
    signals = []
    if hr_error is not None and hr_error > 8:
        signals.append(f'Average HR was {hr_error:g} bpm above the saved expectation.')
    if rpe_error is not None and rpe_error > 1.5:
        signals.append(f'Perceived effort was {rpe_error:g} points above the saved expectation.')
    if drift is not None and drift > 7:
        signals.append(f'HR drift was {drift:g}%.')
    if reason == 'fatigue' and short:
        signals.append('You reported shortening the run because of fatigue.')
    physiological = (hr_error is not None and hr_error > 8) or (drift is not None and drift > 7)
    subjective = (rpe_error is not None and rpe_error > 1.5) or (reason == 'fatigue' and short)
    if execution['pain']:
        return dict(action='pause', evidence=['You reported pain during or after the run.'] + signals,
                    explanation='Pain reported: pause upcoming training and reassess before resuming.')
    if physiological and subjective:
        return dict(action='ease_next', evidence=signals,
                    explanation='Both physiological response and reported effort suggest strain. Ease only the next run within 72 hours by 10%, then reassess at check-in. The rest of the week stays unchanged.')
    if signals:
        return dict(action='monitor', evidence=signals,
                    explanation='One type of strain signal needs context. Keep the plan and reassess recovery at the next check-in; no automatic mileage reduction.')
    return dict(action='maintain', evidence=[], explanation=(
        'Run shortened for availability. Keep the remaining plan; no need to make up the missed distance.'
        if short and reason == 'availability' else
        'Less distance was completed, but that alone is not evidence of fatigue. Keep the remaining plan.'
        if short else 'No recovery adjustment indicated by the available data. Keep the plan.'))
