"""Dated source availability, not a claim that a check-in used these values."""
from datetime import timedelta
from app.apple_health import health_rows, init_apple_health_db
from app.garmin_recovery import recovery_rows, init_garmin_db
from app.storage import connect


def status(athlete, day):
    init_apple_health_db();init_garmin_db()
    key=day.isoformat();end=(day+timedelta(days=1)).isoformat()
    apple=next(iter(health_rows(athlete,key,end)),{})
    garmin=next(iter(recovery_rows(athlete,key,end)),{})
    with connect() as c:
        latest_g=c.execute('SELECT MAX(checkin_date) FROM garmin_recovery_daily WHERE athlete_id=?',(athlete,)).fetchone()[0]
        latest_a=c.execute('SELECT MAX(health_date) FROM apple_health_daily WHERE athlete_id=?',(athlete,)).fetchone()[0]
    metrics=[]
    for field,label in [('sleep_hours','Sleep'),('resting_hr_bpm','Resting HR'),('hrv_ms','HRV')]:
        row=garmin if garmin.get(field) is not None else apple
        available=row.get(field) is not None
        metrics.append({'field':field,'label':label,'available':available,'value':row.get(field),
                        'source':('Garmin import' if row is garmin else 'Apple Health companion') if available else None,
                        'record_updated_at':row.get('imported_at') if row is garmin else row.get('updated_at')})
    return {'date':key,'status':'complete' if all(m['available'] for m in metrics) else 'partial' if any(m['available'] for m in metrics) else 'missing',
            'metrics':metrics,'garmin_latest_date':latest_g,'apple_latest_date':latest_a,
            'garmin_note':'Garmin recovery uses imported exports; this is not a live Garmin connection.',
            'usage_note':'These measurements are available for the selected date. Values already entered in the check-in take precedence. Record update times are not measurement times.'}
