"""Athlete-requested edits preserve original targets and require a current preview."""
import hashlib
import json
from datetime import date, timedelta
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app import athlete_store as store
from app.athlete_coach import change, cut
from app.storage import connect
from app.training_plan import get_goal


class SessionChange(BaseModel):
    action: Literal['skip', 'swap', 'distance']
    reason: Literal['availability', 'fatigue', 'feeling_good', 'other']
    note: str = Field(default='', max_length=300)
    distance_km: float | None = Field(default=None, gt=0, le=100, allow_inf_nan=False)
    swap_date: date | None = None
    confirm_token: str | None = None


def edit_session(wid, payload, athlete='viet'):
    store.init_athlete_db()
    today = store.today(athlete)
    profile = store.profile(athlete)
    goal = get_goal(athlete)
    run_days = {r['date'] for r in store.runs(athlete)}
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        all_rows = [dict(r) for r in c.execute('SELECT * FROM coach_workouts WHERE athlete_id=? AND active=1 ORDER BY date', (athlete,))]
        rows = {r['id']: r for r in all_rows}
        row = rows.get(wid)
        if not row:
            raise HTTPException(404, 'Active workout not found.')
        selected = [row]
        if payload.action == 'swap':
            other = next((r for r in all_rows if payload.swap_date and r['date']==payload.swap_date.isoformat()), None)
            if not other or other['id']==wid:
                raise HTTPException(422, 'Choose a different planned day to swap with.')
            selected.append(other)
        for r in selected:
            if r['date'] < today.isoformat() or r['state'] != 'planned' or r['date'] in run_days:
                raise HTTPException(409, 'Only unstarted sessions without locked predictions can be changed. For a completed run, record the actual result instead.')
            if not goal or r['race_id'] != goal['id'] or r['date']==goal['race_date']:
                raise HTTPException(409, 'Race-day sessions cannot be rescheduled here.')
        originals = {r['id']:json.loads(r['current_json']) for r in selected}
        w = originals[wid]
        if w['distance_km'] <= 0 and payload.action != 'swap':
            raise HTTPException(422, 'Choose a running session. Rest days can be swapped with a planned run.')
        if any(v['kind']=='race' for v in originals.values()):
            raise HTTPException(409, 'Race-day sessions cannot be changed here.')
        if payload.action == 'distance':
            if payload.distance_km is None:
                raise HTTPException(422, 'Enter a new distance.')
            updated = {wid:cut(w,payload.distance_km/w['distance_km'])}
            updated[wid]['purpose'] = 'Your planned run, with revised distance'
        elif payload.action == 'skip':
            updated = {wid:cut(w,0)}
            updated[wid]['purpose']='Run skipped by athlete'
        else:
            other=selected[1]
            # Swap running prescriptions; strength remains on the chosen strength weekday.
            updated={wid:dict(originals[other['id']]),other['id']:dict(w)}
            for r in selected:
                for key in ('strength_session','strength_minutes','strength_instructions','phase'):
                    updated[r['id']].pop(key,None)
                    if key in originals[r['id']]: updated[r['id']][key]=originals[r['id']][key]
        warnings=[]
        check=c.execute('SELECT * FROM daily_checkins WHERE athlete_id=? AND checkin_date=?',(athlete,today.isoformat())).fetchone()
        unsafe=profile.active_injury or bool(check and (check['pain_flag'] or (check['soreness_0_10'] or 0)>=8))
        increases=any(updated[r['id']]['distance_km']>originals[r['id']]['distance_km'] for r in selected)
        if unsafe and any(v['distance_km']>0 for v in updated.values()):
            raise HTTPException(409, 'Pain or injury concerns are active. Skip the run and reassess before scheduling running.')
        if increases and payload.reason=='fatigue':
            raise HTTPException(409, 'For fatigue, reduce or skip rather than move extra distance to another day. Reassess recovery before rescheduling.')
        if increases:
            warnings.append('This is your requested schedule change, not a recommendation to increase training. Check readiness again before running.')
        if payload.action=='skip': warnings.append('Skipped distance is not automatically added to another day.')
        if payload.reason=='fatigue': warnings.append('No make-up mileage is scheduled. Reassess your next session with a fresh check-in.')
        for r in selected:
            new=updated[r['id']]
            new['date']=r['date']
            new['athlete_change']={'action':payload.action,'reason':payload.reason,'note':payload.note,'previous_purpose':originals[r['id']]['purpose'],'changed_at':store.now()}
            if payload.action=='distance' and new.get('segments'):
                raise HTTPException(409,'This session has structured intervals. Swap the complete session or record the actual distance afterward; editing its interval structure is not supported yet.')
            duration=new.get('duration_minutes',0)+new.get('strength_minutes',0)
            if duration>profile.max_session_minutes: warnings.append(f"{r['date']}: estimated session time exceeds your saved availability.")
            if new['distance_km']>originals[r['id']]['distance_km']*1.3 and payload.action=='distance':
                warnings.append('The distance increase is over 30%. Feeling good alone does not establish tolerance for this increase.')
        revised={r['date']:updated.get(r['id'],json.loads(r['current_json'])) for r in all_rows}
        for r in selected:
            new=updated[r['id']]
            if new.get('key_session') or new.get('kind') in ('long','threshold') or new['distance_km']>=16:
                for offset in (-1,1):
                    neighbor=revised.get((date.fromisoformat(r['date'])+timedelta(days=offset)).isoformat(),{})
                    if neighbor.get('key_session') or neighbor.get('kind') in ('long','threshold') or neighbor.get('distance_km',0)>=16:
                        warnings.append(f"{r['date']}: demanding sessions would be on consecutive days. Consider more recovery between them.")
        weeks=[]
        for monday in sorted({date.fromisoformat(r['date'])-timedelta(days=date.fromisoformat(r['date']).weekday()) for r in selected}):
            end=monday+timedelta(days=6)
            week_rows=[r for r in all_rows if monday.isoformat()<=r['date']<=end.isoformat()]
            weeks.append({'week':monday.isoformat(),'before_km':round(sum(json.loads(r['current_json'])['distance_km'] for r in week_rows),2),'after_km':round(sum(revised[r['date']]['distance_km'] for r in week_rows),2)})
        # Includes neighboring workouts, health and profile so stale previews cannot overwrite changes.
        digest=[[(r['id'],r['state'],r['current_json']) for r in all_rows],payload.model_dump(mode='json',exclude={'confirm_token'}),profile.model_dump(mode='json'),dict(check) if check else None]
        token=hashlib.sha256(json.dumps(digest,sort_keys=True).encode()).hexdigest()
        response={'changes':[{'date':r['date'],'before_km':originals[r['id']]['distance_km'],'after_km':updated[r['id']]['distance_km'],'purpose':updated[r['id']]['purpose']} for r in selected], 'weeks':weeks,'warnings':list(dict.fromkeys(warnings)),'confirm_token':token,'saved':False}
        if payload.confirm_token:
            if payload.confirm_token!=token: raise HTTPException(409,'Your plan or recovery data changed. Preview the change again.')
            for r in selected:
                change(c,r,updated[r['id']],f"Athlete {payload.action} ({payload.reason}): {payload.note}".strip(),wid)
            # Keep imported-calendar fallback aligned; retain all previous snapshots.
            snap=c.execute('SELECT plan_json FROM training_plans WHERE athlete_id=? AND race_id=? ORDER BY id DESC LIMIT 1',(athlete,goal['id'])).fetchone()
            if snap:
                plan=json.loads(snap[0]); by_date={r['date']:updated[r['id']] for r in selected}
                for d in plan['days']:
                    if d['date'] in by_date:
                        new=by_date[d['date']];d.update(distance_km=new['distance_km'],activity='run' if new['distance_km'] else 'other' if new.get('strength_session') else 'rest',note=new['purpose'])
                plan['source']='Athlete session change'
                c.execute('INSERT INTO training_plans(race_id,athlete_id,plan_json) VALUES(?,?,?)',(goal['id'],athlete,json.dumps(plan)))
            response['saved']=True
        return response
