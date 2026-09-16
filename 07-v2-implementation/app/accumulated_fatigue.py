from __future__ import annotations

from statistics import mean, median

from app.models import (
    AccumulatedFatigueAssessment,
    AccumulatedFatigueState,
    AccumulatedWorkoutInput,
    AutonomyMode,
    CoachingRecommendation,
    DecisionFactor,
    FatigueState,
    RecommendationAction,
    RecoverySnapshot,
    RiskLevel,
    SubjectiveFatigue,
)

RULES_VERSION = "v2.1-m5.0"

CONTRIBUTOR_DETAILS: dict[str, tuple[int, str]] = {
    "CURRENT_SLEEP_VERY_LOW": (1, "Current sleep is below 5 hours."),
    "CURRENT_SLEEP_LOW": (1, "Current sleep is below 6 hours."),
    "ROLLING_SLEEP_VERY_LOW": (2, "Observed 7-day sleep average is below 4.5 hours."),
    "ROLLING_SLEEP_LOW": (1, "Observed 7-day sleep average is below 5.5 hours."),
    "REPEATED_LOW_SLEEP": (1, "At least four observed days in the 7-day window are below 6 hours of sleep."),
    "REPEATED_VERY_LOW_SLEEP": (1, "At least three observed days in the 7-day window are below 5 hours of sleep."),
    "HRV_BELOW_BASELINE": (2, "Current HRV is below the Garmin baseline range."),
    "HRV_WELL_BELOW_BASELINE": (3, "Current HRV is more than 10% below the Garmin baseline lower bound."),
    "HRV_DECLINING": (1, "HRV has declined by at least 10% across the latest three observations."),
    "HRV_STEEPLY_DECLINING": (2, "HRV has declined by at least 20% across the latest three observations."),
    "RHR_RISING": (1, "Resting HR is at least 4 bpm above the median of recent observations."),
    "RHR_HIGH": (2, "Resting HR is at least 7 bpm above the median of recent observations."),
    "SUBJECTIVE_SLIGHTLY_TIRED": (1, "Subjective readiness is slightly tired."),
    "SUBJECTIVE_TIRED": (2, "Subjective readiness is tired."),
    "SUBJECTIVE_VERY_TIRED": (3, "Subjective readiness is very tired."),
    "SORENESS_ELEVATED": (1, "Soreness is elevated."),
    "SORENESS_HIGH": (2, "Soreness is high."),
    "LOAD_ELEVATED": (1, "Recent load ratio is at least 1.30."),
    "LOAD_SPIKE": (2, "Recent load ratio is at least 1.50."),
    "EVENT_PROXIMITY": (1, "A target event is within three days while recovery debt is already elevated."),
    "PAIN_FLAG": (3, "Pain was reported; automatic training progression is blocked."),
    "SEVERE_SORENESS": (3, "Severe soreness was reported; automatic training progression is blocked."),
}


def _current_snapshot(data: AccumulatedWorkoutInput) -> RecoverySnapshot:
    return RecoverySnapshot(
        day_index=data.day_index,
        sleep_hours=data.sleep_hours,
        hrv_ms=data.hrv_ms,
        hrv_baseline_low=data.hrv_baseline_low,
        hrv_baseline_high=data.hrv_baseline_high,
        resting_hr_bpm=data.resting_hr_bpm,
        soreness_0_10=data.soreness_0_10,
        pain_flag=data.pain_flag,
        subjective_fatigue=data.subjective_fatigue,
        recent_load_ratio=data.recent_load_ratio,
    )


def _timeline(data: AccumulatedWorkoutInput) -> list[RecoverySnapshot]:
    by_day = {item.day_index: item for item in data.recovery_history if item.day_index < data.day_index}
    by_day[data.day_index] = _current_snapshot(data)
    return [by_day[key] for key in sorted(by_day)]


def _window(timeline: list[RecoverySnapshot], current_day: int, days: int) -> list[RecoverySnapshot]:
    return [item for item in timeline if 0 <= current_day - item.day_index < days]


