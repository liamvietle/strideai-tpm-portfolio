from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.models import RecommendationAction, SubjectiveFatigue


class PlannedActivityType(str, Enum):
    run = "run"
    rest = "rest"
    strength = "strength"
    cycling = "cycling"
    tennis = "tennis"
    football = "football"
    other = "other"


class DailyRecoveryCheckInInput(BaseModel):
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
            allowed = {"easy", "moderate", "threshold", "interval", "race"}
            if self.planned_intensity not in allowed:
                raise ValueError("Running check-ins require a valid running intensity.")
            if self.human_decision is None:
                raise ValueError("Running check-ins require your decision before seeing StrideAI.")
        elif self.planned_activity_type == PlannedActivityType.rest:
            self.planned_distance_km = 0
            self.planned_intensity = None
            self.human_decision = None
        return self


class RecoveryOnlyResponse(BaseModel):
    checkin_id: int
    mode: str = "recovery_only_checkin"
    message: str
    calculated_load_ratio: Optional[float] = None
