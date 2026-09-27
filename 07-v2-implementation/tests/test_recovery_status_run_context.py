import json
from datetime import date,timedelta
import pytest
from fastapi import HTTPException
from app import athlete_store as store
from app.storage import connect
from app.recovery_status import status
from app.garmin_recovery import RecoveryImport,import_recovery
from app.run_context import RunContext,save,read,assess
from app.athlete_models import GeneratePlan,Execution
from app.athlete_planning import generate
from app.training_plan import RaceGoal,save_goal
from app.athlete_api import workouts
from app.athlete_coach import execute,evaluate

DAY=date(2026,9,27)
@pytest.fixture(autouse=True)
def isolated(monkeypatch,tmp_path):
    monkeypatch.setenv('STRIDEAI_DB_PATH',str(tmp_path/'test.db'))
    monkeypatch.setenv('STRIDEAI_COACH_AI_ENABLED','false')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setattr(store,'today',lambda athlete='viet':DAY)
    store.init_athlete_db()


def test_status_is_dated_partial_and_scoped():
    assert status('a',DAY)['status']=='missing'
    import_recovery(RecoveryImport(format='strideai-garmin-recovery-v1',days=[{'date':DAY,'sleep_hours':7}]),'a')
    result=status('a',DAY)
    assert result['status']=='partial' and result['metrics'][0]['source']=='Garmin import'
    assert result['metrics'][0]['record_updated_at']
    assert result['metrics'][1]['value'] is None
    assert status('b',DAY)['status']=='missing'
    assert status('a',DAY+timedelta(days=1))['status']=='missing'


def test_mixed_sources_use_garmin_only_for_present_fields():
    status('a',DAY)
    with connect() as c:
        c.execute('INSERT INTO apple_health_daily(athlete_id,health_date,timezone,sleep_hours,resting_hr_bpm,hrv_ms,device_id,generated_at) VALUES(?,?,?,?,?,?,?,?)',('a',DAY.isoformat(),'Asia/Ho_Chi_Minh',8,45,55,'device','2026-09-27T00:00:00Z'))
    import_recovery(RecoveryImport(format='strideai-garmin-recovery-v1',days=[{'date':DAY,'sleep_hours':7}]),'a')
    result=status('a',DAY)
    assert result['status']=='complete'
    assert [m['source'] for m in result['metrics']]==['Garmin import','Apple Health companion','Apple Health companion']
    assert result['metrics'][0]['value']==7


def sample(reason='felt_fresh'):
    return {'original':{'distance_km':26,'kind':'long'},'execution':{'distance_km':10,'completed':True,'target_snapshot':{'distance_km':8,'kind':'easy'}},
            'run_context':{'reason':reason},'evaluation':{},'comparison_metrics':[{'metric':'HR','difference':1,'basis':'Saved prediction'},{'metric':'Pace','expected':400,'difference':5}]}


def test_extension_uses_swapped_target_and_needs_corrobation():
    w=sample();assert assess(w)['signal']=='positive_tolerance'
    assert assess(w)['planned_km']==8 and assess(w)['extra_km']==2
    w['comparison_metrics']=[];assert assess(w)['signal']=='self_reported_capacity'
    assert assess(sample('pushed_harder'))['signal']=='extra_effort'
    assert assess(sample('route_or_company'))['signal']=='extra_distance'
    w=sample();w['execution']['pain']=True;assert assess(w)['signal']=='recovery_concern'
    w=sample();w['execution']['distance_km']=8.1;assert assess(w) is None


def test_post_review_context_preserves_evaluation_and_plan_and_updates_coach():
    store.patch_profile({'available_days':list(range(7))},'a')
    save_goal(RaceGoal(name='Race',race_date=DAY+timedelta(days=90),goal_minutes=240),'a')
    generate(GeneratePlan(start_date=DAY),'a');w=workouts('a')[0];wid=w['id']
    execute(wid,Execution(distance_km=w['current']['distance_km']+2,duration_seconds=3600,average_hr=140,completed=True),'a');evaluate(wid,'a')
    with connect() as c:
        before=c.execute('SELECT evaluation_json FROM coach_evaluations WHERE workout_id=?',(wid,)).fetchone()[0]
        plan=[tuple(r) for r in c.execute('SELECT * FROM coach_plan_changes')]
    save(wid,RunContext(reason='felt_fresh',notes='Still comfortable at the end.'),'a')
    result=next(r for r in workouts('a') if r['id']==wid)
    assert result['run_context']['reason']=='felt_fresh' and result['extra_distance_assessment']
    from app.coach_briefing import build_context
    _,evidence,_=build_context(result,'a')
    assert evidence['athlete_post_run_context']['notes']=='Still comfortable at the end.'
    with connect() as c:
        assert c.execute('SELECT evaluation_json FROM coach_evaluations WHERE workout_id=?',(wid,)).fetchone()[0]==before
        assert [tuple(r) for r in c.execute('SELECT * FROM coach_plan_changes')]==plan
    with pytest.raises(HTTPException): save(wid,RunContext(reason='pushed_harder'),'b')
    save(wid,RunContext(reason='pushed_harder'),'a')
    assert read(wid,'a')['reason']=='pushed_harder'
    with connect() as c: assert c.execute('SELECT COUNT(*) FROM coach_run_context').fetchone()[0]==2
