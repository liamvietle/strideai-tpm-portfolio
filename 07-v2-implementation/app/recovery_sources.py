"""Merge dated recovery measurements without creating training decisions."""
from datetime import date, timedelta

from app.apple_health import health_rows
from app.garmin_recovery import recovery_rows


def automatic_recovery_rows(athlete_id, start, end, path=None):
    rows = {r['checkin_date']: r for r in health_rows(athlete_id, start, end, path)}
    for garmin in recovery_rows(athlete_id, start, end, path):
        merged = rows.setdefault(garmin['checkin_date'], {'checkin_date': garmin['checkin_date']})
        for field in ('sleep_hours', 'resting_hr_bpm'):
            if garmin[field] is not None: merged[field] = garmin[field]
        # Never combine Garmin HRV with an Apple Health SDNN baseline.
        if garmin['hrv_ms'] is not None:
            for field in ('hrv_ms', 'hrv_baseline_low', 'hrv_baseline_high'):
                merged[field] = garmin[field]
    return [rows[k] for k in sorted(rows)]


def enrich_with_recovery(payload, path=None):
    end = (date.fromisoformat(payload.checkin_date) + timedelta(days=1)).isoformat()
    rows = automatic_recovery_rows(payload.athlete_id, payload.checkin_date, end, path)
    if not rows: return payload
    state = rows[0]
    updates = {}
    for field in ('sleep_hours', 'resting_hr_bpm'):
        if getattr(payload, field) is None and state.get(field) is not None:
            updates[field] = state[field]
    if payload.hrv_ms is None and state.get('hrv_ms') is not None:
        updates['hrv_ms'] = state['hrv_ms']
        for field in ('hrv_baseline_low', 'hrv_baseline_high'):
            # Caller-supplied limits remain explicit overrides.
            updates[field] = getattr(payload, field) if getattr(payload, field) is not None else state.get(field)
    return payload.model_copy(update=updates) if updates else payload
