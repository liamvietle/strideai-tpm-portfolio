"""Athlete-scoped coaching questions with bounded retrieval and no plan-writing capability."""
import hashlib
import json
import re
import time
from datetime import date, timedelta

from fastapi import HTTPException
from pydantic import Field, field_validator

from app import athlete_store as store
from app.athlete_models import StrictModel
from app.coach_briefing import reason
from app.coach_knowledge import retrieve
from app.storage import connect

VERSION='coach-questions-1'
SUGGESTIONS=["Am I improving over the last six weeks?", "Why do some sessions feel unusually difficult?",
             "How realistic is my race goal?", "What should I focus on next week?"]


class Question(StrictModel):
    question: str = Field(min_length=5,max_length=1200)
    workout_id: int | None = Field(None,gt=0)
    parent_id: int | None = Field(None,gt=0)

    @field_validator('question')
    @classmethod
    def clean(cls,value):
        value=value.strip()
        if len(value)<5: raise ValueError('Ask a question of at least five characters.')
        return value


def init_db():
    store.init_athlete_db()
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS coach_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, athlete_id TEXT NOT NULL,
            question TEXT NOT NULL, workout_id INTEGER, parent_id INTEGER,
            fingerprint TEXT NOT NULL, created_at REAL NOT NULL, result_json TEXT)''')
        c.execute('CREATE INDEX IF NOT EXISTS coach_questions_owner ON coach_questions(athlete_id,created_at)')


def previous(parent,athlete):
    messages=[]
    with connect() as c:
        for _ in range(4):
            if not parent: break
            row=c.execute('SELECT * FROM coach_questions WHERE id=? AND athlete_id=?',(parent,athlete)).fetchone()
            if not row: raise HTTPException(404,'Coach conversation not found.')
            result=json.loads(row['result_json']) if row['result_json'] else None
            if not result: raise HTTPException(409,'Wait for the previous answer before following up.')
            messages.append({'question':row['question'],'answer':result['briefing'],'answered_at':row['created_at']})
            parent=row['parent_id']
    return list(reversed(messages))


def build_context(payload,athlete):
    today=store.today(athlete);profile=store.profile(athlete)
    past=previous(payload.parent_id,athlete)
    obs=[o for o in store.observations(athlete) if (today-timedelta(days=180)).isoformat()<=o['date']<=today.isoformat()]
    runs=[r for r in store.runs(athlete) if (today-timedelta(days=180)).isoformat()<=r['date']<=today.isoformat()]
    runmap={r['id']:r for r in runs}
    with connect() as c:
        selected=store.workout(c,payload.workout_id,athlete) if payload.workout_id else None
        if selected:
            row=c.execute('SELECT execution_json FROM coach_executions WHERE workout_id=? AND athlete_id=?',(selected['id'],athlete)).fetchone()
            selected['execution_json']=row[0] if row else None
        upcoming=[{'date':r['date'],'workout':json.loads(r['current_json'])} for r in c.execute(
            'SELECT date,current_json FROM coach_workouts WHERE athlete_id=? AND active=1 AND date>=? ORDER BY date LIMIT 7',(athlete,today.isoformat()))]
        checks=[dict(r) for r in c.execute('SELECT checkin_date,sleep_hours,resting_hr_bpm,hrv_ms,pain_flag,soreness_0_10,subjective_fatigue FROM daily_checkins WHERE athlete_id=? AND checkin_date BETWEEN ? AND ? ORDER BY checkin_date DESC LIMIT 14',
                    (athlete,(today-timedelta(days=28)).isoformat(),today.isoformat()))]
    terms=set(re.findall(r'[a-z]+',payload.question.lower()))-{'the','a','i','my','is','what','do','to','and','of','it','why','for','can','feel'}
    target_kind=(json.loads(selected['current_json']).get('kind') if selected else None)
    def score(o):
        text=json.dumps({'kind':o['workout'].get('kind'),'quality':o['evaluation'].get('quality'),'notes':o['execution'].get('notes')}).lower()
        matches=len(terms & set(re.findall(r'[a-z]+',text)))
        return (10 if target_kind and o['workout'].get('kind')==target_kind else 0)+matches*3+max(0,1-(today-date.fromisoformat(o['date'])).days/180)
    ranked=sorted(obs,key=score,reverse=True)[:10]
    from app.strava_details import split_metrics
    evidence={'question':{'text':payload.question,'as_of':today.isoformat()},
              'conversation':{'messages':past,'limit':'Previous answers are context, not verified facts. New athlete statements are self-reported.'},
              'profile':profile.model_dump(mode='json',exclude={'gender','sex','height_cm','weight_kg','health_history','injury_history','constraints'}),
              'recent_checkins':checks,'next_sessions':upcoming}
    if selected:
        execution=json.loads(selected['execution_json']) if selected.get('execution_json') else None
        evidence['selected_workout']={'id':selected['id'],'date':selected['date'],'planned':json.loads(selected['current_json']),
                                      'execution':execution}
        if execution:
            from app.strava_details import apply_details
            if execution.get('activity_id') in runmap: execution=apply_details(execution,runmap[execution['activity_id']])
            evidence['selected_workout']['execution']=execution
            evidence['selected_workout']['split_analysis']=split_metrics(execution.get('splits') or [],target_kind,profile.max_hr,profile.threshold_hr)
    for o in ranked:
        x=o['execution']; key='session_'+str(o.get('workout_id') or len(evidence))
        evidence[key]={'date':o['date'],'workout':o['workout'],
                       'actual':{k:x.get(k) for k in ('distance_km','duration_seconds','average_hr','effort','completed','pain','shortened_reason','notes')},
                       'recommendation':o.get('prediction'),'choice':o.get('choice'),
                       'outcome':{k:o['evaluation'].get(k) for k in ('quality','comparison','expected','recovery_response')},
                       'split_analysis':split_metrics(x.get('splits') or [],o['workout']['kind'],profile.max_hr,profile.threshold_hr)}
    # Include unlinked synced history, not only sessions evaluated through the app.
    linked={o['execution'].get('activity_id') for o in ranked}
    evidence['recent_synced_runs']=[{k:r.get(k) for k in ('id','date','distance_km','duration_seconds','pace','average_hr','effort','weather','elevation_gain_m')} for r in runs if r['id'] not in linked][-10:]
    from app.race_prediction import training_observations,training_progress,training_support
    recent=[o for o in training_observations(runs,obs,profile.max_hr) if o['date']>=(today-timedelta(days=42)).isoformat()]
    evidence['training_trend']=training_progress(recent,profile.active_injury,profile.max_hr)
    evidence['training_volume']=training_support(runs,today,0)
    if any(word in payload.question.lower() for word in ('race','marathon','goal','weather','predict')):
        from app.race_prediction import race_prediction
        forecast=race_prediction(athlete)
        evidence['race_outlook']={k:v for k,v in forecast.items() if k!='history'}
    evidence.update(retrieve(payload.question))
    evidence['retrieval_limits']={'window_days':180,'evaluated_sessions_available':len(obs),'retrieved_sessions':len(ranked),
                                  'method':'Session type and question-word matching, with recency preference; selected session is always included.',
                                  'caution':'Missing records do not prove missed training. Associations do not establish causes. Historical advice is not current permission. Unknown conditions limit trend interpretation.'}
    # Code-owned restrictions remain authoritative, irrespective of what the question requests.
    pain=profile.active_injury or any(c['pain_flag'] for c in checks if c['checkin_date']>= (today-timedelta(days=2)).isoformat())
    restricted=any(o['evaluation'].get('recovery_response',{}).get('action') in ('pause','ease_next') for o in obs if o['date']>=(today-timedelta(days=3)).isoformat())
    pain = pain or bool(((evidence.get('selected_workout') or {}).get('execution') or {}).get('pain'))
    actions={'checkin':'Use your next daily check-in to reassess recovery before changing a session.',
             'review':'Review the evidence below and keep the current plan while you assess the pattern.'}
    if restricted: actions={'checkin':'Reassess at your next check-in and follow the recovery restrictions already in your plan.'}
    if pain: actions={'pause':'Pause running and have the pain or injury concern assessed before resuming.'}
    q=payload.question.lower()
    if any(term in q for term in ('chest pain','faint','passed out','shortness of breath at rest')):
        actions={'urgent':'Stop exercise. If these symptoms are happening now, seek urgent medical help.'}
    evidence['safety']={'restricted':pain or restricted or 'urgent' in actions,'allowed_next_steps':actions,
                        'rule':'No diagnoses, prescriptions, or automatic plan edits. Do not encourage training through pain or override the current recovery plan.'}
    return evidence,actions


def answer(payload,athlete):
    init_db()
    evidence,actions=build_context(payload,athlete)
    fingerprint=hashlib.sha256(json.dumps([VERSION,evidence,actions],sort_keys=True,default=str).encode()).hexdigest()
    now=time.time()
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM coach_questions WHERE athlete_id=? AND created_at<?',(athlete,now-90*86400))
        cached=c.execute('SELECT * FROM coach_questions WHERE athlete_id=? AND fingerprint=? AND created_at>? ORDER BY id DESC LIMIT 1',(athlete,fingerprint,now-3600)).fetchone()
        if cached and cached['result_json']:
            cached_result=json.loads(cached['result_json'])
            if not cached_result['ai_trace']['fallback'] or now-cached['created_at']<60:
                return {**cached_result,'id':cached['id']}
        if cached and now-cached['created_at']<90: return {'status':'pending','id':cached['id']}
        count,last=c.execute('SELECT COUNT(*),MAX(created_at) FROM coach_questions WHERE athlete_id=? AND created_at>?',(athlete,now-86400)).fetchone()
        if count>=20: raise HTTPException(429,'You have reached today’s 20-question limit. Try again tomorrow.')
        if last and now-last<15: raise HTTPException(429,'Please wait a few seconds before asking another question.')
        row=c.execute('INSERT INTO coach_questions(athlete_id,question,workout_id,parent_id,fingerprint,created_at) VALUES(?,?,?,?,?,?)',
                      (athlete,payload.question,payload.workout_id,payload.parent_id,fingerprint,now))
        qid=row.lastrowid
    generated,trace=reason(evidence,actions,'ask')
    if generated is None:
        trend=evidence['training_trend']
        generated={'message':{'text':'AI coaching is unavailable right now. I cannot give a personalised answer to this question yet.','evidence_ids':['question']},
                   'historical_context':{'text':trend['reason'],'evidence_ids':['training_trend']},
                   'learning':{'text':'Review the available records below. Missing data and a single difficult session cannot establish the cause of a performance change.','evidence_ids':['retrieval_limits']},
                   'next_step_id':next(iter(actions)),'uncertainty':'This is a data summary, not an AI answer. You can ask again after one minute.'}
    result={'status':'ready','question':payload.question,'created_at':store.now(),'briefing':generated,
            'next_step':actions[generated['next_step_id']],'ai_trace':trace,'evidence':evidence,'plan_changed':False,
            'safety_notice':next(iter(actions.values())) if evidence['safety']['restricted'] else None}
    with connect() as c: c.execute('UPDATE coach_questions SET result_json=? WHERE id=? AND athlete_id=?',(json.dumps(result),qid,athlete))
    return {**result,'id':qid}


def history(athlete):
    init_db()
    with connect() as c:
        return [{'id':r['id'],'question':r['question'],'created_at':r['created_at']} for r in c.execute('SELECT id,question,created_at FROM coach_questions WHERE athlete_id=? AND created_at>? AND result_json IS NOT NULL ORDER BY id DESC LIMIT 10',(athlete,time.time()-90*86400))]


def get_answer(qid,athlete):
    init_db()
    with connect() as c: row=c.execute('SELECT * FROM coach_questions WHERE id=? AND athlete_id=?',(qid,athlete)).fetchone()
    if not row: raise HTTPException(404,'Coach answer not found.')
    if not row['result_json']:
        if time.time()-row['created_at']>90: raise HTTPException(409,'This answer did not finish. Submit your question again.')
        return {'status':'pending','id':qid}
    return {**json.loads(row['result_json']),'id':qid}
