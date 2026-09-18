import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app import athlete_store as store
from app.athlete_api import weekly_review, workouts
from app.athlete_coach import decide, evaluate, execute, predict
from app.athlete_learning import can_relax, learn
from app.athlete_models import Decision, Execution, GeneratePlan
from app.athlete_planning import generate
from app.main import app
from app.models import ActivityRecord
from app.personal_models import DailyCheckInInput
from app.personal_service import create_personal_recommendation
from app.storage import connect, upsert_activities
from app.training_plan import RaceGoal, save_goal

DAY = date(2026, 9, 17)


def test_combined_calendar_strength_and_start():
    from app.athlete_planning import plan_setup
    setup()
    store.patch_profile({'long_run_day': 5, 'include_strength': True, 'strength_days': [1]})
    result = generate(GeneratePlan(start_mode='next_monday', replace_existing=True), 'viet')
    assert result['start_date'] == '2026-09-21'
    rows = workouts()
    future = [w['current'] for w in rows if w['date'] >= result['start_date']]
    assert all(date.fromisoformat(w['date']).weekday() == 5 for w in future if w['kind'] == 'long')
    strength = [w for w in future if w['strength_session']]
    assert strength
    assert all(date.fromisoformat(w['date']).weekday() == 1 for w in strength)
    assert all(w['strength_minutes'] + w['duration_minutes'] <= 150 for w in strength)
    assert plan_setup('viet')['recommended_weeks'] == 16


def test_combined_forecast_is_dated_and_separate():
    from app.race_prediction import race_prediction
    setup()
    assert race_prediction()['status'] == 'unavailable'
    store.patch_profile({'pbs': [{'distance_km': 42.195, 'time_seconds': 14400, 'date': '2026-09-01'}]})
    first = race_prediction()
    assert first['predicted_seconds'] == 14400
    assert first['goal_seconds'] == 13800
    store.patch_profile({'pbs': [{'distance_km': 42.195, 'time_seconds': 14100, 'date': '2026-09-16'}]})
    assert race_prediction()['predicted_seconds'] == 14100
    assert race_prediction('someone-else')['status'] == 'unavailable'


def test_combined_invalid_calendar():
    from pydantic import ValidationError
    setup()
    with pytest.raises(ValidationError):
        store.patch_profile({'long_run_day': 2})
    with pytest.raises(ValidationError):
        store.patch_profile({'include_strength': True, 'strength_days': []})


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "loop.db"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("STRIDEAI_COACH_AI_ENABLED", "false")
    monkeypatch.setattr(store, "today", lambda athlete="viet": DAY)
    monkeypatch.setattr("app.main.APP_KEY", "")


def setup(athlete="viet"):
    store.patch_profile(
        {
            "age": 33,
            "running_years": 3,
            "recent_weekly_km": 50,
            "available_days": [0, 1, 3, 5, 6],
            "max_session_minutes": 150,
            "threshold_pace": 300,
            "threshold_hr": 167,
            "max_hr": 183,
        },
        athlete,
    )
    save_goal(
        RaceGoal(name="Race", race_date=DAY + timedelta(days=90), goal_minutes=230),
        athlete,
    )
    generate(GeneratePlan(start_date=DAY), athlete)
    return workouts(athlete)[0]


def check(athlete="viet", pain=False):
    w = workouts(athlete)[0]
    return create_personal_recommendation(
        DailyCheckInInput(
            athlete_id=athlete,
            checkin_date=DAY.isoformat(),
            planned_distance_km=w["current"]["distance_km"],
            planned_intensity="easy",
            human_decision="maintain",
            sleep_hours=8,
            soreness_0_10=0,
            pain_flag=pain,
        )
    )


