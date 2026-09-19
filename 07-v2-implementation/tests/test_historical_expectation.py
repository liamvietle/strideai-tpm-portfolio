from app.historical_expectation import estimate


def test_imported_easy_uses_historical_data_without_future_leakage():
    target=dict(kind='custom',distance_km=8,pace_target=None,hr_target=None,rpe_target=None)
    runs=[dict(id=i,date=f'2026-09-{i:02d}',distance_km=8,pace=360+i,average_hr=135+i,rpe=3+i%2) for i in range(1,5)]
    runs += [dict(id=9,date='2026-09-19',distance_km=8,pace=100,average_hr=200,rpe=10)]
    result=estimate(target,'2026-09-19',runs,[],183,'easy')
    assert result['pace']==362.5
    assert result['hr']==137.5
    assert result['rpe']==3.5
    assert result['metric_samples']==dict(pace=4,hr=4,rpe=4)
    assert 9 not in result['activity_ids']


def test_metric_coverage_and_wrong_session_types():
    target=dict(kind='custom',distance_km=8,pace_target=None,hr_target=None,rpe_target=None)
    runs=[dict(id=i,date=f'2026-09-{i:02d}',distance_km=8,pace=360,average_hr=140,rpe=None) for i in range(1,5)]
    result=estimate(target,'2026-09-19',runs,[],183,'easy')
    assert result['hr']==140 and result['rpe'] is None
    assert estimate(target,'2026-09-19',runs,[],183,'interval')['pace'] is None
    for r in runs:r['session_kind']='race'
    assert estimate(target,'2026-09-19',runs,[],183,'easy')['samples']==0
