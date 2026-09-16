from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class FatigueState(str, Enum):
    normal = "normal"
    elevated = "elevated"
    high = "high"
    unknown = "unknown"


class RiskLevel(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"


class AutonomyMode(str, Enum):
    automatic = "automatic"
    confirm = "confirm"
    human_review = "human_review"


class RecommendationAction(str, Enum):
    maintain = "maintain"
    reduce_volume = "reduce_volume"
    reduce_intensity = "reduce_intensity"
    recovery_only = "recovery_only"
    no_change_due_to_missing_data = "no_change_due_to_missing_data"


class WorkoutInput(BaseModel):
    athlete_id: str = Field(min_length=1)
    planned_distance_km: float = Field(gt=0, le=100)
    planned_intensity: str = Field(description="easy, moderate, threshold, interval, race")
    recent_load_ratio: Optional[float] = Field(default=None, ge=0)
    hrv_vs_baseline_pct: Optional[float] = Field(default=None, ge=-100, le=100)
    resting_hr_delta_bpm: Optional[float] = Field(default=None, ge=-30, le=50)
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    soreness_0_10: Optional[int] = Field(default=None, ge=0, le=10)
    pain_flag: bool = False
    recent_race_days_ago: Optional[int] = Field(default=None, ge=0, le=365)


class DecisionFactor(BaseModel):
    code: str
    severity: int = Field(ge=0, le=3)
    detail: str


class CoachingRecommendation(BaseModel):
    fatigue_state: FatigueState
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    autonomy_mode: AutonomyMode
    action: RecommendationAction
    volume_change_pct: int = Field(ge=-100, le=0)
    decision_factors: List[DecisionFactor]
    safety_flags: List[str]
    rules_version: str