def test_partial_profile_patch_and_validation():
    client = TestClient(app)
    assert client.patch("/app/api/coach/profile", json={"age": 33}).status_code == 200
    assert (
        client.patch("/app/api/coach/profile", json={"weight_kg": 70}).status_code
        == 200
    )
    data = client.get("/app/api/coach/profile").json()
    assert data["profile"]["age"] == 33
    assert data["profile"]["hrv_ms"] is None
    assert (
        client.patch(
            "/app/api/coach/profile", json={"available_days": [2, 2]}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/app/api/coach/profile", json={"max_hr": 150, "threshold_hr": 180}
        ).status_code
        == 422
    )
    assert (
        client.patch("/app/api/coach/profile", json={"unrecognized": 1}).status_code
        == 422
    )


def test_first_pass_limits_and_original_preserved():
    setup()
    ws = workouts()
    assert all(
        w["current"]["duration_minutes"] <= 150
        for w in ws
        if w["current"]["kind"] != "race"
    )
    assert all(
        w["current"]["distance_km"] == 0
        for w in ws
        if date.fromisoformat(w["date"]).weekday() in {2, 4}
        and w["current"]["kind"] != "race"
    )
    assert ws[-1]["current"]["kind"] == "race"
    assert ws[-1]["current"]["pace_target"] is None
    with pytest.raises(HTTPException):
        generate(GeneratePlan(start_date=DAY), "viet")


def test_cold_start_no_fabricated_pace_or_hr():
    save_goal(
        RaceGoal(
            name="5K",
            race_date=DAY + timedelta(days=45),
            distance_km=5,
            goal_minutes=20,
        )
    )
    generate(GeneratePlan(start_date=DAY), "viet")
    ws = workouts()
    assert all(
        w["current"]["pace_target"] is None and w["current"]["hr_target"] is None
        for w in ws
    )
    assert sum(w["current"]["distance_km"] for w in ws[:7]) <= 9


def test_full_loop_prediction_decision_execution_evaluation_idempotent():
    w = setup()
    check()
    p = predict(w["id"], "viet")
    assert predict(w["id"], "viet") == p
    decide(w["id"], Decision(choice="accept"), "viet")
    target = p["recommended"]
    expected = p["recommended_expectation"]
    x = Execution(
        distance_km=target["distance_km"],
        duration_seconds=target["distance_km"] * expected["pace"],
        average_hr=expected["hr"],
        rpe=expected["rpe"],
        completed=True,
    )
    execute(w["id"], x, "viet")
    execute(w["id"], x, "viet")
    out = evaluate(w["id"], "viet")
    assert out["comparison"] == "within"
    assert out["pace_error_seconds_km"] == 0
    assert evaluate(w["id"], "viet") == out
    assert workouts()[0]["state"] == "evaluated"
    assert workouts()[0]["original"] == w["original"]
    assert learn("viet")["easy_hr_pace"]["samples"] == 1
    assert weekly_review()["completed_km"] == round(target["distance_km"], 1)


def test_hard_safety_accept_shows_and_applies_rest_of_week():
    w = setup()
    check(pain=True)
    p = predict(w["id"], "viet")
    assert p["hard_stop"] and p["recommended"]["distance_km"] == 0
    assert all(e["after_km"] == 0 for e in p["week_effect"])
    decide(w["id"], Decision(choice="accept"), "viet")
    assert workouts()[0]["current"]["distance_km"] == 0
    assert workouts()[0]["original"]["distance_km"] > 0
    assert workouts()[1]["current"]["distance_km"] == 0
    with pytest.raises(HTTPException):
        decide(w["id"], Decision(choice="decline"), "viet")


def test_decline_not_success_and_pain_reduces_future():
    w = setup()
    check(pain=True)
    predict(w["id"], "viet")
    decide(w["id"], Decision(choice="decline"), "viet")
    assert workouts()[0]["current"] == w["current"]
    execute(
        w["id"],
        Execution(distance_km=2, duration_seconds=900, completed=False, pain=True),
        "viet",
    )
    e = evaluate(w["id"], "viet")
    assert e["quality"] == "recovery_concern" and e["next_changes"]
    assert all(x["after_km"] == 0 for x in e["next_changes"])
    assert all(t["samples"] < 5 for t in learn("viet").values())


