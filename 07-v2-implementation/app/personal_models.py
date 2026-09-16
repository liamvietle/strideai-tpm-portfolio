from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.daily_checkin_v2 import PlannedActivityType
from app.models import (
    AccumulatedFatigueAssessment,
    CoachingRecommendation,
    EvidencePackage,
    ExplanationTrace,
    RecommendationAction,
    SubjectiveFatigue,
)


class DailyCheckInInput(BaseModel):
    athlete_id: str = Field(default="viet", min_length=1)
    checkin_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    planned_activity_type: PlannedActivityType = PlannedActivityType.run
    planned_distance_km: float = Field(default=0, ge=0, le=300)
    planned_intensity: Optional[str] = None
    planned_activity_note: Optional[str] = Field(default=None, max_length=200)
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    hrv_ms: Optional[float] = Field(default=None, ge=0)
    hrv_baseline_low: Optional[float] = Field(default=None, ge=0)
    hrv_baseline_high: Optional[float] = Field(default=None, ge=0)
    resting_hr_bpm: Optional[float] = Field(default=None, ge=20, le=220)
    soreness_0_10: Optional[int] = Field(default=None, ge=0, le=10)
    pain_flag: bool = False
    subjective_fatigue: SubjectiveFatigue = SubjectiveFatigue.normal
    recent_load_ratio: Optional[float] = Field(default=None, ge=0)
    days_until_event: Optional[int] = Field(default=None, ge=0, le=365)
    human_decision: Optional[RecommendationAction] = None

    @model_validator(mode="after")
    def validate_session(self):
        if self.planned_activity_type == PlannedActivityType.run:
            if self.planned_distance_km <= 0:
                raise ValueError("Running check-ins require a planned distance greater than 0 km.")
            if self.planned_intensity not in {"easy", "moderate", "threshold", "interval", "race"}:
                raise ValueError("Running check-ins require a valid running intensity.")
            if self.human_decision is None:
                raise ValueError("Running check-ins require your decision before seeing StrideAI.")
        elif self.planned_activity_type == PlannedActivityType.rest:
            self.planned_distance_km = 0
            self.planned_intensity = None
            self.human_decision = None
        return self


class DailyCheckInRecord(DailyCheckInInput):
    id: int
    recommendation_id: Optional[int] = None
    calculated_load_ratio: Optional[float] = None
    created_at: str
    updated_at: str


class PersonalRecommendationResponse(BaseModel):
    mode: str = "recommendation"
    checkin_id: int
    human_decision: Optional[RecommendationAction] = None
    calculated_load_ratio: Optional[float] = None
    message: Optional[str] = None
    recommendation: Optional[CoachingRecommendation] = None
    accumulated_fatigue: Optional[AccumulatedFatigueAssessment] = None
    explanation: Optional[str] = None
    evidence: Optional[EvidencePackage] = None
    trace: Optional[ExplanationTrace] = None
    recommendation_id: Optional[int] = None
