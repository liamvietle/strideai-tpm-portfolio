from __future__ import annotations

from app.daily_checkin_v2 import DailyRecoveryCheckInInput, PlannedActivityType, RecoveryOnlyResponse
from app.personal_models import DailyCheckInInput, PersonalRecommendationResponse
from app.personal_service import create_personal_recommendation
from app.personal_storage import calculate_recent_load_ratio, upsert_recovery_checkin


def save_daily_checkin(
    payload: DailyRecoveryCheckInInput,
) -> PersonalRecommendationResponse | RecoveryOnlyResponse:
    if payload.planned_activity_type == PlannedActivityType.run:
        run_payload = DailyCheckInInput(
            athlete_id=payload.athlete_id,
            checkin_date=payload.checkin_date,
            planned_distance_km=payload.planned_distance_km,
            planned_intensity=payload.planned_intensity,
            sleep_hours=payload.sleep_hours,
            hrv_ms=payload.hrv_ms,
            hrv_baseline_low=payload.hrv_baseline_low,
            hrv_baseline_high=payload.hrv_baseline_high,
            resting_hr_bpm=payload.resting_hr_bpm,
            soreness_0_10=payload.soreness_0_10,
            pain_flag=payload.pain_flag,
            subjective_fatigue=payload.subjective_fatigue,
            recent_load_ratio=payload.recent_load_ratio,
            days_until_event=payload.days_until_event,
            human_decision=payload.human_decision,
        )
        return create_personal_recommendation(run_payload)

    calculated_load = calculate_recent_load_ratio(payload.athlete_id, payload.checkin_date)
    checkin_id = upsert_recovery_checkin(payload, calculated_load_ratio=calculated_load)
    label = "Rest day" if payload.planned_activity_type == PlannedActivityType.rest else payload.planned_activity_type.value.replace("_", " ").title()
    return RecoveryOnlyResponse(
        checkin_id=checkin_id,
        message=f"{label} recovery check-in saved. It will contribute to your rolling recovery history for future running recommendations.",
        calculated_load_ratio=calculated_load,
    )
