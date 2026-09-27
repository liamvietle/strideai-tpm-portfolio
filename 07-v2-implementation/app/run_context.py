"""Optional post-run context; original execution, evaluation and plan decisions are preserved."""
import json
from typing import Literal
from fastapi import HTTPException
from pydantic import Field
from app.athlete_models import StrictModel
from app import athlete_store as store
from app.storage import connect


class RunContext(StrictModel):
    reason: Literal['felt_fresh','pushed_harder','route_or_company','other','unspecified']='unspecified'
    notes: str = Field('',max_length=1000)


def init_db():
    store.init_athlete_db()
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS coach_run_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT, athlete_id TEXT NOT NULL, workout_id INTEGER NOT NULL,
            context_json TEXT NOT NULL, created_at TEXT NOT NULL)''')
        c.execute('CREATE INDEX IF NOT EXISTS run_context_owner ON coach_run_context(athlete_id,workout_id,id)')


def read(wid,athlete):
    init_db()
    with connect() as c:
        row=c.execute('SELECT context_json,created_at FROM coach_run_context WHERE workout_id=? AND athlete_id=? ORDER BY id DESC LIMIT 1',(wid,athlete)).fetchone()
    return {**json.loads(row[0]),'recorded_at':row[1],'source':'athlete_report_after_run'} if row else None


def save(wid,payload,athlete):
    init_db()
    with connect() as c:
        store.workout(c,wid,athlete)
        if not c.execute('SELECT 1 FROM coach_executions WHERE workout_id=? AND athlete_id=?',(wid,athlete)).fetchone():
            raise HTTPException(409,'Record or sync the run first.')
        c.execute('INSERT INTO coach_run_context(athlete_id,workout_id,context_json,created_at) VALUES(?,?,?,?)',
                  (athlete,wid,payload.model_dump_json(),store.now()))
    return {'saved':True,'plan_changed':False}


def assess(workout):
    x=workout.get('execution') or {};e=workout.get('evaluation') or {}
    target=x.get('target_snapshot') or workout.get('execution_target') or workout['original']
    planned=target.get('distance_km') or 0;actual=x.get('distance_km') or 0
    # Ignore normal GPS/distance rounding; compare against the actual saved execution target.
    if planned<=0 or actual-planned<max(.2,planned*.05): return None
    context=workout.get('run_context') or {};reason=context.get('reason','unspecified')
    response=e.get('recovery_response') or {}
    concern=x.get('pain') or response.get('action') in ('pause','ease_next') or bool(response.get('evidence'))
    hr=next((m for m in workout.get('comparison_metrics',[]) if m['metric']=='HR'),{})
    pace=next((m for m in workout.get('comparison_metrics',[]) if m['metric']=='Pace'),{})
    pace_matched=pace.get('expected') and pace.get('difference') is not None and abs(pace['difference'])<=pace['expected']*.10
    normal_hr=hr.get('difference') is not None and abs(hr['difference'])<=5
    from app.strava_details import split_metrics
    splits=split_metrics(x.get('splits') or [],target['kind'])
    drift=splits['hr_drift_pct']
    if drift is not None and drift>7: concern=True
    if concern:
        signal='recovery_concern';text='You ran farther, but the recorded recovery signals need attention. Feeling fresh does not cancel those signals.'
    elif reason=='pushed_harder':
        signal='extra_effort';text='You reported pushing harder than intended. Treat the extra distance as additional load, not proof of improved fitness. Check how you recover before the next session.'
    elif reason=='felt_fresh' and normal_hr and pace_matched and x.get('completed'):
        signal='positive_tolerance';text='You felt fresh and handled extra distance with pace and HR close to the available expectations. This is a positive observation of session tolerance, not yet proof of better fitness or complete recovery.'
    elif reason=='felt_fresh':
        signal='self_reported_capacity';text='You felt fresh and ran farther. The available physiological comparison is not strong enough to confirm improved capacity yet.'
    else:
        signal='extra_distance';text='You ran farther than the saved target. Your reason and recovery afterwards help explain whether this was comfortable extra work or a harder session.'
    return {'signal':signal,'extra_km':round(actual-planned,2),'planned_km':planned,'actual_km':actual,'reason':reason,
            'summary':text,'hr_comparison_basis':hr.get('basis'),'hr_difference':hr.get('difference'),
            'limitation':'Repeated comparable outcomes and subsequent recovery are needed before changing the athlete model or increasing the plan. Missing splits do not establish normal drift.',
            'plan_changed':False}
