"""Retrospective notes and explicit, isolated coach-provider diagnostics."""
import json
import time
from typing import Literal

from fastapi import HTTPException
from pydantic import Field
from app import athlete_store as store
from app.athlete_models import StrictModel
from app.storage import connect
from app.coach_reasoning import choose


class LateCheckin(StrictModel):
    feeling: Literal['good', 'normal', 'tired', 'very_tired', 'sore', 'very_sore']
    sleep_hours: float | None = Field(None, ge=0, le=24)
    pain_before: bool | None = None
    notes: str = Field('', max_length=2000)


def init():
    store.init_athlete_db()
    with connect() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS coach_late_checkins(
            workout_id INTEGER PRIMARY KEY, athlete_id TEXT NOT NULL,
            payload_json TEXT NOT NULL, recorded_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS coach_ai_tests(
            athlete_id TEXT PRIMARY KEY, attempted_at REAL NOT NULL, result_json TEXT);''')


def read(wid, athlete):
    init()
    with connect() as c:
        store.workout(c, wid, athlete)
        row=c.execute('SELECT payload_json,recorded_at FROM coach_late_checkins WHERE workout_id=? AND athlete_id=?',(wid,athlete)).fetchone()
    return {'checkin':json.loads(row[0]) if row else None,'recorded_at':row[1] if row else None,'timing':'retrospective'}


def save(wid, payload, athlete):
    init()
    with connect() as c:
        w=store.workout(c,wid,athlete)
        executed=c.execute('SELECT 1 FROM coach_executions WHERE workout_id=?',(wid,)).fetchone()
    if w['date']>store.today(athlete).isoformat() or not (executed or any(r['date']==w['date'] for r in store.runs(athlete))):
        raise HTTPException(409,'Sync or record the run before adding a late check-in.')
    with connect() as c:
        c.execute('INSERT INTO coach_late_checkins VALUES(?,?,?,?) ON CONFLICT(workout_id) DO UPDATE SET payload_json=excluded.payload_json,recorded_at=excluded.recorded_at',
                  (wid,athlete,payload.model_dump_json(),store.now()))
    return read(wid,athlete)


def test_connection(athlete):
    init()
    now=time.time()
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        previous=c.execute('SELECT attempted_at FROM coach_ai_tests WHERE athlete_id=?',(athlete,)).fetchone()
        if previous and now-previous[0]<60:
            raise HTTPException(429,'Wait one minute before testing again.')
        c.execute('INSERT INTO coach_ai_tests VALUES(?,?,NULL) ON CONFLICT(athlete_id) DO UPDATE SET attempted_at=excluded.attempted_at,result_json=NULL',(athlete,now))
    # The actual coach request/validation path, with synthetic data only.
    _, trace=choose({'connection_test':{'purpose':'Synthetic connectivity test; not an athlete workout.'}},
                   {'test_ok':{'purpose':'Confirm provider connection; no training action.'}},'test_ok')
    result={'success':not trace['fallback'],'tested_at':store.now(),
            'model':trace.get('model'),'reason':trace.get('reason'),
            'latency_ms':trace.get('latency_ms'), 'scope':'Connection test only; not a workout prediction.'}
    with connect() as c:
        c.execute('UPDATE coach_ai_tests SET result_json=? WHERE athlete_id=?',(json.dumps(result),athlete))
    return result
