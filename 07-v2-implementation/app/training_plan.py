"""Private race goals, versioned plan snapshots and descriptive progress only."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, time
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from app.activity_weather import raw_activity
from app.personal_history import list_personal_history
from app.storage import connect, init_db


class RaceLocation(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    timezone: str

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (KeyError, ValueError):
            raise ValueError('Choose a valid location time zone.')
        return value


class RaceGoal(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    race_date: date
    distance_km: float = Field(default=42.195, gt=0, le=300, allow_inf_nan=False)
    goal_minutes: float = Field(gt=0, le=10000, allow_inf_nan=False)
    timezone: str = 'Asia/Ho_Chi_Minh'
    new_race: bool = False
    location: RaceLocation | None = None
    start_time: time | None = None

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (KeyError, ValueError):
            raise ValueError('Choose a valid time zone.')
        return value


class PlanDay(BaseModel):
    date: date
    distance_km: float = Field(ge=0, le=300, allow_inf_nan=False)
    activity: Literal['run', 'rest', 'other'] = 'run'
    note: str = Field(default='', max_length=300)

    @model_validator(mode='after')
    def valid_distance(self):
        if self.activity != 'run' and self.distance_km != 0:
            raise ValueError('Only running distance belongs in plan mileage.')
        return self


class PlanImport(BaseModel):
    race_id: int
    source: str = Field(default='Manual plan', max_length=300)
    days: list[PlanDay] = Field(min_length=1, max_length=730)

    @field_validator('days')
    @classmethod
    def unique_dates(cls, days):
        if len({d.date for d in days}) != len(days):
            raise ValueError('Each date must occur once in a plan snapshot.')
        return sorted(days, key=lambda d: d.date)


def init_plan_db():
    init_db()
    with connect() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS race_goals (
            id INTEGER PRIMARY KEY, athlete_id TEXT NOT NULL,
            goal_json TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS training_plans (
            id INTEGER PRIMARY KEY, race_id INTEGER NOT NULL,
            athlete_id TEXT NOT NULL, plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        ''')


def get_goal(athlete_id='viet'):
    init_plan_db()
    with connect() as conn:
        row = conn.execute('SELECT * FROM race_goals WHERE athlete_id=? AND active=1 ORDER BY id DESC LIMIT 1', (athlete_id,)).fetchone()
    return {**json.loads(row['goal_json']), 'id': row['id']} if row else None


def save_goal(goal: RaceGoal, athlete_id='viet'):
    init_plan_db()
    data = goal.model_dump(mode='json', exclude={'new_race'})
    with connect() as conn:
        row = conn.execute('SELECT id FROM race_goals WHERE athlete_id=? AND active=1 ORDER BY id DESC LIMIT 1', (athlete_id,)).fetchone()
        if row and not goal.new_race:
            conn.execute('UPDATE race_goals SET goal_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (json.dumps(data), row['id']))
        else:
            conn.execute('UPDATE race_goals SET active=0 WHERE athlete_id=?', (athlete_id,))
            conn.execute('INSERT INTO race_goals(athlete_id,goal_json) VALUES (?,?)', (athlete_id, json.dumps(data)))
    return get_goal(athlete_id)


def save_plan(plan: PlanImport, athlete_id='viet'):
    goal = get_goal(athlete_id)
    if not goal or goal['id'] != plan.race_id:
        raise HTTPException(409, 'The active race changed. Reload before importing.')
    with connect() as conn:
        cursor = conn.execute('INSERT INTO training_plans(race_id,athlete_id,plan_json) VALUES (?,?,?)', (plan.race_id, athlete_id, plan.model_dump_json()))
    return {'revision': cursor.lastrowid, 'days': len(plan.days)}


def plan_progress(athlete_id='viet', as_of: date | None = None):
    goal = get_goal(athlete_id)
    if not goal:
        return {'goal': None, 'weeks': [], 'days': [], 'review': 'Add your race goal and training plan.'}
    zone = ZoneInfo(goal['timezone'])
    today = as_of or datetime.now(zone).date()
    with connect() as conn:
        plan = conn.execute('SELECT * FROM training_plans WHERE athlete_id=? AND race_id=? ORDER BY id DESC LIMIT 1', (athlete_id, goal['id'])).fetchone()
        activities = [dict(r) for r in conn.execute("SELECT * FROM activities WHERE athlete_id=? AND source='strava' AND lower(activity_type) IN ('run','trailrun','virtualrun')", (athlete_id,))]
    history = {r['checkin_date']: r for r in list_personal_history(athlete_id, limit=365)}
    actual = {}
    for row in activities:
        raw = raw_activity(row)
        try:
            # Strava's local start reflects the activity's location, including travel.
            if raw.get('start_date_local'):
                day = date.fromisoformat(raw['start_date_local'][:10]).isoformat()
            else:
                start = datetime.fromisoformat(row['start_time'].replace('Z', '+00:00'))
                if start.tzinfo is None:
                    continue
                day = start.astimezone(zone).date().isoformat()
        except (ValueError, TypeError):
            continue
        if row['distance_km'] is not None:
            actual[day] = actual.get(day, 0) + row['distance_km']
    days = json.loads(plan['plan_json'])['days'] if plan else []
    weeks = {}
    for day in days:
        d = date.fromisoformat(day['date'])
        h = history.get(day['date'], {})
        rec = h.get('recommendation') or {}
        day['recorded_km'] = round(actual[day['date']], 2) if day['date'] in actual else None
        day['action'] = rec.get('action')
        day['weather_guidance'] = (h.get('run_weather') or {}).get('guidance')
        day['checkin_planned_km'] = h.get('planned_distance_km') if rec else None
        day['recommended_km'] = round(h['planned_distance_km'] * (1 + rec.get('volume_change_pct', 0) / 100), 2) if rec else None
        start = (d - timedelta(days=d.weekday())).isoformat()
        w = weeks.setdefault(start, {'start': start, 'planned_km': 0, 'planned_to_date_km': 0, 'recorded_km': 0, 'unrecorded_run_days': 0, 'reductions': 0, 'longest_planned_km': 0})
        w['planned_km'] += day['distance_km']
        w['longest_planned_km'] = max(w['longest_planned_km'], day['distance_km'])
        if d <= today:
            w['planned_to_date_km'] += day['distance_km']
            w['unrecorded_run_days'] += int(day['activity'] == 'run' and day['distance_km'] > 0 and day['recorded_km'] is None)
            w['reductions'] += int(bool(rec) and rec.get('action') in {'reduce_volume', 'reduce_intensity', 'recovery_only'})
    for start, week in weeks.items():
        end = date.fromisoformat(start) + timedelta(days=6)
        week['recorded_km'] = round(sum(km for d, km in actual.items() if start <= d <= min(end, today).isoformat()), 2)
        for field in ('planned_km', 'planned_to_date_km'):
            week[field] = round(week[field], 2)
    recent = [r for d, r in history.items() if today - timedelta(days=13) <= date.fromisoformat(d) <= today and r.get('recommendation')]
    reductions = sum(r['recommendation']['action'] in {'reduce_volume', 'reduce_intensity', 'recovery_only'} for r in recent)
    review = ('Repeated reductions: review recovery, key sessions and the remaining plan before reassessing the race goal. Do not cram missed mileage.' if reductions >= 3 else 'Track consistency and key sessions. There is not enough evidence here to predict your finish time.')
    return {'goal': goal, 'as_of': today.isoformat(), 'days_to_race': (date.fromisoformat(goal['race_date']) - today).days,
            'goal_pace_seconds_km': round(goal['goal_minutes'] * 60 / goal['distance_km']),
            'revision': plan['id'] if plan else None, 'imported_at': plan['created_at'] if plan else None,
            'source': json.loads(plan['plan_json'])['source'] if plan else None,
            'weeks': list(weeks.values()), 'days': days, 'reductions_14d': reductions, 'decisions_14d': len(recent), 'review': review}
