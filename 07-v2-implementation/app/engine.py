from __future__ import annotations

from app.models import (
    AutonomyMode,
    CoachingRecommendation,
    DecisionFactor,
    FatigueState,
    RecommendationAction,
    RiskLevel,
    WorkoutInput,
)

RULES_VERSION = "v2-m1.0"


def _factor(code: str, severity: int, detail: str) -> DecisionFactor:
    return DecisionFactor(code=code, severity=severity, detail=detail)


def evaluate_workout(data: WorkoutInput) -> CoachingRecommendation:
    factors: list[DecisionFactor] = []
    safety_flags: list[str] = []

    if data.pain_flag:
        safety_flags.append("pain_reported")
        factors.append(_factor("PAIN_FLAG", 3, "Pain was reported; automatic training progression is blocked."))

    if data.soreness_0_10 is not None and data.soreness_0_10 >= 8:
        safety_flags.append("severe_soreness")
        factors.append(_factor("SEVERE_SORENESS", 3, f"Soreness is {data.soreness_0_10}/10."))

    if data.recent_race_days_ago is not None and data.recent_race_days_ago <= 2:
        factors.append(_factor("RECENT_RACE", 2, f"Race occurred {data.recent_race_days_ago} day(s) ago."))

    if data.hrv_vs_baseline_pct is not None:
        if data.hrv_vs_baseline_pct <= -20:
            factors.append(_factor("HRV_LOW", 3, f"HRV is {abs(data.hrv_vs_baseline_pct):.0f}% below baseline."))
        elif data.hrv_vs_baseline_pct <= -10:
            factors.append(_factor("HRV_BELOW_BASELINE", 2, f"HRV is {abs(data.hrv_vs_baseline_pct):.0f}% below baseline."))

    if data.resting_hr_delta_bpm is not None:
        if data.resting_hr_delta_bpm >= 10:
            factors.append(_factor("RHR_HIGH", 3, f"Resting HR is +{data.resting_hr_delta_bpm:.0f} bpm above baseline."))
        elif data.resting_hr_delta_bpm >= 5:
            factors.append(_factor("RHR_ELEVATED", 2, f"Resting HR is +{data.resting_hr_delta_bpm:.0f} bpm above baseline."))

    if data.sleep_hours is not None:
        if data.sleep_hours < 5:
            factors.append(_factor("SLEEP_VERY_LOW", 3, f"Sleep was {data.sleep_hours:.1f} h."))
        elif data.sleep_hours < 6.5:
            factors.append(_factor("SLEEP_LOW", 2, f"Sleep was {data.sleep_hours:.1f} h."))

    if data.recent_load_ratio is not None:
        if data.recent_load_ratio >= 1.5:
            factors.append(_factor("LOAD_SPIKE", 3, f"Recent load ratio is {data.recent_load_ratio:.2f}."))
        elif data.recent_load_ratio >= 1.3:
            factors.append(_factor("LOAD_ELEVATED", 2, f"Recent load ratio is {data.recent_load_ratio:.2f}."))

    if data.soreness_0_10 is not None:
        if 6 <= data.soreness_0_10 < 8:
            factors.append(_factor("SORENESS_HIGH", 2, f"Soreness is {data.soreness_0_10}/10."))
        elif 4 <= data.soreness_0_10 < 6:
            factors.append(_factor("SORENESS_ELEVATED", 1, f"Soreness is {data.soreness_0_10}/10."))

    critical_inputs = [
        data.hrv_vs_baseline_pct,
        data.resting_hr_delta_bpm,
        data.sleep_hours,
        data.recent_load_ratio,
    ]
    present_count = sum(v is not None for v in critical_inputs)
    confidence = round(0.45 + 0.125 * present_count, 2)
    if data.soreness_0_10 is not None:
        confidence = min(1.0, round(confidence + 0.05, 2))

    if safety_flags:
        return CoachingRecommendation(
            fatigue_state=FatigueState.high,
            risk_level=RiskLevel.high,
            confidence=max(confidence, 0.8),
            autonomy_mode=AutonomyMode.human_review,
            action=RecommendationAction.recovery_only,
            volume_change_pct=-100,
            decision_factors=factors,
            safety_flags=safety_flags,
            rules_version=RULES_VERSION,
        )

    if present_count < 2:
        return CoachingRecommendation(
            fatigue_state=FatigueState.unknown,
            risk_level=RiskLevel.moderate,
            confidence=confidence,
            autonomy_mode=AutonomyMode.human_review,
            action=RecommendationAction.no_change_due_to_missing_data,
            volume_change_pct=0,
            decision_factors=factors,
            safety_flags=safety_flags,
            rules_version=RULES_VERSION,
        )

    score = sum(f.severity for f in factors)

    if score >= 7:
        fatigue_state = FatigueState.high
        risk_level = RiskLevel.high
        action = RecommendationAction.recovery_only
        volume_change_pct = -60
    elif score >= 4:
        fatigue_state = FatigueState.elevated
        risk_level = RiskLevel.moderate
        action = RecommendationAction.reduce_volume
        volume_change_pct = -25
    elif score >= 2:
        fatigue_state = FatigueState.elevated
        risk_level = RiskLevel.moderate
        action = RecommendationAction.reduce_intensity
        volume_change_pct = -10
    else:
        fatigue_state = FatigueState.normal
        risk_level = RiskLevel.low
        action = RecommendationAction.maintain
        volume_change_pct = 0

    if confidence >= 0.85 and risk_level == RiskLevel.low:
        autonomy_mode = AutonomyMode.automatic
    elif confidence >= 0.7 and risk_level != RiskLevel.high:
        autonomy_mode = AutonomyMode.confirm
    else:
        autonomy_mode = AutonomyMode.human_review

    return CoachingRecommendation(
        fatigue_state=fatigue_state,
        risk_level=risk_level,
        confidence=confidence,
        autonomy_mode=autonomy_mode,
        action=action,
        volume_change_pct=volume_change_pct,
        decision_factors=factors,
        safety_flags=safety_flags,
        rules_version=RULES_VERSION,
    )
