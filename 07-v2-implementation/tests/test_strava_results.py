import json
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from app import athlete_store as store
from app.athlete_api import workouts, execution_feedback
from app.athlete_coach import evaluate
from app.athlete_models import GeneratePlan, ExecutionFeedback
from app.athlete_planning import generate
from app.models import ActivityRecord
from app.storage import upsert_activities
from app.strava_results import reconcile
from app.training_plan import RaceGoal, save_goal

DAY = date(2026, 9, 17)

@pytest.fixture
def workout(monkeypatch, tmp_path):
    monkeypatch.setenv('STRIDEAI_DB_PATH', str(tmp_path / 'test.db'))
    monkeypatch.setattr(store, 'today', lambda athlete='viet': DAY)
    store.patch_profile({'available_days': [3], 'recent_weekly_km': 20})
    save_goal(RaceGoal(name='Race', race_date=DAY+timedelta(days=90), goal_minutes=230), 'viet')
    generate(GeneratePlan(start_date=DAY), 'viet')
    return workouts()[0]

def run(id='1', athlete='viet', kind='Run', raw=None):
    upsert_activities([ActivityRecord(source='strava', source_activity_id=id,
        athlete_id=athlete, start_time='2026-09-16T23:00:00Z', activity_type=kind,
        distance_km=5, duration_seconds=1800, average_hr=140,
        raw_format='strava-api-summary', raw_payload=json.dumps(raw or {}))])

def test_auto_match_local_day_and_optional_feedback(workout):
    run()
    assert reconcile('viet')['matched_workouts'] == 1
    assert reconcile('viet')['matched_workouts'] == 0
    x=workouts()[0]['execution']
    assert (x['distance_km'],x['duration_seconds'],x['average_hr'],x['rpe']) == (5,1800,140,None)
    execution_feedback(workout['id'],ExecutionFeedback(rpe=4,pain=True),'viet')
    result=evaluate(workout['id'],'viet')
    assert result['quality']=='recovery_concern'
    with pytest.raises(HTTPException):
        execution_feedback(workout['id'],ExecutionFeedback(rpe=1),'viet')

def test_missing_rpe_does_not_block_review(workout):
    run(raw={'suffer_score': 65})
    reconcile('viet')
    assert workouts()[0]['execution']['rpe'] is None
    assert evaluate(workout['id'],'viet')['rpe_error'] is None

def test_multiple_runs_and_other_athletes_are_not_guessed(workout):
    run(athlete='someone-else')
    run(kind='Tennis')
    assert reconcile('viet')['matched_workouts']==0
    run('2');run('3')
    assert reconcile('viet')['matched_workouts']==0
    assert workouts()[0]['execution'] is None

def test_explicit_effort_imported_only_when_valid(workout):
    run(raw={'perceived_exertion': 4})
    reconcile('viet')
    assert workouts()[0]['execution']['rpe']==4
    with pytest.raises(HTTPException):
        execution_feedback(workout['id'],ExecutionFeedback(rpe=2),'someone-else')