def test_missing_prediction_never_claims_prospective_accuracy():
    w = setup()
    execute(
        w["id"], Execution(distance_km=5, duration_seconds=1800, completed=True), "viet"
    )
    e = evaluate(w["id"], "viet")
    assert not e["prediction_valid"]
    assert e["comparison"] == "insufficient_data"
    assert e["hr_drift_pct"] is None


def activity(athlete="viet", sport="Run", start="2026-09-17T10:00:00Z"):
    upsert_activities(
        [
            ActivityRecord(
                source="strava",
                source_activity_id="123",
                athlete_id=athlete,
                start_time=start,
                activity_type=sport,
                distance_km=8,
                duration_seconds=3000,
                average_hr=140,
                raw_format="json",
                raw_payload=json.dumps({"start_date_local": "2026-09-17T17:00:00Z"}),
            )
        ]
    )
    with connect() as c:
        return c.execute(
            "SELECT id FROM activities WHERE athlete_id=?", (athlete,)
        ).fetchone()[0]


def test_post_run_prediction_and_cross_athlete_link_rejected():
    w = setup()
    check()
    activity()
    with pytest.raises(HTTPException):
        predict(w["id"], "viet")
    other = setup("other")
    with pytest.raises(HTTPException):
        execute(other["id"], Execution(activity_id=1, completed=True), "other")
    with pytest.raises(HTTPException):
        predict(w["id"], "other")


def test_prediction_after_activity_start_is_not_scored(monkeypatch):
    w = setup()
    check()
    monkeypatch.setattr(store, "now", lambda: "2026-09-17T12:00:00+00:00")
    predict(w["id"], "viet")
    aid = activity(start="2026-09-17T10:00:00Z")
    execute(w["id"], Execution(activity_id=aid, rpe=3, completed=True), "viet")
    assert evaluate(w["id"], "viet")["prediction_valid"] is False


def test_split_drift_and_consistency():
    w = setup()
    check()
    predict(w["id"], "viet")
    splits = [
        {"distance_km": 2, "duration_seconds": 750, "average_hr": h}
        for h in [130, 130, 140, 140]
    ]
    execute(
        w["id"],
        Execution(
            distance_km=8,
            duration_seconds=3000,
            average_hr=135,
            rpe=3,
            completed=True,
            splits=splits,
        ),
        "viet",
    )
    e = evaluate(w["id"], "viet")
    assert e["pace_consistency_cv_pct"] == 0
    assert e["hr_drift_pct"] == pytest.approx(7.14)


def test_mismatched_splits_and_rewrite_rejected():
    w = setup()
    with pytest.raises(HTTPException):
        execute(
            w["id"],
            Execution(
                distance_km=8,
                duration_seconds=3000,
                completed=True,
                splits=[{"distance_km": 1, "duration_seconds": 300}],
            ),
            "viet",
        )
    execute(
        w["id"], Execution(distance_km=8, duration_seconds=3000, completed=True), "viet"
    )
    with pytest.raises(HTTPException):
        execute(
            w["id"],
            Execution(distance_km=9, duration_seconds=3000, completed=True),
            "viet",
        )


def test_no_repeated_learning_from_repeat_evaluation():
    w = setup()
    execute(
        w["id"],
        Execution(
            distance_km=8, duration_seconds=3000, average_hr=135, rpe=3, completed=True
        ),
        "viet",
    )
    evaluate(w["id"], "viet")
    evaluate(w["id"], "viet")
    assert learn("viet")["easy_hr_pace"]["samples"] == 1


def test_generation_preserves_locked_workout():
    w = setup()
    check()
    predict(w["id"], "viet")
    generate(GeneratePlan(start_date=DAY, replace_existing=True), "viet")
    assert workouts()[0]["id"] == w["id"]
    assert workouts()[0]["prediction"] is not None


