from app.post_run_policy import recovery_response


def response(reason='unspecified', hr=None, rpe=None, drift=None, pain=False):
    return recovery_response(dict(completed=False, shortened_reason=reason, pain=pain),7.1/8,hr,rpe,drift)


def test_time_limited_7_1_of_8_does_not_cut_week():
    assert response('availability',hr=-4,rpe=0)['action']=='maintain'
    assert response()['action']=='maintain'


def test_single_signal_or_correlated_hr_signals_only_monitor():
    assert response(hr=9)['action']=='monitor'
    assert response(rpe=2)['action']=='monitor'
    assert response(drift=8)['action']=='monitor'
    assert response('fatigue')['action']=='monitor'
    assert response(hr=9,drift=8)['action']=='monitor'


def test_independent_signals_ease_next_and_pain_preserved():
    assert response(hr=9,rpe=2)['action']=='ease_next'
    assert response('fatigue',drift=8)['action']=='ease_next'
    assert response('availability',hr=9,rpe=2)['action']=='ease_next'
    assert response('availability',pain=True)['action']=='pause'
