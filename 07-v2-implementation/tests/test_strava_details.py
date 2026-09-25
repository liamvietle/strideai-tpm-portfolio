import json
from datetime import date,timedelta

import httpx
import pytest

from app import athlete_store as store
from app.athlete_api import workouts,weekly_review
from app.athlete_coach import evaluate,predict
from app.athlete_models import GeneratePlan
from app.athlete_planning import generate
from app.effort import expected_effort
from app.models import ActivityRecord
from app.storage import connect,upsert_activities
from app.strava_details import enrich_runs,normalize,stream_splits,split_metrics
from app.strava_results import reconcile
from app.training_plan import RaceGoal,save_goal

DAY=date(2026,9,25)

@pytest.fixture
def db(tmp_path,monkeypatch):
    monkeypatch.setenv('STRIDEAI_DB_PATH',str(tmp_path/'details.db'))
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setattr(store,'today',lambda athlete='viet':DAY)
    store.patch_profile({'available_days':[4],'recent_weekly_km':20,'max_hr':185})
    save_goal(RaceGoal(name='Test',race_date=DAY+timedelta(days=90),goal_minutes=230),'viet')
    generate(GeneratePlan(start_date=DAY),'viet')
    return workouts()[0]


def add_run(id='1',athlete='viet',day=DAY):
    upsert_activities([ActivityRecord(source='strava',source_activity_id=id,athlete_id=athlete,
        start_time=f'{day}T00:00:00Z',activity_type='Run',distance_km=5,duration_seconds=1800,average_hr=140,
        raw_format='strava-api-summary',raw_payload='{}')])


def streams():
    n=181
    return {key:{'data':data} for key,data in {
        'time':[i*10 for i in range(n)],'distance':[i*5000/(n-1) for i in range(n)],
        'moving':[True]*n,'heartrate':[135+i*10/(n-1) for i in range(n)]}.items()}


def provider(monkeypatch,detail=None,hr=True):
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        assert '/athlete/activities/' not in url
        if url.endswith('/streams'):
            body=streams()
            if not hr: body.pop('heartrate')
        else: body=detail or {'id':1,'suffer_score':42,'perceived_exertion':4}
        return httpx.Response(200,request=httpx.Request('GET',url),json=body)
    monkeypatch.setattr('app.strava_details.httpx.get',get)
    return calls


def test_normalized_pace_and_hr_splits():
    out=normalize({'suffer_score':42,'perceived_exertion':4},streams(),5,1800)
    assert len(out['splits'])==5
    assert sum(s['distance_km'] for s in out['splits'])==pytest.approx(5)
    assert sum(s['duration_seconds'] for s in out['splits'])==pytest.approx(1800)
    assert out['splits'][0]['average_hr']<out['splits'][-1]['average_hr']
    assert out['effort']['relative']==42 and out['effort']['perceived']==4
    assert split_metrics(out['splits'],'easy')['hr_drift_pct']>0
    assert split_metrics(out['splits'],'threshold')['hr_drift_pct'] is None
    assert split_metrics(out['splits'],'custom')['hr_drift_pct'] is not None


def test_missing_hr_and_malformed_streams_never_invent_hr():
    data=streams();data.pop('heartrate')
    rows=stream_splits(data,5,1800)
    assert len(rows)==5 and all(r['average_hr'] is None for r in rows)
    assert split_metrics(rows,'easy')['hr_drift_pct'] is None
    data=streams();data['distance']['data'][2]=-1
    assert stream_splits(data,5,1800)==[]
    data=streams();data['time']['data'][2]=100
    assert stream_splits(data,5,1800)==[]
    data=streams();data['heartrate']['data']=data['heartrate']['data'][:2]
    assert stream_splits(data,5,1800)==[]
    assert normalize({'suffer_score':float('nan'),'perceived_exertion':50},{},5,1800)['effort']['relative'] is None


def test_metric_splits_fallback_and_partial_coverage():
    detail={'splits_metric':[{'distance':1000,'moving_time':360} for _ in range(5)]}
    out=normalize(detail,{},5,1800)
    assert out['split_source']=='strava_splits_metric'
    assert out['split_coverage']['with_hr']==0
    assert normalize(detail,{},10,3600)['splits']==[]


def test_initial_link_includes_details_and_summary_refresh_preserves(db,monkeypatch):
    add_run();calls=provider(monkeypatch)
    assert enrich_runs('viet',{})['details_refreshed']==1
    reconcile('viet')
    x=workouts()[0]['execution']
    assert x['effort']==store.runs('viet')[0]['effort']
    assert len(x['splits'])==5 and x['rpe']==4
    add_run()
    assert store.runs('viet')[0]['effort']['relative']==42
    assert enrich_runs('viet',{})['details_status']=='cooldown'
    assert len(calls)==2


