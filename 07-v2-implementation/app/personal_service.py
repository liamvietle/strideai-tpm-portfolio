from __future__ import annotations

from datetime import date, timedelta
import json

from fastapi import HTTPException

from app.accumulated_fatigue import evaluate_workout_v21
from app.daily_checkin_v2 import PlannedActivityType
from app.explanation import build_evidence_package, generate_explanation
from app.models import AccumulatedWorkoutInput, RecoverySnapshot
from app.observability import write_trace
from app.persisted_history import load_persisted_history
from app.personal_models import DailyCheckInInput, PersonalRecommendationResponse
from app.personal_storage import (
    attach_recommendation,
    calculate_recent_load_ratio,
    init_personal_app_db,
    prior_checkins,
    upsert_checkin,
)
from app.recovery_storage import upsert_recovery_day
from app.retrieval import load_history, retrieve_similar_history
from app.storage import connect, save_recommendation
from app.run_weather import forecast_guidance
from app.apple_health import enrich_with_apple_health, health_rows


def _day_index(checkin_date: str) -> int:
    return date.fromisoformat(checkin_date).toordinal()


def _locked_checkin_exists(athlete_id: str, checkin_date: str) -> bool:
    init_personal_app_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT recommendation_id FROM daily_checkins WHERE athlete_id=? AND checkin_date=?",
            (athlete_id, checkin_date),
        ).fetchone()
    return bool(row and row["recommendation_id"] is not None)


def _snapshot_from_row(row: dict) -> RecoverySnapshot:
    return RecoverySnapshot(
        day_index=_day_index(row["checkin_date"]),
        sleep_hours=row.get("sleep_hours"),
        hrv_ms=row.get("hrv_ms"),
        hrv_baseline_low=row.get("hrv_baseline_low"),
        hrv_baseline_high=row.get("hrv_baseline_high"),
        resting_hr_bpm=row.get("resting_hr_bpm"),
        soreness_0_10=row.get("soreness_0_10"),
        pain_flag=bool(row.get("pain_flag", False)),
        subjective_fatigue=row.get("subjective_fatigue", "normal"),
        recent_load_ratio=(
            row.get("recent_load_ratio")
            if row.get("recent_load_ratio") is not None
            else row.get("calculated_load_ratio")
        ),
    )


def build_accumulated_input(payload: DailyCheckInInput) -> tuple[AccumulatedWorkoutInput, float | None]:
    payload = enrich_with_apple_health(payload)
    calculated_load = calculate_recent_load_ratio(payload.athlete_id, payload.checkin_date)
    effective_load = payload.recent_load_ratio if payload.recent_load_ratio is not None else calculated_load
    start = (date.fromisoformat(payload.checkin_date) - timedelta(days=7)).isoformat()
    automatic_rows = health_rows(payload.athlete_id, start, payload.checkin_date)
    manual_rows = prior_checkins(payload.athlete_id, payload.checkin_date, days=7)
    merged = {row["checkin_date"]: row for row in automatic_rows}
    for row in manual_rows:
        base = merged.get(row["checkin_date"], {})
        merged[row["checkin_date"]] = {
            **base,
            **{key: value for key, value in row.items() if value is not None},
        }
    history_rows = [merged[key] for key in sorted(merged)]
    recovery_history = [_snapshot_from_row(row) for row in history_rows]

    return (
        AccumulatedWorkoutInput(
            athlete_id=payload.athlete_id,
            day_index=_day_index(payload.checkin_date),
            planned_distance_km=payload.planned_distance_km,
            planned_intensity=payload.planned_intensity or "easy",
            recent_load_ratio=effective_load,
            hrv_vs_baseline_pct=None,
            resting_hr_delta_bpm=None,
            sleep_hours=payload.sleep_hours,
            soreness_0_10=payload.soreness_0_10,
            pain_flag=payload.pain_flag,
            recent_race_days_ago=None,
            hrv_ms=payload.hrv_ms,
            hrv_baseline_low=payload.hrv_baseline_low,
            hrv_baseline_high=payload.hrv_baseline_high,
            resting_hr_bpm=payload.resting_hr_bpm,
            subjective_fatigue=payload.subjective_fatigue,
            days_until_event=payload.days_until_event,
            recovery_history=recovery_history,
        ),
        calculated_load,
    )


def create_personal_recommendation(payload: DailyCheckInInput) -> PersonalRecommendationResponse:
    payload = enrich_with_apple_health(payload)
    if payload.planned_activity_type != PlannedActivityType.run:
        calculated_load = calculate_recent_load_ratio(payload.athlete_id, payload.checkin_date)
        try:
            checkin_id = upsert_recovery_day(payload, calculated_load_ratio=calculated_load)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        label = "Rest day" if payload.planned_activity_type == PlannedActivityType.rest else payload.planned_activity_type.value.replace("_", " ").title()
        return PersonalRecommendationResponse(
            mode="recovery_only_checkin",
            checkin_id=checkin_id,
            calculated_load_ratio=calculated_load,
            message=f"{label} recovery check-in saved. It will contribute to your rolling recovery history for future running recommendations.",
        )

    if _locked_checkin_exists(payload.athlete_id, payload.checkin_date):
        raise HTTPException(
            status_code=409,
            detail="This morning decision is already locked. Record the outcome from History instead of regenerating it.",
        )

    accumulated_input, calculated_load = build_accumulated_input(payload)
    checkin_id = upsert_checkin(payload, calculated_load_ratio=calculated_load)

    recommendation, accumulated_fatigue = evaluate_workout_v21(accumulated_input)
    weather = forecast_guidance(payload.run_weather)
    if recommendation.action.value == 'recovery_only':
        weather['guidance'] = 'Follow recovery-only advice; a cooler forecast does not override pain or recovery concerns. ' + weather['guidance']
    history = [*load_history(), *load_persisted_history(payload.athlete_id)]
    retrieved = retrieve_similar_history(accumulated_input, recommendation, history=history)
    evidence = build_evidence_package(accumulated_input, recommendation, retrieved)
    explanation, trace = generate_explanation(evidence)
    write_trace(trace, athlete_id=payload.athlete_id, approved_action=recommendation.action)
    recommendation_id = save_recommendation(
        accumulated_input,
        recommendation,
        trace,
        explanation=explanation,
        evidence=evidence,
    )
    attach_recommendation(checkin_id, recommendation_id)
    with connect() as conn:
        conn.execute('INSERT INTO run_weather_decisions VALUES (?,?)', (recommendation_id, json.dumps(weather)))

    return PersonalRecommendationResponse(
        run_weather=weather,
        recommendation=recommendation,
        accumulated_fatigue=accumulated_fatigue,
        explanation=explanation,
        evidence=evidence,
        trace=trace,
        recommendation_id=recommendation_id,
        checkin_id=checkin_id,
        human_decision=payload.human_decision,
        calculated_load_ratio=calculated_load,
    )
