"""Bounded Strava detail imports and source-aware effort/split normalization."""
import json
import math
import time
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

import httpx

from app.storage import connect


def number(value, low=0, high=1e9):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and low <= value <= high else None


def effort(raw):
    return {'relative': number(raw.get('suffer_score')), 'perceived': number(raw.get('perceived_exertion'),1,10),
            'source':'strava', 'relative_unit':'Relative Effort score', 'perceived_unit':'reported effort /10'}


def valid_splits(splits, km, seconds):
    return bool(splits and len(splits)<=300 and km and seconds and
        abs(sum(s['distance_km'] for s in splits)-km)<=max(.1,km*.03) and
        abs(sum(s['duration_seconds'] for s in splits)-seconds)<=max(10,seconds*.03))


def metric_splits(items):
    result=[]
    if not isinstance(items,list) or len(items)>300: return []
    for row in items:
        if not isinstance(row,dict): return []
        d=number(row.get('distance'),.01,100000)
        t=number(row.get('moving_time'),.01,100000)
        if d is None or t is None: return []
        result.append({'distance_km':d/1000,'duration_seconds':t,'average_hr':number(row.get('average_heartrate'),30,240)})
    return result


def stream_splits(streams, km, seconds):
    """Integrate moving intervals into kilometre bins, retaining partial final km.

    Require aligned full-resolution streams, small gaps and full-run coverage.
    Missing HR stays missing; never copy overall HR into individual splits.
    """
    if not isinstance(streams,dict): return []
    def data(key):
        v=streams.get(key) or {}
        return v.get('data',[]) if isinstance(v,dict) else []
    ts,ds,hrs,moving=[data(k) for k in ('time','distance','heartrate','moving')]
    n=len(ts)
    if n<2 or n>100000 or len(ds)!=n or len(moving)!=n or (hrs and len(hrs)!=n): return []
    if any(number(t) is None for t in ts) or any(number(d) is None for d in ds): return []
    if ts[0]>5 or ds[0]>20 or not km or abs(ds[-1]/1000-km)>max(.1,km*.03): return []
    bins={}
    for i in range(1,n):
        dt,dd=ts[i]-ts[i-1],ds[i]-ds[i-1]
        if dt<=0 or dd<0 or dt>30 or dd/dt>15: return []
        if type(moving[i]) is not bool: return []
        if not moving[i]:
            if dd>10: return []
            continue
        hr1=number(hrs[i-1],30,240) if hrs else None
        hr2=number(hrs[i],30,240) if hrs else None
        hr=(hr1+hr2)/2 if hr1 is not None and hr2 is not None else None
        left=ds[i-1]
        if dd==0:
            parts=[(int(left//1000),0,dt)]
        else:
            parts=[]
            while left<ds[i]-1e-8:
                idx=int(left//1000)
                right=min(ds[i],(idx+1)*1000)
                parts.append((idx,right-left,dt*(right-left)/dd));left=right
        for idx,d,t in parts:
            b=bins.setdefault(idx,[0,0,0,0]);b[0]+=d;b[1]+=t
            if hr is not None: b[2]+=hr*t;b[3]+=t
    result=[{'distance_km':b[0]/1000,'duration_seconds':b[1],
             'average_hr':round(b[2]/b[3],1) if b[3] and b[3]>=.95*b[1] else None}
            for _,b in sorted(bins.items()) if b[0]>0 and b[1]>0]
    return result if valid_splits(result,km,seconds) else []


def normalize(detail, streams, km, seconds):
    stream_rows=stream_splits(streams,km,seconds)
    metric=metric_splits(detail.get('splits_metric'))
    laps=metric_splits(detail.get('laps'))
    metric=metric if valid_splits(metric,km,seconds) else []
    full_laps=laps if valid_splits(laps,km,seconds) else []
    candidates=[(stream_rows,'strava_streams'),(metric,'strava_splits_metric'),(full_laps,'strava_laps')]
    # Prefer complete HR coverage, retaining kilometre pace splits separately.
    candidates=[(rows,source) for rows,source in candidates if rows]
    candidates.sort(key=lambda item:sum(s['average_hr'] is not None for s in item[0])/len(item[0]),reverse=True)
    splits,source=candidates[0] if candidates else ([],None)
    return {'effort':effort(detail),'splits':splits,'split_source':source,
            'pace_splits':metric or stream_rows, 'laps':laps,
            'split_coverage':{'count':len(splits),'with_hr':sum(s['average_hr'] is not None for s in splits),
                              'complete':bool(splits),'time_basis':'moving time'}}


def split_metrics(splits,kind):
    drift=consistency=None
    if len(splits)>=4:
        paces=[s['duration_seconds']/s['distance_km'] for s in splits]
        consistency=round(pstdev(paces)/mean(paces)*100,2)
        if kind in ('easy','long','custom') and consistency<=10 and all(s.get('average_hr') for s in splits):
            half=len(splits)//2
            def efficiency(group):
                hr_time=sum(s['average_hr']*s['duration_seconds'] for s in group)
                return sum(s['distance_km'] for s in group)/hr_time
            drift=round((1-efficiency(splits[half:])/efficiency(splits[:half]))*100,2)
    return {'hr_drift_pct':drift,'pace_consistency_cv_pct':consistency}


def apply_details(execution,run):
    """Read-time enrichment: preserve original execution and decision audit records."""
    x=dict(execution)
    x['effort']=dict(run.get('effort') or {})
    if x.get('rpe') is not None and x.get('effort_source') != 'strava':
        x['effort']['perceived']=x['rpe']
        x['effort']['perceived_source']='saved_reported_effort'
    elif x.get('effort_source') == 'strava' or x['effort'].get('perceived') is not None:
        x['rpe']=x['effort'].get('perceived') # Compatibility only; never Relative Effort.
        x['effort_source']='strava'
    if not x.get('splits') or x.get('split_source','').startswith('strava'):
        if run.get('splits') and valid_splits(run['splits'],x.get('distance_km'),x.get('duration_seconds')):
            x['splits']=run['splits'];x['split_source']=run.get('split_source')
    x['pace_splits']=run.get('pace_splits') or []
    x['laps']=run.get('laps') or []
    x['details_fetched_at']=run.get('details_fetched_at')
    return x


def nearing_limit(response):
    headers=getattr(response,'headers',{})
    for prefix in ('X-RateLimit','X-ReadRateLimit'):
        try:
            limits=[int(v) for v in headers.get(prefix+'-Limit','').split(',')]
            used=[int(v) for v in headers.get(prefix+'-Usage','').split(',')]
            if any(u>=max(0,l-5) for l,u in zip(limits,used)): return True
        except ValueError: pass
    return False


def enrich_runs(athlete,headers):
    """Three activities per sync, latest eligible first; old runs backfill gradually."""
    from app import athlete_store as store
    from app.strava_integration import STRAVA_API_BASE
    store.init_athlete_db()
    now=time.time()
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        lock=c.execute('SELECT next_at FROM strava_detail_sync WHERE athlete_id=?',(athlete,)).fetchone()
        if lock and lock[0]>now: return {'details_refreshed':0,'details_status':'cooldown'}
        c.execute('INSERT OR REPLACE INTO strava_detail_sync VALUES(?,?)',(athlete,now+300))
        rows=c.execute('''SELECT a.*,d.next_at,d.fetched_at FROM activities a
            LEFT JOIN strava_run_details d ON d.activity_id=a.id AND d.athlete_id=a.athlete_id
            WHERE a.athlete_id=? AND a.source='strava' AND lower(a.activity_type) IN ('run','running','trailrun','virtualrun')
            AND (d.next_at IS NULL OR d.next_at<=?) ORDER BY a.start_time DESC LIMIT 3''',(athlete,now)).fetchall()
    refreshed=0; status='complete'; began=time.monotonic()
    for raw in rows:
        if time.monotonic()-began>18: status='more_pending';break
        row=dict(raw); detail=None; streams={}; limited=False; error=None
        try:
            response=httpx.get(f"{STRAVA_API_BASE}/activities/{row['source_activity_id']}",headers=headers,timeout=5)
            response.raise_for_status();candidate=response.json()
            if not isinstance(candidate,dict) or str(candidate.get('id'))!=row['source_activity_id']: raise ValueError('Activity mismatch')
            detail=candidate
            limited=nearing_limit(response)
            if not limited:
                response=httpx.get(f"{STRAVA_API_BASE}/activities/{row['source_activity_id']}/streams",headers=headers,
                    params={'keys':'time,distance,heartrate,moving','key_by_type':'true'},timeout=5)
                if response.status_code==404: error='streams_unavailable'
                else:
                    response.raise_for_status(); streams=response.json()
                limited=nearing_limit(response)
        except httpx.HTTPStatusError as exc:
            error='rate_limited' if exc.response.status_code==429 else 'provider_unavailable'
            limited=exc.response.status_code in (401,403,429)
        except (httpx.HTTPError,ValueError,TypeError): error='detail_unavailable'
        next_at=now+(900 if error and error!='streams_unavailable' else (21600 if row['start_time'][:10]>=(datetime.now(timezone.utc)-timedelta(days=7)).date().isoformat() else 30*86400))
        with connect() as c:
            old=c.execute('SELECT data_json FROM strava_run_details WHERE activity_id=? AND athlete_id=?',(row['id'],athlete)).fetchone()
            data=json.loads(old[0]) if old and old[0] else {}
            if detail is not None and isinstance(detail,dict) and str(detail.get('id'))==row['source_activity_id']:
                new=normalize(detail,streams,row['distance_km'],row['duration_seconds'])
                # Missing fields on a failed/partial detail lookup never erase valid saved data.
                if (error or limited) and data.get('splits') and not new['splits']:
                    for key in ('splits','split_source','split_coverage','pace_splits','laps'):
                        if key in data: new[key]=data[key]
                for k in ('relative','perceived'):
                    if k not in ('relative' if 'suffer_score' in detail else '', 'perceived' if 'perceived_exertion' in detail else ''):
                        new['effort'][k]=data.get('effort',{}).get(k,effort(json.loads(row.get('raw_payload') or '{}')).get(k))
                data=new;refreshed+=1
            c.execute('''INSERT INTO strava_run_details VALUES(?,?,?,?,?,?) ON CONFLICT(activity_id) DO UPDATE SET
                data_json=excluded.data_json,fetched_at=excluded.fetched_at,next_at=excluded.next_at,status=excluded.status''',
                (row['id'],athlete,json.dumps(data),store.now() if detail else row['fetched_at'],next_at,error or 'available'))
            if limited: c.execute('UPDATE strava_detail_sync SET next_at=? WHERE athlete_id=?',(now+3600,athlete))
        if limited: status=error or 'rate_limit_near';break
        if error and detail is None: status=error;break
    with connect() as c:
        remaining=c.execute("""SELECT COUNT(*) FROM activities a LEFT JOIN strava_run_details d ON d.activity_id=a.id AND d.athlete_id=a.athlete_id
            WHERE a.athlete_id=? AND a.source='strava' AND lower(a.activity_type) IN ('run','running','trailrun','virtualrun') AND d.fetched_at IS NULL""",(athlete,)).fetchone()[0]
    return {'details_refreshed':refreshed,'details_status':status,'details_remaining':remaining}