def test_existing_evaluated_run_gets_late_details_without_plan_changes(db,monkeypatch):
    add_run();reconcile('viet');evaluate(db['id'],'viet')
    with connect() as c:
        original=c.execute('SELECT evaluation_json FROM coach_evaluations').fetchone()[0]
        execution=c.execute('SELECT execution_json FROM coach_executions').fetchone()[0]
        changes=[tuple(r) for r in c.execute('SELECT * FROM coach_plan_changes')]
    provider(monkeypatch);enrich_runs('viet',{})
    w=workouts()[0]
    assert w['execution']['effort']['relative']==42
    assert w['evaluation']['hr_drift_pct'] is not None
    assert w['evaluation']['detail_refresh']
    assert store.observations('viet')[0]['execution']['effort']['relative']==42
    assert weekly_review()['relative_effort_total']==42
    with connect() as c:
        assert c.execute('SELECT evaluation_json FROM coach_evaluations').fetchone()[0]==original
        assert c.execute('SELECT execution_json FROM coach_executions').fetchone()[0]==execution
        assert [tuple(r) for r in c.execute('SELECT * FROM coach_plan_changes')]==changes


def test_effort_updates_removals_and_user_isolation(db,monkeypatch):
    add_run();add_run('2',athlete='other')
    provider(monkeypatch);enrich_runs('viet',{});reconcile('viet')
    assert not store.runs('other')[0].get('splits')
    with connect() as c:
        c.execute('UPDATE strava_detail_sync SET next_at=0')
        c.execute('UPDATE strava_run_details SET next_at=0')
    provider(monkeypatch,{'id':1,'suffer_score':50,'perceived_exertion':None})
    enrich_runs('viet',{})
    assert workouts()[0]['execution']['effort']['relative']==50
    assert workouts()[0]['execution']['rpe'] is None


def test_rate_limit_does_not_block_matching(db,monkeypatch):
    add_run()
    def get(url,**kw):return httpx.Response(429,request=httpx.Request('GET',url))
    monkeypatch.setattr('app.strava_details.httpx.get',get)
    assert enrich_runs('viet',{})['details_status']=='rate_limited'
    assert reconcile('viet')['matched_workouts']==1
    assert workouts()[0]['execution']['distance_km']==5


def test_backfill_is_bounded_and_progresses(db,monkeypatch):
    for i in range(8):add_run(str(i+1),day=DAY-timedelta(days=i))
    calls=[]
    def get(url,**kw):
        calls.append(url)
        body={} if url.endswith('/streams') else {'id':int(url.rsplit('/',1)[1]),'suffer_score':10}
        return httpx.Response(200,request=httpx.Request('GET',url),json=body)
    monkeypatch.setattr('app.strava_details.httpx.get',get)
    assert enrich_runs('viet',{})['details_refreshed']==3
    with connect() as c:c.execute('UPDATE strava_detail_sync SET next_at=0')
    assert enrich_runs('viet',{})['details_refreshed']==3
    assert len(calls)==12
    with connect() as c:assert c.execute('SELECT COUNT(*) FROM strava_run_details').fetchone()[0]==6


def test_relative_effort_is_not_a_rating_and_duration_matters():
    rows=[{'duration_seconds':1800,'effort':{'relative':v}} for v in [30,40,50]]
    expected=expected_effort(rows,{'duration_minutes':30})
    assert expected['relative']==40 and expected['samples']==3
    assert expected_effort(rows,{'duration_minutes':60})['relative'] is None
    from app.effort import reported
    assert reported(rows[0]) is None


def test_lap_hr_is_retained_when_metric_splits_have_no_hr():
    detail={'splits_metric':[{'distance':1000,'moving_time':360} for _ in range(5)],
            'laps':[{'distance':1250,'moving_time':450,'average_heartrate':140+i} for i in range(4)]}
    out=normalize(detail,{},5,1800)
    assert out['split_source']=='strava_laps'
    assert len(out['splits'])==4 and len(out['pace_splits'])==5


def test_fast_finish_hr_rise_is_not_steady_effort_drift():
    rows=[{'distance_km':1,'duration_seconds':420,'average_hr':130} for _ in range(5)]
    rows.append({'distance_km':1,'duration_seconds':360,'average_hr':155})
    result=split_metrics(rows,'easy',183,167)
    assert result['hr_drift_pct'] is None
    context=result['pace_hr_context']
    assert context['status']=='faster_finish'
    assert context['finish_pace_change_pct']==-14.3
    assert context['finish_hr_change_bpm']==25
    zones=context['hr_zones']
    assert zones['finish_pct_max']==84.7
    assert zones['finish_pct_threshold']==92.8
    assert zones['estimated_seconds_by_split_average']['Z4']==360
    assert not zones['exact_time_in_zones_available']


def test_steady_pace_hr_rise_retains_drift_and_partial_hr_is_unknown():
    rows=[{'distance_km':1,'duration_seconds':400,'average_hr':hr} for hr in [130,130,145,145]]
    result=split_metrics(rows,'easy',183)
    assert result['hr_drift_pct']>7
    assert result['pace_hr_context']['status']=='steady_pace'
    rows[-1]['average_hr']=None
    assert split_metrics(rows,'easy')['hr_drift_pct'] is None
    assert not split_metrics(rows,'easy')['pace_hr_context']['hr_zones']['available']


def test_slowing_finish_is_not_steady_effort_drift():
    rows=[{'distance_km':1,'duration_seconds':pace,'average_hr':140} for pace in [360,360,360,420]]
    assert split_metrics(rows,'long')['hr_drift_pct'] is None
    assert split_metrics(rows,'long')['pace_hr_context']['status']=='variable_pace'
