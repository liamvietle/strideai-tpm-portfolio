"""Resumable setup and activation of user-authored plans."""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app import athlete_store as store
from app.storage import connect
from app.training_plan import get_goal, plan_progress

router = APIRouter(prefix='/app/api/journey')

class SetupState(BaseModel):
    step: int = Field(0, ge=0, le=2)
    finished: bool = False


def init_journey():
    store.init_athlete_db()
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS athlete_setup (athlete_id TEXT PRIMARY KEY, step INTEGER NOT NULL DEFAULT 0, finished INTEGER NOT NULL DEFAULT 0)')


@router.get('')
def status(athlete_id: str = 'viet'):
    init_journey()
    goal = get_goal(athlete_id)
    with connect() as c:
        state = c.execute('SELECT * FROM athlete_setup WHERE athlete_id=?', (athlete_id,)).fetchone()
        returning = c.execute('SELECT 1 FROM daily_checkins WHERE athlete_id=? LIMIT 1', (athlete_id,)).fetchone()
        plan = c.execute('SELECT 1 FROM training_plans WHERE athlete_id=? AND race_id=? LIMIT 1', (athlete_id, goal['id'] if goal else -1)).fetchone()
    return {'step': state['step'] if state else 0,
            'finished': bool(state['finished']) if state else bool(returning or plan),
            'has_plan': bool(plan)}


@router.put('')
def save_status(payload: SetupState, athlete_id: str = 'viet'):
    init_journey()
    with connect() as c:
        c.execute('INSERT INTO athlete_setup VALUES(?,?,?) ON CONFLICT(athlete_id) DO UPDATE SET step=excluded.step, finished=excluded.finished',
                  (athlete_id, payload.step, int(payload.finished)))
    return status(athlete_id)


@router.post('/activate-import')
def activate_import(athlete_id: str = 'viet'):
    """Bring a reviewed snapshot into coaching without guessing workout intensity."""
    init_journey()
    progress = plan_progress(athlete_id)
    if not progress.get('days'):
        raise HTTPException(409, 'Import your plan first.')
    today = store.today(athlete_id).isoformat()
    days = [d for d in progress['days'] if d['date'] >= today]
    if not days:
        raise HTTPException(409, 'Your plan needs at least one session today or later.')
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        # Avoid silently overwriting another plan or saved expectations.
        if c.execute('SELECT 1 FROM coach_workouts WHERE athlete_id=? AND active=1 AND date>=? LIMIT 1', (athlete_id, today)).fetchone():
            raise HTTPException(409, 'A coaching plan already exists. Your imported snapshot is saved, but has not replaced your coaching plan.')
        for d in days:
            # Non-running sessions remain in the imported calendar and daily check-in.
            if d['activity'] != 'run':
                continue
            w = {'date': d['date'], 'kind': 'custom', 'phase': 'athlete_plan',
                 'purpose': d['note'] or 'Your planned run', 'key_session': False,
                 'distance_km': d['distance_km'], 'duration_minutes': round(d['distance_km']*8, 1),
                 'pace_target': None, 'hr_target': None, 'rpe_target': None,
                 'pace_basis': 'Imported plan: intensity and duration not specified', 'pace_samples': 0,
                 'instructions': 'Follow your original session instructions. Confirm intensity in your daily check-in. Duration shown is a provisional estimate at 8 min/km.',
                 'source': 'imported'}
            c.execute('INSERT INTO coach_workouts(athlete_id,race_id,date,original_json,current_json) VALUES(?,?,?,?,?)',
                      (athlete_id, progress['goal']['id'], d['date'], json.dumps(w), json.dumps(w)))
    return {'activated': sum(d['activity']=='run' for d in days)}
