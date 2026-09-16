from pathlib import Path

from app.engine import evaluate_workout
from app.evaluation import run_evaluation
from app.ingestion import parse_garmin_summary_csv, parse_tcx
from app.models import OutcomeInput, WorkoutInput
from app.storage import get_outcome, init_db, list_activities, save_outcome, save_recommendation, upsert_activities

TCX = """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">
  <Activities><Activity Sport="Running"><Id>2026-09-13T20:30:00Z</Id>
  <Lap StartTime="2026-09-13T20:30:00Z">
    <TotalTimeSeconds>3600</TotalTimeSeconds><DistanceMeters>10000</DistanceMeters><Calories>650</Calories>
    <Track><Trackpoint><Time>2026-09-13T20:30:00Z</Time><HeartRateBpm><Value>150</Value></HeartRateBpm></Trackpoint>
    <Trackpoint><Time>2026-09-13T20:31:00Z</Time><HeartRateBpm><Value>160</Value></HeartRateBpm></Trackpoint></Track>
  </Lap></Activity></Activities>
</TrainingCenterDatabase>"""


def test_tcx_parser_normalizes_activity():
    records = parse_tcx(TCX, athlete_id="viet", source="garmin")
    assert len(records) == 1
    r = records[0]
    assert r.distance_km == 10
    assert r.duration_seconds == 3600
    assert r.average_hr == 155
    assert r.max_hr == 160
    assert r.activity_type == "running"


def test_garmin_csv_parser():
    csv_text = "Activity Type,Date,Title,Distance,Time,Avg HR,Max HR,Calories\nRunning,2026-09-01 06:00,Morning Run,8.2,00:45:00,145,166,500\n"
    r = parse_garmin_summary_csv(csv_text, athlete_id="viet")[0]
    assert r.distance_km == 8.2
    assert r.duration_seconds == 2700
    assert r.average_hr == 145


def test_sqlite_upsert_is_idempotent(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    records = parse_tcx(TCX, athlete_id="viet", source="garmin")
    assert upsert_activities(records, db) == (1, 0)
    assert upsert_activities(records, db) == (0, 1)
    rows = list_activities("viet", path=db)
    assert len(rows) == 1
    assert rows[0]["distance_km"] == 10


def test_eval_runner_has_zero_safety_violations():
    import json
    cases = json.loads((Path(__file__).parents[1] / "evaluation" / "cases.json").read_text())
    summary = run_evaluation(cases)
    assert summary.cases == 6
    assert summary.safety_violations == 0
    assert summary.action_accuracy == 1.0


def test_recommendation_outcome_feedback_loop(tmp_path):
    db = tmp_path / "test.db"
    init_db(db)
    workout = WorkoutInput(
        athlete_id="viet",
        planned_distance_km=10,
        planned_intensity="easy",
        recent_load_ratio=1.0,
        hrv_vs_baseline_pct=0,
        resting_hr_delta_bpm=0,
        sleep_hours=8,
        soreness_0_10=1,
    )
    rec = evaluate_workout(workout)
    rec_id = save_recommendation(workout, rec, path=db)
    save_outcome(rec_id, OutcomeInput(completed=True, perceived_effort_0_10=4, pain_after=False), path=db)
    outcome = get_outcome(rec_id, path=db)
    assert outcome["completed"] == 1
    assert outcome["perceived_effort_0_10"] == 4
    assert outcome["pain_after"] == 0