def assess_accumulated_fatigue(data: AccumulatedWorkoutInput) -> AccumulatedFatigueAssessment:
    timeline = _timeline(data)
    window3 = _window(timeline, data.day_index, 3)
    window7 = _window(timeline, data.day_index, 7)
    score = 0
    contributors: list[str] = []

    def add(code: str) -> None:
        nonlocal score
        if code in contributors:
            return
        contributors.append(code)
        score += CONTRIBUTOR_DETAILS[code][0]

    if data.sleep_hours is not None:
        if data.sleep_hours < 5:
            add("CURRENT_SLEEP_VERY_LOW")
        elif data.sleep_hours < 6:
            add("CURRENT_SLEEP_LOW")

    sleeps7 = [item.sleep_hours for item in window7 if item.sleep_hours is not None]
    average_sleep_7d = round(mean(sleeps7), 2) if sleeps7 else None
    sleeps3 = [item.sleep_hours for item in window3 if item.sleep_hours is not None]
    average_sleep_3d = round(mean(sleeps3), 2) if sleeps3 else None
    low_sleep = sum(value < 6 for value in sleeps7)
    very_low_sleep = sum(value < 5 for value in sleeps7)

    # Require at least three observed days before treating short sleep as accumulated debt.
    if len(sleeps7) >= 3 and average_sleep_7d is not None:
        if average_sleep_7d < 4.5:
            add("ROLLING_SLEEP_VERY_LOW")
        elif average_sleep_7d < 5.5:
            add("ROLLING_SLEEP_LOW")
        if low_sleep >= 4:
            add("REPEATED_LOW_SLEEP")
        if very_low_sleep >= 3:
            add("REPEATED_VERY_LOW_SLEEP")

    hrv_status = "unknown"
    if (
        data.hrv_ms is not None
        and data.hrv_baseline_low is not None
        and data.hrv_baseline_high is not None
        and data.hrv_baseline_high >= data.hrv_baseline_low
    ):
        if data.hrv_ms < data.hrv_baseline_low:
            hrv_status = "below_baseline"
            if data.hrv_ms < data.hrv_baseline_low * 0.9:
                add("HRV_WELL_BELOW_BASELINE")
            else:
                add("HRV_BELOW_BASELINE")
        elif data.hrv_ms > data.hrv_baseline_high:
            hrv_status = "above_baseline"
        else:
            hrv_status = "within_baseline"

    hrv_values = [item.hrv_ms for item in timeline if item.hrv_ms is not None]
    hrv_trend_pct = None
    if len(hrv_values) >= 3 and hrv_values[-3] > 0:
        hrv_trend_pct = round((hrv_values[-1] - hrv_values[-3]) / hrv_values[-3] * 100, 1)
        if hrv_trend_pct <= -20:
            add("HRV_STEEPLY_DECLINING")
        elif hrv_trend_pct <= -10:
            add("HRV_DECLINING")

    prior_rhr = [
        item.resting_hr_bpm
        for item in timeline[:-1][-3:]
        if item.resting_hr_bpm is not None
    ]
    resting_hr_change_bpm = None
    if data.resting_hr_bpm is not None and len(prior_rhr) >= 2:
        resting_hr_change_bpm = round(data.resting_hr_bpm - median(prior_rhr), 1)
        if resting_hr_change_bpm >= 7:
            add("RHR_HIGH")
        elif resting_hr_change_bpm >= 4:
            add("RHR_RISING")

    subjective_map = {
        SubjectiveFatigue.slightly_tired: "SUBJECTIVE_SLIGHTLY_TIRED",
        SubjectiveFatigue.tired: "SUBJECTIVE_TIRED",
        SubjectiveFatigue.very_tired: "SUBJECTIVE_VERY_TIRED",
    }
    if data.subjective_fatigue in subjective_map:
        add(subjective_map[data.subjective_fatigue])

    if data.soreness_0_10 is not None:
        if data.soreness_0_10 >= 8:
            add("SEVERE_SORENESS")
        elif data.soreness_0_10 >= 6:
            add("SORENESS_HIGH")
        elif data.soreness_0_10 >= 4:
            add("SORENESS_ELEVATED")

    if data.pain_flag:
        add("PAIN_FLAG")

    if data.recent_load_ratio is not None:
        if data.recent_load_ratio >= 1.5:
            add("LOAD_SPIKE")
        elif data.recent_load_ratio >= 1.3:
            add("LOAD_ELEVATED")

    if data.days_until_event is not None and data.days_until_event <= 3 and score >= 3:
        add("EVENT_PROXIMITY")

    if score == 0:
        state = AccumulatedFatigueState.low
    elif score <= 2:
        state = AccumulatedFatigueState.elevated
    elif score <= 5:
        state = AccumulatedFatigueState.high
    else:
        state = AccumulatedFatigueState.critical

    return AccumulatedFatigueAssessment(
        state=state,
        score=score,
        has_warning=score > 0,
        observed_days_3=len({item.day_index for item in window3}),
        observed_days_7=len({item.day_index for item in window7}),
        average_sleep_3d=average_sleep_3d,
        average_sleep_7d=average_sleep_7d,
        low_sleep_observations_7d=low_sleep,
        very_low_sleep_observations_7d=very_low_sleep,
        hrv_status=hrv_status,
        hrv_trend_pct=hrv_trend_pct,
        resting_hr_change_bpm=resting_hr_change_bpm,
        contributors=contributors,
    )


