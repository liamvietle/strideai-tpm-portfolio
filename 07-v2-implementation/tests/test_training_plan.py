import json
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models import ActivityRecord
from app.personal_models import DailyCheckInInput
from app.personal_service import create_personal_recommendation
from app.run_weather import RunWeatherInput, forecast_guidance
from app.storage import connect, upsert_activities
from app.training_plan import RaceGoal, PlanDay, PlanImport, get_goal, save_goal, save_plan, plan_progress


@pytest.fixture
def db(monkeypatch, tmp_path):
    monkeypatch.setenv('STRIDEAI_DB_PATH', str(tmp_path / 'test.db'))


def goal(**kwargs):
    return RaceGoal(name='Test marathon', race_date='2026-12-20', goal_minutes=230, **kwargs)


def test_goal_revisions_and_next_race_preserve_previous_plan(db):
    first = save_goal(goal())
    save_plan(PlanImport(race_id=first['id'], days=[PlanDay(date='2026-09-14', distance_km=8)]))
    assert save_goal(goal())['id'] == first['id']
    assert plan_progress()['revision'] == 1
    second = save_goal(goal(new_race=True))
    assert second['id'] != first['id']
    assert plan_progress()['revision'] is None
    with connect() as conn:
        assert conn.execute('SELECT count(*) FROM training_plans').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM race_goals').fetchone()[0] == 2


def test_local_day_actuals_unknown_days_and_original_plan(db):
    g = save_goal(goal())
    save_plan(PlanImport(race_id=g['id'], days=[PlanDay(date='2026-09-14', distance_km=10), PlanDay(date='2026-09-15', distance_km=8)]))
    upsert_activities([ActivityRecord(source='strava', source_activity_id='1', athlete_id='viet', start_time='2026-09-13T23:00:00Z', activity_type='Run', distance_km=7, raw_format='json', raw_payload=json.dumps({'start_date_local': '2026-09-14T06:00:00Z'})), ActivityRecord(source='strava', source_activity_id='2', athlete_id='viet', start_time='2026-09-14T07:00:00Z', activity_type='Ride', distance_km=50, raw_format='json')])
    create_personal_recommendation(DailyCheckInInput(checkin_date='2026-09-14', planned_distance_km=12, planned_intensity='easy', human_decision='maintain', pain_flag=True))
    p = plan_progress(as_of=date(2026, 9, 15))
    assert p['weeks'][0]['recorded_km'] == 7
    assert p['weeks'][0]['planned_km'] == 18
    assert p['days'][0]['distance_km'] == 10
    assert p['days'][0]['checkin_planned_km'] == 12
    assert p['days'][0]['recommended_km'] == 0
    assert p['days'][1]['recorded_km'] is None
    assert p['weeks'][0]['unrecorded_run_days'] == 1
    assert p['goal']['goal_minutes'] == 230


def test_athlete_isolation_and_duplicate_plan_dates(db):
    save_goal(goal(), 'one')
    assert get_goal('two') is None
    with pytest.raises(ValidationError):
        PlanImport(race_id=1, days=[PlanDay(date='2026-09-14', distance_km=8)] * 2)
    with pytest.raises(ValidationError):
        RaceGoal(name='x', race_date='2026-12-20', goal_minutes=230, timezone='bad/zone')


def request(**kwargs):
    return RunWeatherInput(latitude=21, longitude=105, start=datetime.now(timezone.utc)+timedelta(hours=2), **kwargs)


@pytest.mark.parametrize('feels,action', [(29.9, 'no_heat_adjustment'), (30, 'easy_effort'), (38, 'reschedule_or_indoor')])
def test_forecast_rules_are_separate_and_hour_matched(monkeypatch, feels, action):
    req = request()
    def get(url, **kwargs):
        assert url == 'https://api.open-meteo.com/v1/forecast'
        from app.activity_weather import FIELDS
        hourly = {v: [feels] for v in FIELDS.values()}
        hourly['time'] = [int(req.start.replace(minute=0, second=0, microsecond=0).timestamp())]
        return httpx.Response(200, json={'hourly': hourly}, request=httpx.Request('GET', url))
    monkeypatch.setattr('app.run_weather.httpx.get', get)
    result = forecast_guidance(req)
    assert result['action'] == action
    assert 'not validated' in result['limitation']


def test_weather_failure_and_indoor_do_not_claim_safe(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError('unavailable')
    monkeypatch.setattr('app.run_weather.httpx.get', fail)
    assert forecast_guidance(request())['status'] == 'unavailable'
    assert forecast_guidance(request(indoor=True))['status'] == 'indoor'
    assert forecast_guidance(None)['status'] == 'not_requested'
    req = request().model_copy(update={'start': datetime.now(timezone.utc) - timedelta(days=1)})
    assert forecast_guidance(req)['status'] == 'outside_window'


def test_repeated_reductions_flag_review_without_rewriting_goal(db):
    save_goal(goal())
    for day in ('2026-09-13', '2026-09-14', '2026-09-15'):
        create_personal_recommendation(DailyCheckInInput(checkin_date=day, planned_distance_km=8, planned_intensity='easy', human_decision='maintain', pain_flag=True))
    result = plan_progress(as_of=date(2026, 9, 15))
    assert result['reductions_14d'] == 3
    assert result['review'].startswith('Repeated reductions')
    assert result['goal']['goal_minutes'] == 230


def test_new_endpoints_protected_and_network_error_handled(db, monkeypatch):
    monkeypatch.setattr('app.main.APP_KEY', 'test-key')
    client = TestClient(app)
    assert client.get('/app/api/plan').status_code == 401
    assert client.put('/app/api/goal', json=goal().model_dump(mode='json')).status_code == 401
    def fail(*args):
        raise httpx.ConnectError('DNS failure')
    monkeypatch.setattr('app.main.sync_strava_activities', fail)
    assert client.post('/app/api/strava/sync', headers={'X-StrideAI-Key': 'test-key'}).status_code == 503


def test_strava_uses_documented_endpoint():
    from app.strava_integration import STRAVA_ACTIVITIES_URL
    assert STRAVA_ACTIVITIES_URL == 'https://www.strava.com/api/v3/athlete/activities'
