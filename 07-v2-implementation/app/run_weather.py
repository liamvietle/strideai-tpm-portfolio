"""Forecast guidance is separate from the unchanged recovery score."""
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import BaseModel, Field, field_validator

from app.activity_weather import FIELDS, number


class RunWeatherInput(BaseModel):
    indoor: bool = False
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    start: datetime
    location: str = Field(default='', max_length=160)

    @field_validator('start')
    @classmethod
    def aware_start(cls, value):
        if value.tzinfo is None:
            raise ValueError('Run start must include a time zone.')
        return value


def find_places(name):
    response = httpx.get('https://geocoding-api.open-meteo.com/v1/search', params={'name': name, 'count': 5, 'language': 'en', 'format': 'json'}, timeout=4)
    response.raise_for_status()
    return [{'name': ', '.join(str(r[k]) for k in ('name', 'admin1', 'country') if r.get(k)),
             'latitude': r['latitude'], 'longitude': r['longitude']}
            for r in response.json().get('results', [])]


def forecast_guidance(request: RunWeatherInput | None):
    if request is None:
        return {'status': 'not_requested', 'guidance': 'Weather not assessed. Select the next run location and start time to include it.'}
    if request.indoor:
        return {'status': 'indoor', 'guidance': 'Outdoor weather guidance does not apply to this indoor run.'}
    now = datetime.now(timezone.utc)
    start = request.start.astimezone(timezone.utc)
    if not now - timedelta(hours=1) <= start <= now + timedelta(days=7):
        return {'status': 'outside_window', 'guidance': 'Choose an upcoming start within 7 days. Past-run weather cannot stand in for the next run forecast.'}
    try:
        response = httpx.get('https://api.open-meteo.com/v1/forecast', params={
            'latitude': request.latitude, 'longitude': request.longitude,
            'start_date': start.date().isoformat(), 'end_date': start.date().isoformat(),
            'hourly': ','.join(FIELDS.values()), 'timezone': 'GMT', 'timeformat': 'unixtime',
            'temperature_unit': 'celsius', 'wind_speed_unit': 'kmh', 'precipitation_unit': 'mm',
        }, timeout=4)
        response.raise_for_status()
        hourly = response.json()['hourly']
        index = hourly['time'].index(int(start.replace(minute=0, second=0, microsecond=0).timestamp()))
        values = {key: number(hourly[field][index]) for key, field in FIELDS.items()}
        feels = values['feels_like_c']
        if feels is None:
            raise ValueError('Missing apparent temperature')
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return {'status': 'unavailable', 'guidance': 'Forecast unavailable. No weather adjustment applied; check local conditions before running.'}
    # Product heuristics, not WBGT categories or validated physiological cutoffs.
    if feels >= 38:
        action = 'reschedule_or_indoor'
        guidance = 'Move the run to a cooler time or indoors. Recheck conditions before deciding on an outdoor session.'
    elif feels >= 30:
        action = 'easy_effort'
        guidance = 'Use easy effort instead of chasing planned pace. Move quality work to a cooler time or indoors, and shorten the run if effort rises.'
    else:
        action = 'no_heat_adjustment'
        guidance = 'No heat adjustment triggered. Follow the recovery recommendation and reassess conditions during the run.'
    return {'status': 'available', 'action': action, 'guidance': guidance,
            'values': values, 'location': request.location, 'start': request.start.isoformat(),
            'retrieved_at': now.isoformat(), 'source': 'Open-Meteo',
            'limitation': '30°C and 38°C feels-like triggers are provisional app rules, not validated safety limits. Apparent temperature is not WBGT. This is not an all-weather safety assessment; sun exposure, acclimation and local warnings still matter.'}
