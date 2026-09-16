from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models import RecommendationAction, SubjectiveFatigue, V5CoachingResponse


class DailyCheckInInput(BaseModel):
    athlete_id: str = Field(default="viet", min_length=1)
    checkin_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    planned_distance_km: float = Field(gt=0, le=100)
    planned_intensity: str = Field(pattern=r"^(easy|moderate|threshold|interval|race)$")
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
    human_decision: RecommendationAction


class DailyCheckInRecord(DailyCheckInInput):
    id: int
    recommendation_id: Optional[int] = None
    calculated_load_ratio: Optional[float] = None
    created_at: str
    updated_at: str


class PersonalRecommendationResponse(V5CoachingResponse):
    checkin_id: int
    human_decision: RecommendationAction
    calculated_load_ratio: Optional[float] = None
