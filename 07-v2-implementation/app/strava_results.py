"""Conservative, idempotent matching of synced runs to active workouts."""
import json
from collections import defaultdict

from fastapi import HTTPException
from pydantic import ValidationError

from app import athlete_store as store
from app.athlete_coach import execute
from app.athlete_models import Execution
from app.storage import connect


def reconcile(athlete):
    store.init_athlete_db()
    by_day = defaultdict(list)
    # Include other providers when detecting ambiguity; never guess between runs.
    for run in store.runs(athlete):
        by_day[run['date']].append(run)
    with connect() as c:
        rows = c.execute('''SELECT w.* FROM coach_workouts w
            LEFT JOIN coach_executions x ON x.workout_id=w.id
            WHERE w.athlete_id=? AND w.active=1 AND x.workout_id IS NULL
            AND w.date<=? ORDER BY w.date''',
            (athlete, store.today(athlete).isoformat())).fetchall()
    dates = defaultdict(list)
    for row in rows:
        dates[row['date']].append(row)
    matched = 0
    for day, workouts in dates.items():
        runs = by_day[day]
        if len(workouts) != 1 or len(runs) != 1 or runs[0]['source'] != 'strava':
            continue
        row, run = workouts[0], runs[0]
        target = json.loads(row['current_json'])
        if target.get('distance_km', 0) <= 0 or not run.get('distance_km') or not run.get('duration_seconds'):
            continue
        try:
            execute(row['id'], Execution(activity_id=run['id'],
                completed=run['distance_km'] >= target['distance_km'] * .9,
                notes='Automatically matched from Strava. Completion inferred from distance; effort and pain not reported.'), athlete)
            matched += 1
        except (HTTPException, ValidationError):
            # A concurrent sync/manual link can win; do not overwrite it.
            continue
    return {'matched_workouts': matched}
