from datetime import timedelta
import pytest
from fastapi import HTTPException
from app import athlete_store as store
from app.journey import status, save_status, SetupState, activate_import
from app.training_plan import RaceGoal, PlanImport, PlanDay, save_goal, save_plan
from app.athlete_api import workouts

@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('STRIDEAI_DB_PATH', str(tmp_path/'journey.db'))

def test_setup_resumes_and_is_scoped():
    assert status()['finished'] is False
    save_status(SetupState(step=1))
    assert status()['step'] == 1
    assert status('other')['step'] == 0
    save_status(SetupState(step=1, finished=True))
    assert status()['finished'] is True

def test_import_preserves_nonrunning_and_does_not_replace_locked_plan():
    today = store.today()
    goal = save_goal(RaceGoal(name='Test', race_date=today+timedelta(days=90), goal_minutes=240))
    save_plan(PlanImport(race_id=goal['id'], days=[PlanDay(date=today, distance_km=8, note='Intervals from my coach'), PlanDay(date=today+timedelta(days=1), distance_km=0, activity='other', note='Strength')]))
    assert status()['finished'] is True  # existing athletes bypass onboarding
    assert activate_import()['activated'] == 1
    w = workouts()[0]
    assert w['current']['kind'] == 'custom'
    assert w['current']['pace_target'] is None
    assert w['current']['purpose'] == 'Intervals from my coach'
    with pytest.raises(HTTPException) as error:
        activate_import()
    assert error.value.status_code == 409
    assert len(workouts()) == 1
    with pytest.raises(HTTPException):
        activate_import('other')

def test_journey_endpoints_require_existing_app_key(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setattr('app.main.APP_KEY', 'test-only-key')
    with TestClient(app) as client:
        assert client.get('/app/api/journey').status_code == 401
        assert client.put('/app/api/journey', json={'step': 1}).status_code == 401
        assert client.post('/app/api/journey/activate-import', json={}).status_code == 401
        assert client.get('/app/api/journey', headers={'X-StrideAI-Key': 'test-only-key'}).status_code == 200
