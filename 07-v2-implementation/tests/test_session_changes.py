from datetime import date, timedelta
import json
import pytest
from fastapi import HTTPException
from app import athlete_store as store
from app.athlete_api import workouts
from app.session_changes import SessionChange, edit_session
from app.training_plan import RaceGoal, PlanImport, PlanDay, save_goal, save_plan, plan_progress
from app.journey import activate_import
from app.storage import connect

DAY=date(2026,9,19)
@pytest.fixture(autouse=True)
def seeded(tmp_path,monkeypatch):
    monkeypatch.setenv('STRIDEAI_DB_PATH',str(tmp_path/'changes.db'))
    monkeypatch.setattr(store,'today',lambda athlete='viet':DAY)
    g=save_goal(RaceGoal(name='Race',race_date=DAY+timedelta(days=90),goal_minutes=230))
    save_plan(PlanImport(race_id=g['id'],days=[PlanDay(date=DAY+timedelta(days=i),distance_km=km,note=f'Run {km}') for i,km in enumerate([26,8,5])]))
    activate_import()


def apply(wid,**kwargs):
    p=SessionChange(**kwargs)
    preview=edit_session(wid,p)
    assert not preview['saved']
    return edit_session(wid,p.model_copy(update={'confirm_token':preview['confirm_token']}))


def test_swap_preserves_original_week_and_snapshot():
    wid=workouts()[0]['id']
    result=apply(wid,action='swap',reason='availability',swap_date=DAY+timedelta(days=1))
    assert result['weeks']==[{'week':'2026-09-14','before_km':34,'after_km':34}]
    rows=workouts()
    assert [r['current']['distance_km'] for r in rows]==[8,26,5]
    assert rows[0]['original']['distance_km']==26
    assert rows[1]['current']['date']=='2026-09-20'
    assert plan_progress()['days'][0]['distance_km']==8
    assert rows[0]['current']['athlete_change']['reason']=='availability'
    with connect() as c: assert c.execute('SELECT count(*) FROM coach_plan_changes').fetchone()[0]==2


def test_cross_week_skip_and_increase():
    rows=workouts()
    preview=edit_session(rows[0]['id'],SessionChange(action='swap',reason='availability',swap_date=DAY+timedelta(days=2)))
    assert len(preview['weeks'])==2
    result=apply(rows[0]['id'],action='distance',reason='feeling_good',distance_km=30)
    assert result['weeks'][0]['after_km']==38
    apply(rows[0]['id'],action='skip',reason='fatigue')
    assert workouts()[0]['current']['distance_km']==0
    assert workouts()[1]['current']['distance_km']==8


def test_scope_stale_locked_and_safety():
    wid=workouts()[0]['id']
    p=SessionChange(action='distance',reason='availability',distance_km=8)
    with pytest.raises(HTTPException) as e: edit_session(wid,p,'other')
    assert e.value.status_code==404
    preview=edit_session(wid,p)
    apply(wid,action='distance',reason='availability',distance_km=10)
    with pytest.raises(HTTPException): edit_session(wid,p.model_copy(update={'confirm_token':preview['confirm_token']}))
    with pytest.raises(HTTPException): edit_session(wid,SessionChange(action='swap',reason='fatigue',swap_date=DAY+timedelta(days=1)))
    store.patch_profile({'active_injury':True})
    with pytest.raises(HTTPException): edit_session(wid,p)
    apply(wid,action='skip',reason='fatigue')
    with connect() as c: c.execute("UPDATE coach_workouts SET state='recommended_adjustment' WHERE id=?",(wid,))
    with pytest.raises(HTTPException): edit_session(wid,p)
