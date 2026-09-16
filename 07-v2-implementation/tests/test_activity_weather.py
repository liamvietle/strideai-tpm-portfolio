import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app import activity_weather as weather
from app.main import app
from app.storage import connect, init_db, list_activities, upsert_activities
from app.strava_integration import _activity_record


def activity(**changes):
    return {'id': 1, 'sport_type': 'Run', 'name': '<img src=x onerror=alert(1)>',
            'start_date': '2020-01-02T23:45:00Z', 'start_latlng': [21.03, 105.85],
            'distance': 10000, 'moving_time': 3600, 'average_cadence': 86,
            'total_elevation_gain': 0, 'average_temp': 0, **changes}


@pytest.fixture
def database(monkeypatch, tmp_path):
    monkeypatch.setenv('STRIDEAI_DB_PATH', str(tmp_path / 'weather.db'))
    init_db()


def save(raw, athlete='viet'):
    upsert_activities([_activity_record(athlete, raw)])


@pytest.mark.parametrize('changes,expected', [
    ({'trainer': True}, 'indoor'), ({'sport_type': 'VirtualRun'}, 'indoor'),
    ({'sport_type': 'WeightTraining'}, 'indoor'), ({'start_latlng': []}, 'missing_location'),
    ({'start_latlng': [91, 0]}, 'missing_location'), ({'start_latlng': [float('nan'), 0]}, 'missing_location'),
    ({'start_date': None}, 'missing_time'), ({'start_date': '2020-01-02T10:00:00'}, 'missing_time'),
    ({'start_date': '2099-01-01T00:00:00Z'}, 'missing_time'),
])
def test_ineligible_never_calls_provider(database, monkeypatch, changes, expected):
    save(activity(**changes))
    monkeypatch.setattr(weather, 'fetch_weather', lambda _: pytest.fail('Unexpected lookup'))
    weather.enrich_weather()
    assert weather.recent_activities()[0]['weather_status'] == expected


def test_cache_preservation_and_changed_coordinates(database, monkeypatch):
    raw = activity()
    save(raw)
    original = list_activities('viet')[0]
    calls = []
    monkeypatch.setattr(weather, 'fetch_weather', lambda target: calls.append(target) or {'temperature_c': 25})
    weather.enrich_weather()
    save(raw)
    init_db()  # migration/startup is repeatable
    weather.enrich_weather()
    assert len(calls) == 1
    assert list_activities('viet')[0]['raw_payload'] == original['raw_payload']
    assert list_activities('viet')[0]['id'] == original['id']
    assert weather.recent_activities()[0]['weather']['temperature_c'] == 25
    save(activity(start_latlng=[22, 106]))
    assert weather.recent_activities()[0]['weather_status'] == 'pending'
    weather.enrich_weather()
    assert len(calls) == 2
    save(activity(trainer=True))
    assert weather.recent_activities()[0]['weather'] is None


def test_failure_backoff_and_retry(database, monkeypatch):
    save(activity())
    calls = []
    def fail(_):
        calls.append(1)
        raise httpx.ReadTimeout('timeout')
    monkeypatch.setattr(weather, 'fetch_weather', fail)
    weather.enrich_weather()
    weather.enrich_weather()
    assert len(calls) == 1
    assert len(list_activities('viet')) == 1
    assert weather.recent_activities()[0]['weather_status'] == 'unavailable'
    with connect() as conn:
        conn.execute('UPDATE activity_weather SET attempted_at=0')
    monkeypatch.setattr(weather, 'fetch_weather', lambda _: {'temperature_c': 0})
    weather.enrich_weather()
    assert weather.recent_activities()[0]['weather']['temperature_c'] == 0


def test_request_budget_resumes_backfill(database, monkeypatch):
    for i in range(5):
        save(activity(id=i))
    monkeypatch.setattr(weather, 'fetch_weather', lambda _: {'temperature_c': 25})
    weather.enrich_weather(max_requests=2)
    assert sum(a['weather_status'] == 'available' for a in weather.recent_activities()) == 2
    weather.enrich_weather(max_requests=2)
    assert sum(a['weather_status'] == 'available' for a in weather.recent_activities()) == 4


@pytest.mark.parametrize('recent', [False, True])
def test_provider_uses_utc_hour_and_correct_endpoint(monkeypatch, recent):
    start = datetime.now(timezone.utc).replace(minute=45) if recent else datetime.fromisoformat('2020-01-03T06:45:00+07:00')
    target = (21.03, 105.85, start.astimezone(timezone.utc))
    epoch = int(target[2].replace(minute=0, second=0, microsecond=0).timestamp())
    def get(url, params, timeout):
        assert ('archive-api' not in url) == recent
        assert params['timezone'] == 'GMT'
        assert params['start_date'] == target[2].date().isoformat()
        assert params['wind_speed_unit'] == 'kmh'
        return httpx.Response(200, request=httpx.Request('GET', url), json={
            'hourly': {'time': [epoch - 3600, epoch], 'temperature_2m': [99, 0],
                       'relative_humidity_2m': [None, 80]}})
    monkeypatch.setattr(weather.httpx, 'get', get)
    result = weather.fetch_weather(target)
    assert result['temperature_c'] == 0
    assert result['humidity_pct'] == 80
    assert result['wind_kmh'] is None


def test_null_or_mismatched_weather_not_success(monkeypatch):
    target = weather.weather_target(activity())[1]
    monkeypatch.setattr(weather.httpx, 'get', lambda url, **kwargs: httpx.Response(
        200, request=httpx.Request('GET', url), json={'hourly': {'time': [0], 'temperature_2m': [None]}}))
    with pytest.raises(ValueError):
        weather.fetch_weather(target)


def test_api_authorization_isolation_limit_and_safe_payload(database, monkeypatch):
    import app.main as main
    save(activity())
    save(activity(id=2, start_date='2020-01-04T00:00:00Z'))
    save(activity(id=3), 'other')
    monkeypatch.setattr(main, 'APP_KEY', 'test-key')
    with TestClient(app) as client:
        assert client.get('/app/api/activities').status_code == 401
        headers = {'X-StrideAI-Key': 'test-key'}
        response = client.get('/app/api/activities?limit=1', headers=headers)
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1 and items[0]['source_activity_id'] == '2'
        assert 'raw_payload' not in items[0] and 'start_latlng' not in items[0]
        assert client.get('/app/api/activities?limit=101', headers=headers).status_code == 422
        assert len(client.get('/app/api/activities?athlete_id=other', headers=headers).json()) == 1


def test_sync_schedules_enrichment_after_activity_save(database, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, 'APP_KEY', '')
    calls = []
    def sync(athlete):
        save(activity(), athlete)
        return {'inserted': 1}
    def enrich(athlete):
        assert len(list_activities(athlete)) == 1
        calls.append(athlete)
    monkeypatch.setattr(main, 'sync_strava_activities', sync)
    monkeypatch.setattr(main, 'enrich_weather', enrich)
    with TestClient(app) as client:
        assert client.post('/app/api/strava/sync').json()['inserted'] == 1
    assert calls == ['viet']