def test_guarded_ai_choice_and_fallback(monkeypatch):
    import httpx

    from app.coach_reasoning import choose

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("STRIDEAI_COACH_AI_ENABLED", "true")

    def respond(*args, **kwargs):
        assert kwargs["json"]["store"] is False
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "candidate_id": "unsafe",
                        "evidence_ids": ["state"],
                        "uncertainty": "",
                    }
                )
            },
            request=httpx.Request("POST", "https://example.org"),
        )

    monkeypatch.setattr("app.coach_reasoning.httpx.post", respond)
    assert choose({"state": {}}, {"baseline": {}}, "baseline")[1]["fallback"]

    def valid(*args, **kwargs):
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "candidate_id": "extra",
                        "evidence_ids": ["state"],
                        "uncertainty": "",
                    }
                )
            },
            request=httpx.Request("POST", "https://example.org"),
        )

    monkeypatch.setattr("app.coach_reasoning.httpx.post", valid)
    candidate, trace = choose({"state": {}}, {"baseline": {}, "extra": {}}, "baseline")
    assert candidate == "extra" and not trace["fallback"]


def test_relaxation_requires_physiology_and_next_day_not_just_decline():
    cases = []
    health = []
    for i in range(5):
        d = DAY - timedelta(days=i * 3 + 2)
        cases.append(
            {
                "date": d.isoformat(),
                "choice": "decline",
                "prediction": {"base_action": "reduce_intensity"},
                "evaluation": {
                    "completion_ratio": 1,
                    "comparison": "within",
                    "hr_error_bpm": 0,
                },
                "execution": {"rpe": 3, "pain": False},
            }
        )
        health.append(
            {
                "date": (d + timedelta(days=1)).isoformat(),
                "sleep_hours": 8,
                "soreness": 1,
                "pain": False,
            }
        )
    assert not can_relax(cases, [])
    assert can_relax(cases, health)
    cases[0]["execution"]["pain"] = True
    assert not can_relax(cases, health)


def test_migration_repeat_and_access_protection(monkeypatch):
    setup()
    store.init_athlete_db()
    store.init_athlete_db()
    with connect() as c:
        assert (
            c.execute("SELECT count(*) FROM athlete_loop_migrations").fetchone()[0] == 1
        )
    monkeypatch.setattr("app.main.APP_KEY", "secret")
    client = TestClient(app)
    for url in [
        "/app/api/coach/profile",
        "/app/api/coach/workouts",
        "/app/api/coach/review",
    ]:
        assert client.get(url).status_code == 401
        assert client.get(url, headers={"X-StrideAI-Key": "secret"}).status_code == 200
    assert client.get("/app").status_code == 200


def test_new_ui_and_legacy_hooks():
    html = TestClient(app).get("/app").text
    for id in [
        "athleteForm",
        "coachToday",
        "coachDetail",
        "coachReview",
        "connectStravaBtn",
        "planned_activity_type",
        "weatherStart",
    ]:
        assert f'id="{id}"' in html


def test_evaluated_pain_blocks_regeneration_until_profile_reassessed():
    w = setup()
    execute(
        w["id"],
        Execution(distance_km=2, duration_seconds=900, completed=False, pain=True),
        "viet",
    )
    evaluate(w["id"], "viet")
    assert store.profile().active_injury
    generate(GeneratePlan(start_date=DAY, replace_existing=True), "viet")
    assert all(
        w["current"]["distance_km"] == 0
        for w in workouts()[1:]
        if w["current"]["kind"] != "race"
    )


def test_imported_sleep_history_contributes_to_fatigue():
    w = setup()
    store.patch_profile(
        {
            "health_history": [
                {"date": (DAY - timedelta(days=i)).isoformat(), "sleep_hours": 4}
                for i in range(1, 7)
            ]
        }
    )
    check()
    pred = predict(w["id"], "viet")
    assert (
        "ROLLING_SLEEP_LOW" in pred["factor_codes"]
        or "ROLLING_SLEEP_VERY_LOW" in pred["factor_codes"]
    )
    assert pred["selected_candidate"] != "learned_easy"


