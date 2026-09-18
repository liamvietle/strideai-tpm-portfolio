"""Race-hour forecasts or recent seasonal samples, never a distant-date forecast."""
import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from statistics import median

import httpx

from app.activity_weather import number
from app.storage import connect, init_db

FIELDS = ['temperature_2m', 'apparent_temperature', 'relative_humidity_2m', 'wind_speed_10m']


def _fetch(location, start, end):
    url, first, last = start
    response = httpx.get(url, params={
        'latitude': location['latitude'], 'longitude': location['longitude'],
        'start_date': first.isoformat(), 'end_date': last.isoformat(),
        'hourly': ','.join(FIELDS), 'timezone': location['timezone'],
        'temperature_unit': 'celsius', 'wind_speed_unit': 'kmh',
    }, timeout=4)
    response.raise_for_status()
    hourly = response.json()['hourly']
    rows = []
    for i, timestamp in enumerate(hourly['time']):
        stamp = datetime.fromisoformat(timestamp)
        # Hours after the local start, including races crossing midnight.
        if '/forecast' in url:
            beginning = datetime.combine(first, datetime.min.time()) + timedelta(hours=end[0])
            if not beginning <= stamp < beginning + timedelta(hours=end[1]):
                continue
        hour_offset = (stamp.hour - end[0]) % 24
        if hour_offset >= end[1]:
            continue
        values = {f: number(hourly[f][i]) for f in FIELDS}
        if all(v is not None for v in values.values()):
            rows.append(values)
    if not rows:
        raise ValueError('No complete race-hour weather data')
    return rows


def race_weather(goal, today):
    location = goal.get('location')
    if not location:
        return {'status': 'missing_location', 'summary': 'Add the race location to include expected conditions.'}
    if not goal.get('start_time'):
        return {'status': 'missing_start', 'summary': 'Add the local race start time to assess conditions during the race.'}
    race_date = date.fromisoformat(goal['race_date'])
    if race_date < today:
        return {'status': 'past', 'summary': 'Race date has passed; no future-weather estimate applied.'}
    kind = 'forecast' if (race_date - today).days <= 7 else 'seasonal'
    key = hashlib.sha256(json.dumps([location, goal['race_date'], goal['start_time'], goal['goal_minutes'], kind, today.isoformat()], sort_keys=True).encode()).hexdigest()
    init_db()
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS race_weather_cache (cache_key TEXT PRIMARY KEY, result_json TEXT NOT NULL, expires_at REAL NOT NULL)')
        cached = c.execute('SELECT result_json FROM race_weather_cache WHERE cache_key=? AND expires_at>?', (key, time.time())).fetchone()
    if cached:
        return json.loads(cached[0])
    hours = (int(goal['start_time'][:2]), min(24, max(1, math.ceil(goal['goal_minutes']/60)+1)))
    windows = []
    if kind == 'forecast':
        windows.append(('https://api.open-meteo.com/v1/forecast', race_date, race_date + timedelta(days=1)))
    else:
        for year in range(today.year-3, today.year):
            anchor = date(year, race_date.month, min(race_date.day, 28) if race_date.month == 2 else race_date.day)
            windows.append(('https://archive-api.open-meteo.com/v1/archive', anchor-timedelta(days=3), anchor+timedelta(days=3)))
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            groups = list(pool.map(lambda window: _fetch(location, window, hours), windows))
        rows = [row for group in groups for row in group]
        values = {f: round(median(r[f] for r in rows), 1) for f in FIELDS}
        result = {'status': 'available', 'kind': kind, 'location': location['name'],
                  'values': values, 'samples': len(rows), 'source': 'Open-Meteo',
                  'source_url': 'https://open-meteo.com/', 'retrieved_at': datetime.now().isoformat(),
                  'years': [] if kind == 'forecast' else list(range(today.year-3, today.year)),
                  'summary': ('Race-period forecast' if kind == 'forecast' else 'Historical seasonal conditions, not a race-day forecast') + f" · {values['temperature_2m']}°C · humidity {values['relative_humidity_2m']}%",
                  'method': 'Median conditions across race hours. Seasonal samples use the same calendar week in three previous years; this is a small historical sample, not a climate normal.'}
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        result = {'status': 'unavailable', 'summary': 'Weather unavailable. Estimate currently excludes weather.'}
    with connect() as c:
        c.execute('DELETE FROM race_weather_cache WHERE expires_at<?', (time.time(),))
        c.execute('INSERT OR REPLACE INTO race_weather_cache VALUES(?,?,?)', (key, json.dumps(result), time.time()+(21600 if result['status']=='available' else 300)))
    return result


def weather_range(estimate, weather):
    """Broaden uncertainty only: anchor races have no reliable weather normalization."""
    base = [round(estimate*.93), round(estimate*1.10)]
    if weather.get('status') != 'available':
        return base, 'No weather adjustment available.'
    feels = weather['values']['apparent_temperature']
    allowance = min(.08, max(0, feels-20)*.004)
    return [base[0], round(estimate*(1.10+allowance))], (
        f'Weather adds up to {allowance*100:.1f}% to the slower end of the planning range. '
        'This is an experimental uncertainty allowance (0.4% per feels-like degree above 20°C, capped at 8%), not a validated time penalty. '
        'The central estimate stays unchanged because conditions at the reference races are unknown. Course, acclimation and individual heat response remain uncertain.')
