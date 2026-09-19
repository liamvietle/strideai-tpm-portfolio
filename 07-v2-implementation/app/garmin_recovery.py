"""Recovery-only Garmin export import. Never writes activities or check-ins."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.storage import connect, db_path

FIELDS = ('sleep_hours', 'resting_hr_bpm', 'hrv_ms', 'hrv_baseline_low', 'hrv_baseline_high')
router = APIRouter(prefix='/app/api/garmin-recovery')


class RecoveryDay(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    date: date
    sleep_hours: float | None = Field(default=None, gt=0, le=24)
    resting_hr_bpm: float | None = Field(default=None, ge=20, le=220)
    hrv_ms: float | None = Field(default=None, gt=0, le=1000)
    hrv_baseline_low: float | None = Field(default=None, gt=0, le=1000)
    hrv_baseline_high: float | None = Field(default=None, gt=0, le=1000)

    @model_validator(mode='after')
    def valid_day(self):
        if self.date > datetime.now(timezone.utc).date():
            raise ValueError('Recovery dates cannot be in the future.')
        if all(getattr(self, f) is None for f in FIELDS[:3]):
            raise ValueError('A day must contain sleep, resting heart rate or HRV.')
        low, high = self.hrv_baseline_low, self.hrv_baseline_high
        if (low is None) != (high is None) or (low is not None and (self.hrv_ms is None or low > high)):
            raise ValueError('HRV baseline requires an HRV value and an ordered pair of limits.')
        return self


class RecoveryImport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format: str = Field(pattern=r'^strideai-garmin-recovery-v1$')
    days: list[RecoveryDay] = Field(min_length=1, max_length=5000)

    @model_validator(mode='after')
    def unique_days(self):
        if len({d.date for d in self.days}) != len(self.days):
            raise ValueError('Duplicate dates are not allowed.')
        return self


def init_garmin_db(path=None):
    with connect(path) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS garmin_recovery_daily (
            athlete_id TEXT NOT NULL, checkin_date TEXT NOT NULL,
            sleep_hours REAL, resting_hr_bpm REAL, hrv_ms REAL,
            hrv_baseline_low REAL, hrv_baseline_high REAL,
            imported_at TEXT NOT NULL, PRIMARY KEY(athlete_id, checkin_date))''')


def recovery_rows(athlete_id, start='0001-01-01', end='9999-12-31', path=None):
    init_garmin_db(path)
    with connect(path) as conn:
        return [dict(r) for r in conn.execute('''SELECT * FROM garmin_recovery_daily
            WHERE athlete_id=? AND checkin_date>=? AND checkin_date<? ORDER BY checkin_date''',
            (athlete_id, start, end))]


def import_recovery(payload: RecoveryImport, athlete_id='viet', path=None):
    target = Path(path) if path else db_path()
    # A private SQLite backup precedes the transaction; no raw export is retained.
    digest = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()[:16]
    backup = target.parent / 'backups' / f'pre-garmin-recovery-{digest}.sqlite'
    if target.exists() and not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(target) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
    init_garmin_db(path)
    inserted = updated = unchanged = 0
    now = datetime.now(timezone.utc).isoformat()
    with connect(path) as conn:
        for day in payload.days:
            existing = conn.execute('SELECT * FROM garmin_recovery_daily WHERE athlete_id=? AND checkin_date=?',
                                    (athlete_id, day.date.isoformat())).fetchone()
            # Missing metrics in a later partial export cannot erase existing values.
            values = [getattr(day, f) if getattr(day, f) is not None else (existing[f] if existing else None) for f in FIELDS]
            if day.hrv_ms is not None:
                values[3:] = [day.hrv_baseline_low, day.hrv_baseline_high]
            if existing and values == [existing[f] for f in FIELDS]:
                unchanged += 1
                continue
            conn.execute('''INSERT INTO garmin_recovery_daily VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(athlete_id,checkin_date) DO UPDATE SET
                sleep_hours=excluded.sleep_hours, resting_hr_bpm=excluded.resting_hr_bpm,
                hrv_ms=excluded.hrv_ms, hrv_baseline_low=excluded.hrv_baseline_low,
                hrv_baseline_high=excluded.hrv_baseline_high, imported_at=excluded.imported_at''',
                (athlete_id, day.date.isoformat(), *values, now))
            if existing: updated += 1
            else: inserted += 1
    return {'received': len(payload.days), 'inserted': inserted, 'updated': updated, 'unchanged': unchanged,
            'first_date': min(d.date for d in payload.days).isoformat(),
            'latest_date': max(d.date for d in payload.days).isoformat()}


@router.post('/import')
def import_endpoint(payload: RecoveryImport, athlete_id: str = Query(default='viet', min_length=1, max_length=100)):
    return import_recovery(payload, athlete_id)


@router.get('/history')
def history(athlete_id: str = 'viet', limit: int = Query(default=30, ge=1, le=5000)):
    rows = recovery_rows(athlete_id)
    return {'days': len(rows), 'first_date': rows[0]['checkin_date'] if rows else None,
            'latest_date': rows[-1]['checkin_date'] if rows else None,
            'counts': {f: sum(r[f] is not None for r in rows) for f in FIELDS[:3]},
            'rows': list(reversed(rows[-limit:]))}


def normalize_export(root: Path):
    """Read only the three required file families, selecting an explicit allowlist."""
    root = root / 'DI_CONNECT' if (root / 'DI_CONNECT').exists() else root
    output = {}
    skipped = {}
    def add(day, field, value):
        if not day: return
        date.fromisoformat(day)
        row = output.setdefault(day, {'date': day})
        if field in row and row[field] != value:
            raise ValueError(f'Conflicting {field} records on {day}; review before import.')
        row[field] = value
    def number(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    def records(folder, pattern):
        for f in sorted((root / folder).glob(pattern)):
            for r in json.loads(f.read_text(encoding='utf-8-sig')):
                yield r
    for r in records('DI-Connect-Wellness', '*sleepData.json'):
        stages = [r.get(k) for k in ('deepSleepSeconds','lightSleepSeconds','remSleepSeconds')]
        if not r.get('calendarDate') or not all(number(v) and v >= 0 for v in stages[:2]):
            skipped['sleep_missing_stages_or_date'] = skipped.get('sleep_missing_stages_or_date', 0) + 1
            continue
        if stages[2] is None:
            # Omitted REM can represent zero, but only accept if the sleep window reconciles.
            try:
                window = (datetime.fromisoformat(r['sleepEndTimestampGMT']) - datetime.fromisoformat(r['sleepStartTimestampGMT'])).total_seconds()
                accounted = sum(stages[:2]) + r['awakeSleepSeconds'] + (r.get('unmeasurableSeconds') or 0)
                if abs(window - accounted) > 180: raise ValueError()
                stages[2] = 0
            except (KeyError, TypeError, ValueError):
                skipped['sleep_incomplete'] = skipped.get('sleep_incomplete', 0) + 1
                continue
        if not number(stages[2]) or stages[2] < 0: raise ValueError('Invalid sleep stage.')
        add(r['calendarDate'], 'sleep_hours', round(sum(stages) / 3600, 4))
    for r in records('DI-Connect-Aggregator', 'UDSFile*.json'):
        if number(r.get('restingHeartRate')):
            add(r.get('calendarDate'), 'resting_hr_bpm', r['restingHeartRate'])
    for r in records('DI-Connect-Wellness', '*healthStatusData.json'):
        for metric in r.get('metrics', []):
            if metric.get('type') == 'HRV' and number(metric.get('value')):
                add(r.get('calendarDate'), 'hrv_ms', metric['value'])
                low, high = metric.get('baselineLowerLimit'), metric.get('baselineUpperLimit')
                if number(low) and number(high) and 0 < low <= high <= 1000:
                    add(r['calendarDate'], 'hrv_baseline_low', low)
                    add(r['calendarDate'], 'hrv_baseline_high', high)
                else:
                    skipped['invalid_hrv_baseline_pair'] = skipped.get('invalid_hrv_baseline_pair', 0) + 1
    payload = RecoveryImport(format='strideai-garmin-recovery-v1', days=[output[k] for k in sorted(output)])
    return payload, skipped


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Prepare recovery-only Garmin data; does not upload or import.')
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    payload, skipped = normalize_export(args.export)
    args.output.write_text(payload.model_dump_json(indent=2), encoding='utf-8')
    print(json.dumps({'days':len(payload.days), 'first':str(payload.days[0].date), 'last':str(payload.days[-1].date),
                      'counts':{f:sum(getattr(d,f) is not None for d in payload.days) for f in FIELDS[:3]}, 'skipped':skipped}))
