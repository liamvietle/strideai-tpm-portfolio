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


def test_weather_and_terrain_matching_adjusts_each_metric():
    target=dict(kind='easy',distance_km=8,pace_target=None,hr_target=None,rpe_target=None)
    runs=[]
    for i in range(1,9):
        hot=i>4
        runs.append(dict(id=i,date=f'2026-09-{i:02d}',distance_km=8,
            pace=390 if hot else 350,average_hr=145 if hot else 135,rpe=4 if hot else 3,
            weather={'feels_like_c':32 if hot else 20},elevation_gain_m=160 if hot else 0))
    base=estimate(target,'2026-09-19',runs,[],183)
    adjusted=estimate(target,'2026-09-19',runs,[],183,conditions={'feels_like_c':33,'elevation_gain_m':150})
    assert base['pace']==370 and adjusted['pace']==390
    assert adjusted['hr']==145 and adjusted['rpe']==4
    assert adjusted['condition_adjustments']['pace']['delta']==20
    assert adjusted['condition_adjustments']['pace']['activity_ids']==[5,6,7,8]
    missing=estimate(target,'2026-09-19',runs,[],183,conditions={'feels_like_c':42,'elevation_gain_m':150})
    assert missing['pace']==base['pace']
    assert not missing['condition_adjustments']['pace']['applied']


def test_zero_ascent_is_known_but_missing_ascent_is_not_flat():
    target=dict(kind='easy',distance_km=8,pace_target=None,hr_target=None,rpe_target=None)
    runs=[dict(id=i,date=f'2026-09-{i:02d}',distance_km=8,pace=360,average_hr=140,rpe=None) for i in range(1,5)]
    missing=estimate(target,'2026-09-19',runs,[],183,conditions={'elevation_gain_m':0})
    assert missing['condition_adjustments']['pace']['samples']==0
    for r in runs:r['elevation_gain_m']=0
    matched=estimate(target,'2026-09-19',runs,[],183,conditions={'elevation_gain_m':0})
    assert matched['condition_adjustments']['pace']['applied']
    assert not matched['condition_adjustments']['rpe']['applied']
    assert matched['rpe'] is None
