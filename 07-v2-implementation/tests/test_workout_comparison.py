from app.workout_comparison import comparison_metrics


def workout():
    return dict(original=dict(distance_km=5,duration_minutes=30,pace_target=[350,370],hr_target=[130,150],rpe_target=[3,5]),
                execution=dict(distance_km=5,duration_seconds=1850,average_hr=142,rpe=4),prediction=None,choice=None)


def test_legacy_results_display_plan_without_creating_prediction():
    w=workout()
    m={r['metric']:r for r in comparison_metrics(w)}
    assert m['Pace']['expected']==360
    assert m['Pace']['difference']==10
    assert m['HR']['difference']==2
    assert m['RPE']['difference']==0
    assert all(r['basis']=='Plan target' for r in m.values())
    assert w['prediction'] is None


def test_prediction_priority_partial_fallback_and_snapshot():
    w=workout()
    w['execution']['prediction_valid']=True
    w['execution']['target_snapshot']=dict(w['original'],distance_km=4)
    w['choice']='accept'
    w['prediction']={'recommended_expectation':{'pace':365,'hr':None,'rpe':3}}
    m={r['metric']:r for r in comparison_metrics(w)}
    assert m['Pace']['difference']==5
    assert m['Pace']['basis']=='Pre-run prediction'
    assert m['HR']['basis']=='Plan target'
    assert m['Distance']['expected']==4


def test_late_prediction_and_missing_targets_remain_honest():
    w=workout()
    w['original'].update(pace_target=None,hr_target=None,rpe_target=None)
    w['prediction']={'planned_expectation':{'pace':200,'hr':130,'rpe':3}}
    w['execution']['prediction_valid']=False
    m={r['metric']:r for r in comparison_metrics(w)}
    assert m['Pace']['expected'] is None
    assert m['Pace']['difference'] is None
    assert m['Distance']['expected']==5


def test_retrospective_only_fills_missing_values_without_becoming_prediction():
    w=workout()
    w['original'].update(pace_target=None,hr_target=None)
    w['historical_review_estimate']=dict(pace=365,hr=138,rpe=6,metric_samples=dict(pace=5,hr=4,rpe=3))
    m={r['metric']:r for r in comparison_metrics(w)}
    assert m['Pace']['expected']==365 and m['Pace']['difference']==5
    assert m['HR']['expected']==138
    assert m['RPE']['expected']==4  # Explicit plan target preserved.
    assert m['Pace']['basis']=='Historical estimate (retrospective)'
    assert w['prediction'] is None
    w['historical_review_estimate']['metric_samples']['hr']=2
    assert next(r for r in comparison_metrics(w) if r['metric']=='HR')['expected'] is None