def evaluate_workout_v21(
    data: AccumulatedWorkoutInput,
) -> tuple[CoachingRecommendation, AccumulatedFatigueAssessment]:
    assessment = assess_accumulated_fatigue(data)
    hard_safety = data.pain_flag or (data.soreness_0_10 is not None and data.soreness_0_10 >= 8)

    factors = [
        DecisionFactor(
            code=code,
            severity=CONTRIBUTOR_DETAILS[code][0],
            detail=CONTRIBUTOR_DETAILS[code][1],
        )
        for code in assessment.contributors
    ]

    safety_flags: list[str] = []
    if data.pain_flag:
        safety_flags.append("pain_reported")
    if data.soreness_0_10 is not None and data.soreness_0_10 >= 8:
        safety_flags.append("severe_soreness")

    if hard_safety:
        action = RecommendationAction.recovery_only
        volume_change_pct = -100
        risk_level = RiskLevel.high
        fatigue_state = FatigueState.high
        autonomy_mode = AutonomyMode.human_review
    elif assessment.score <= 2:
        action = RecommendationAction.maintain
        volume_change_pct = 0
        risk_level = RiskLevel.low if assessment.score == 0 else RiskLevel.moderate
        fatigue_state = FatigueState.normal if assessment.score == 0 else FatigueState.elevated
        autonomy_mode = AutonomyMode.automatic if assessment.score == 0 else AutonomyMode.confirm
    elif assessment.score <= 5:
        action = RecommendationAction.reduce_intensity
        volume_change_pct = -10
        risk_level = RiskLevel.moderate
        fatigue_state = FatigueState.elevated
        autonomy_mode = AutonomyMode.confirm
    else:
        action = RecommendationAction.reduce_volume
        volume_change_pct = -25
        risk_level = RiskLevel.high
        fatigue_state = FatigueState.high
        autonomy_mode = AutonomyMode.human_review

    present = sum(
        value is not None
        for value in (
            data.sleep_hours,
            data.hrv_ms,
            data.hrv_baseline_low,
            data.hrv_baseline_high,
            data.resting_hr_bpm,
            data.soreness_0_10,
            data.recent_load_ratio,
        )
    )
    confidence = min(0.95, round(0.5 + present * 0.04 + min(assessment.observed_days_7, 5) * 0.03, 2))

    return (
        CoachingRecommendation(
            fatigue_state=fatigue_state,
            risk_level=risk_level,
            confidence=confidence,
            autonomy_mode=autonomy_mode,
            action=action,
            volume_change_pct=volume_change_pct,
            decision_factors=factors,
            safety_flags=safety_flags,
            rules_version=RULES_VERSION,
        ),
        assessment,
    )
