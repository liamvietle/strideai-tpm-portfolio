from datetime import date, timedelta

import httpx
import pytest

from app import race_weather as weather
from app.training_plan import RaceGoal, RaceLocation, save_goal, get_goal

@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv('STRIDEAI_DB_PATH', str(tmp_path/'weather.db'))


def goal(day='2026-12-20'):
    return {'race_date': day, 'goal_minutes': 230, 'start_time': '06:30:00',
            'location': {'name': 'Taipei', 'latitude': 25.03, 'longitude': 121.56, 'timezone': 'Asia/Taipei'}}


def test_seasonal_cache_and_transition(monkeypatch):
    calls=[]
    def fetch(loc, window, hours):
        calls.append(window)
        assert loc['timezone']=='Asia/Taipei'
        assert hours == (6,5)
        return [dict(zip(weather.FIELDS,[28,32,80,5]))]
    monkeypatch.setattr(weather,'_fetch',fetch)
    result=weather.race_weather(goal(),date(2026,9,18))
    assert result['kind']=='seasonal' and result['years']==[2023,2024,2025]
    assert len(calls)==3
    weather.race_weather(goal(),date(2026,9,18))
    assert len(calls)==3
    result=weather.race_weather(goal(),date(2026,12,18))
    assert result['kind']=='forecast' and len(calls)==4
    interval, note=weather.weather_range(10000,result)
    assert interval[0]==9300 and interval[1]>11000
    assert 'experimental' in note


def test_missing_failure_and_validation(monkeypatch):
    assert weather.race_weather({},date.today())['status']=='missing_location'
    g=goal();g['start_time']=None
    assert weather.race_weather(g,date.today())['status']=='missing_start'
    def fail(*args): raise httpx.ConnectError('offline')
    monkeypatch.setattr(weather,'_fetch',fail)
    result=weather.race_weather(goal(),date(2026,9,18))
    assert result['status']=='unavailable'
    assert weather.weather_range(10000,result)[0]==[9300,11000]
    with pytest.raises(ValueError): RaceLocation(name='X',latitude=100,longitude=0,timezone='UTC')
    with pytest.raises(ValueError): RaceLocation(name='X',latitude=0,longitude=0,timezone='invalid')


def test_goal_location_roundtrip_keeps_training_timezone():
    data=goal()
    save_goal(RaceGoal(name='Taipei', **data,timezone='Asia/Ho_Chi_Minh'))
    saved=get_goal()
    assert saved['location']['timezone']=='Asia/Taipei'
    assert saved['timezone']=='Asia/Ho_Chi_Minh'
    assert saved['start_time']=='06:30:00'
    assert get_goal('another') is None


def test_forecast_selects_race_hours_not_next_day(monkeypatch):
    class Response:
        def raise_for_status(self): pass
        def json(self):
            stamps=[f'2026-12-{day}T{h:02d}:00' for day in (20,21) for h in range(24)]
            return {'hourly': {'time':stamps,**{f:list(range(48)) for f in weather.FIELDS}}}
    monkeypatch.setattr(weather.httpx,'get',lambda *a,**kw:Response())
    rows=weather._fetch(goal()['location'],('https://api.open-meteo.com/v1/forecast',date(2026,12,20),date(2026,12,21)),(23,3))
    assert [r['temperature_2m'] for r in rows]==[23,24,25]