def test_future_predictions_and_execution_rejected():
    setup()
    future = next(
        w
        for w in workouts()
        if w["date"] > DAY.isoformat() and w["current"]["distance_km"] > 0
    )
    with pytest.raises(HTTPException):
        predict(future["id"], "viet")
    with pytest.raises(HTTPException):
        execute(
            future["id"],
            Execution(distance_km=5, duration_seconds=2000, completed=True),
            "viet",
        )


def test_existing_outcome_metrics_receive_evaluated_execution():
    w = setup()
    check()
    p = predict(w["id"], "viet")
    decide(w["id"], Decision(choice="accept"), "viet")
    execute(
        w["id"],
        Execution(
            distance_km=p["recommended"]["distance_km"],
            duration_seconds=2000,
            completed=True,
            rpe=3,
        ),
        "viet",
    )
    evaluate(w["id"], "viet")
    with connect() as c:
        row = c.execute("SELECT * FROM outcomes").fetchone()
        assert row["completed"] == 1 and row["followed_recommendation"] == 1


def test_retrieved_cases_do_not_recursively_embed_full_context():
    w = setup()
    check()
    predict(w["id"], "viet")
    execute(
        w["id"], Execution(distance_km=5, duration_seconds=2000, completed=True), "viet"
    )
    evaluate(w["id"], "viet")
    obs = store.observations("viet")
    assert set(obs[0]["prediction"]["context"]) == {"daily_state"}


def test_prior_week_review_does_not_rewrite_current_traits():
    setup()
    current = learn("viet")
    weekly_review(week=DAY - timedelta(days=7))
    with connect() as c:
        saved = json.loads(
            c.execute(
                "SELECT trait_json FROM coach_traits WHERE name='easy_hr_pace'"
            ).fetchone()[0]
        )
    assert saved["as_of"] == current["easy_hr_pace"]["as_of"]


def test_decision_does_not_initialize_schema_inside_write_transaction(monkeypatch):
    from app.training_plan import get_goal

    w = setup()
    check()
    predict(w["id"], "viet")

    def real_lookup(athlete="viet"):
        get_goal(
            athlete
        )  # Production today() reads the goal and initializes the schema.
        return DAY

    monkeypatch.setattr(store, "today", real_lookup)
    assert decide(w["id"], Decision(choice="accept"), "viet")["choice"] == "accept"


def test_race_progress_requires_comparable_effort_and_caps_change():
    from app.race_prediction import training_progress
    def sample(day, pace, hr=140, rpe=3):
        return {'date': (DAY-timedelta(days=day)).isoformat(),
                'workout': {'kind': 'easy'},
                'execution': {'completed': True, 'pain': False,
                              'distance_km': 3600/pace, 'duration_seconds': 3600,
                              'average_hr': hr, 'rpe': rpe}}
    observations = [sample(d, 400) for d in [40, 35, 30]] + [sample(d, 360) for d in [15, 10, 5]]
    result = training_progress(observations)
    assert result['adjustment_fraction'] == -.03
    assert training_progress(observations, True)['adjustment_fraction'] == 0
    assert training_progress(observations[:5])['status'] == 'insufficient_data'
    for o in observations[3:]:
        o['execution']['average_hr'] = 160
    assert training_progress(observations)['status'] == 'insufficient_data'
    for o in observations:
        o['workout']['kind'] = 'threshold'
    assert training_progress(observations)['status'] == 'insufficient_data'


def test_completed_race_updates_forecast_but_easy_run_does_not(monkeypatch):
    from app.race_prediction import race_prediction
    setup()
    observation = {'date': (DAY-timedelta(days=1)).isoformat(),
                   'workout': {'kind': 'easy', 'distance_km': 42.195},
                   'execution': {'completed': True, 'pain': False,
                                 'distance_km': 42.195, 'duration_seconds': 14400}}
    monkeypatch.setattr(store, 'observations', lambda athlete: [observation])
    assert race_prediction()['status'] == 'unavailable'
    observation['workout']['kind'] = 'race'
    assert race_prediction()['predicted_seconds'] == 14400
    observation['execution']['completed'] = False
    assert race_prediction()['status'] == 'unavailable'
