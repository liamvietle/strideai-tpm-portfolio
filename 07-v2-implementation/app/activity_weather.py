from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from datetime import datetime, timezone

import httpx

from app.storage import connect, init_db

FIELDS = {
    'temperature_c': 'temperature_2m',
    'feels_like_c': 'apparent_temperature',
    'humidity_pct': 'relative_humidity_2m',
    'dew_point_c': 'dew_point_2m',
    'precipitation_mm': 'precipitation',
    'wind_kmh': 'wind_speed_10m',
}
_WORKER_LOCK = threading.Lock()


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def raw_activity(row):
    try:
        raw = json.loads(row.get('raw_payload') or '{}')
        return raw if isinstance(raw, dict) else {}
    except (ValueError, TypeError):
        return {}


def weather_target(raw):
    sport = str(raw.get('sport_type') or raw.get('type') or '').lower()
    if raw.get('trainer') or sport.startswith('virtual') or sport in {
        'weighttraining', 'workout', 'yoga', 'pilates', 'elliptical', 'stairstepper',
    }:
        return 'indoor', None
    coords = raw.get('start_latlng')
    if not isinstance(coords, list) or len(coords) != 2:
        return 'missing_location', None
    lat, lon = map(number, coords)
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return 'missing_location', None
    try:
        # start_date_local looks like UTC in Strava but is a wall-clock time.
        # Never substitute it for the actual UTC start_date.
        start = datetime.fromisoformat(raw['start_date'].replace('Z', '+00:00'))
        if start.tzinfo is None:
            raise ValueError('Timezone required')
        start = start.astimezone(timezone.utc)
        if start > datetime.now(timezone.utc) or start.year < 1940:
            raise ValueError('Outside historical range')
    except (KeyError, AttributeError, TypeError, ValueError):
        return 'missing_time', None
    return 'pending', (lat, lon, start)


def fingerprint(target):
    lat, lon, start = target
    return hashlib.sha256(f'{lat}|{lon}|{start.isoformat()}'.encode()).hexdigest()


def fetch_weather(target):
    lat, lon, start = target
    recent = (datetime.now(timezone.utc).date() - start.date()).days < 7
    url = 'https://api.open-meteo.com/v1/forecast' if recent else 'https://archive-api.open-meteo.com/v1/archive'
    response = httpx.get(url, params={
        'latitude': lat, 'longitude': lon,
        'start_date': start.date().isoformat(), 'end_date': start.date().isoformat(),
        'hourly': ','.join(FIELDS.values()), 'timezone': 'GMT', 'timeformat': 'unixtime',
        'temperature_unit': 'celsius', 'wind_speed_unit': 'kmh', 'precipitation_unit': 'mm',
    }, timeout=4.0)
    response.raise_for_status()
    hourly = response.json()['hourly']
    hour = int(start.replace(minute=0, second=0, microsecond=0).timestamp())
    index = hourly['time'].index(hour)
    values = {key: number((hourly.get(field) or [])[index])
              if len(hourly.get(field) or []) > index else None for key, field in FIELDS.items()}
    if not any(value is not None for value in values.values()):
        raise ValueError('No weather at activity hour')
    return {**values, 'source': 'Open-Meteo', 'dataset': 'recent_model' if recent else 'historical_reanalysis',
            'hour_utc': datetime.fromtimestamp(hour, timezone.utc).isoformat(),
            'retrieved_at': datetime.now(timezone.utc).isoformat()}


def _rows(athlete_id, limit=None):
    query = '''SELECT a.*, w.fingerprint, w.status AS weather_status,
        w.weather_json, w.attempted_at FROM activities a
        LEFT JOIN activity_weather w ON w.activity_id=a.id
        WHERE a.athlete_id=? AND a.source='strava'
        ORDER BY a.start_time DESC, a.id DESC'''
    params = [athlete_id]
    if limit is not None:
        query += ' LIMIT ?'
        params.append(limit)
    with connect() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def enrich_weather(athlete_id='viet', *, max_requests=20):
    """Best-effort background backfill. No network calls while holding SQLite locks.

    Work resumes on the next sync after restarts/budget exhaustion. One worker
    per process avoids overlapping automatic/manual sync requests.
    """
    if not _WORKER_LOCK.acquire(blocking=False):
        return
    try:
        init_db()
        began = time.monotonic()
        requests = 0
        for row in _rows(athlete_id):
            status, target = weather_target(raw_activity(row))
            if target is None:
                continue
            key = fingerprint(target)
            if row['fingerprint'] == key:
                if row['weather_status'] == 'available':
                    continue
                if time.time() - row['attempted_at'] < 6 * 3600:
                    continue
            if requests >= max_requests or time.monotonic() - began >= 20:
                break
            requests += 1
            weather = None
            try:
                weather = fetch_weather(target)
                status = 'available'
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
                status = 'unavailable'
            with connect() as conn:
                conn.execute('''INSERT INTO activity_weather
                    (activity_id, fingerprint, status, weather_json, attempted_at)
                    VALUES (?, ?, ?, ?, ?) ON CONFLICT(activity_id) DO UPDATE SET
                    fingerprint=excluded.fingerprint, status=excluded.status,
                    weather_json=excluded.weather_json, attempted_at=excluded.attempted_at''',
                    (row['id'], key, status, json.dumps(weather) if weather else None, time.time()))
    finally:
        _WORKER_LOCK.release()


def recent_activities(athlete_id='viet', limit=30):
    init_db()
    result = []
    for row in _rows(athlete_id, limit):
        raw = raw_activity(row)
        status, target = weather_target(raw)
        weather = None
        if target is not None and row['fingerprint'] == fingerprint(target):
            status = row['weather_status']
            weather = json.loads(row['weather_json']) if row['weather_json'] else None
        # Explicit allowlist: never expose raw payload, coordinates or tokens.
        item = {key: row[key] for key in ('source_activity_id', 'start_time', 'activity_type',
                'name', 'distance_km', 'duration_seconds', 'average_hr', 'max_hr')}
        item.update(elevation_m=number(raw.get('total_elevation_gain')),
                    cadence_rpm=number(raw.get('average_cadence')),
                    strava_temperature_c=number(raw.get('average_temp')),
                    weather_status=status, weather=weather)
        result.append(item)
    return result
