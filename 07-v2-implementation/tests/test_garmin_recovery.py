import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main
from app.garmin_recovery import RecoveryImport, import_recovery, normalize_export, recovery_rows
from app.apple_health import AppleHealthSyncInput, upsert_apple_health
from app.personal_models import DailyCheckInInput
from app.personal_service import build_accumulated_input
from app.personal_storage import init_personal_app_db
from app.recovery_sources import enrich_with_recovery
from app.storage import connect


def payload(**kwargs):
    return RecoveryImport(format='strideai-garmin-recovery-v1', days=[{'date':'2026-09-16', **kwargs}])


def test_import_atomic_idempotent_preserves_other_tables_and_backup(tmp_path, monkeypatch):
    path=tmp_path/'db.sqlite'; monkeypatch.setenv('STRIDEAI_DB_PATH',str(path))
    init_personal_app_db()
    before={}
    with connect() as c:
        for table in ['activities','daily_checkins','recommendations']:
            before[table]=[tuple(r) for r in c.execute(f'SELECT * FROM {table}')]
    first=import_recovery(payload(sleep_hours=7, resting_hr_bpm=52, hrv_ms=48, hrv_baseline_low=40, hrv_baseline_high=60))
    assert first['inserted']==1
    assert import_recovery(payload(sleep_hours=7))['unchanged']==1
    assert import_recovery(payload(sleep_hours=8))['updated']==1
    row=recovery_rows('viet')[0]
    assert row['hrv_ms']==48 and row['sleep_hours']==8
    assert list((tmp_path/'backups').glob('*.sqlite'))
    with connect() as c:
        for table,rows in before.items():
            assert [tuple(r) for r in c.execute(f'SELECT * FROM {table}')]==rows
    assert recovery_rows('someone-else')==[]


@pytest.mark.parametrize('fields',[{'sleep_hours':25},{'hrv_ms':float('nan')},{'body_battery':80}, {'hrv_ms':40,'hrv_baseline_low':60,'hrv_baseline_high':30}])
def test_invalid_data_rejected(fields):
    with pytest.raises(ValidationError): payload(**fields)


def test_export_only_reads_allowlisted_metrics_and_handles_missing_sleep(tmp_path):
    wellness=tmp_path/'DI-Connect-Wellness';wellness.mkdir()
    agg=tmp_path/'DI-Connect-Aggregator';agg.mkdir()
    (wellness/'x_sleepData.json').write_text(json.dumps([
        {'calendarDate':'2026-09-16','deepSleepSeconds':3600,'lightSleepSeconds':14400,'remSleepSeconds':7200,'awakeSleepSeconds':3600,'napList':[{'duration':9999}]},
        {'retro':False},
        {'calendarDate':'2026-09-15','deepSleepSeconds':3600,'lightSleepSeconds':18000,'remSleepSeconds':None,'awakeSleepSeconds':0,'sleepStartTimestampGMT':'2026-09-14T20:00:00','sleepEndTimestampGMT':'2026-09-15T02:00:00'}]))
    (agg/'UDSFile_test.json').write_text(json.dumps([{'calendarDate':'2026-09-16','restingHeartRate':51,'bodyBattery':{'value':80},'allDayStress':{'value':20}}]))
    (wellness/'x_healthStatusData.json').write_text(json.dumps([{'calendarDate':'2026-09-16','metrics':[{'type':'HRV','value':50,'baselineLowerLimit':-1,'baselineUpperLimit':0},{'type':'SPO2','value':98}]}]))
    data,skipped=normalize_export(tmp_path)
    assert data.days[-1].sleep_hours==7
    assert data.days[0].sleep_hours==6
    assert data.days[-1].hrv_baseline_low is None
    assert skipped=={'sleep_missing_stages_or_date':1,'invalid_hrv_baseline_pair':1}
    assert 'bodyBattery' not in data.model_dump_json() and 'SPO2' not in data.model_dump_json()


def test_manual_priority_date_scope_and_hrv_sources(tmp_path, monkeypatch):
    monkeypatch.setenv('STRIDEAI_DB_PATH',str(tmp_path/'db.sqlite'))
    init_personal_app_db()
    upsert_apple_health(AppleHealthSyncInput(device_id='test-device',generated_at=datetime.now(timezone.utc),summaries=[{'date':'2026-09-16','timezone':'Asia/Ho_Chi_Minh','sleep_hours':6,'hrv_ms':20}]))
    import_recovery(payload(sleep_hours=7,resting_hr_bpm=51,hrv_ms=50))
    run=DailyCheckInInput(checkin_date='2026-09-16',planned_distance_km=8,planned_intensity='easy',human_decision='maintain')
    filled=enrich_with_recovery(run)
    assert (filled.sleep_hours,filled.hrv_ms,filled.resting_hr_bpm)==(7,50,51)
    assert filled.hrv_baseline_low is None
    manual=enrich_with_recovery(run.model_copy(update={'sleep_hours':9,'hrv_ms':55}))
    assert (manual.sleep_hours,manual.hrv_ms)==(9,55)
    tomorrow=run.model_copy(update={'checkin_date':'2026-09-17'})
    assert enrich_with_recovery(tomorrow).sleep_hours is None
    accumulated,_=build_accumulated_input(tomorrow)
    assert len(accumulated.recovery_history)==1
    assert accumulated.recovery_history[0].sleep_hours==7
    assert accumulated.sleep_hours is None


def test_endpoint_auth_and_validation(tmp_path, monkeypatch):
    monkeypatch.setenv('STRIDEAI_DB_PATH',str(tmp_path/'db.sqlite'))
    monkeypatch.delenv('STRIDEAI_ACCOUNT_AUTH',raising=False)
    monkeypatch.setattr(main,'APP_KEY','test-secret')
    client=TestClient(main.app)
    body=payload(sleep_hours=7).model_dump(mode='json')
    assert client.post('/app/api/garmin-recovery/import',json=body).status_code==401
    assert client.get('/app/api/garmin-recovery/history').status_code==401
    client.headers['X-StrideAI-Key']='test-secret'
    assert client.post('/app/api/garmin-recovery/import',json=body).status_code==200
    assert client.get('/app/api/garmin-recovery/history').json()['counts']['sleep_hours']==1
    body['days'].append(body['days'][0])
    assert client.post('/app/api/garmin-recovery/import',json=body).status_code==422
