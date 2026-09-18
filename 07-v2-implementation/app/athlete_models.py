"""Validated, optional athlete inputs; unknown values are never filled with zero."""

from datetime import date as Date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PB(StrictModel):
    distance_km: float = Field(gt=0, le=300)
    time_seconds: float = Field(gt=0, le=200000)
    date: Date | None = None


class HealthPoint(StrictModel):
    date: Date
    resting_hr: float | None = Field(None, ge=20, le=220)
    hrv_ms: float | None = Field(None, gt=0, le=500)
    sleep_hours: float | None = Field(None, ge=0, le=24)


class AthleteProfile(StrictModel):
    age: int | None = Field(None, ge=16, le=100)
    sex: Literal["female", "male", "intersex", "prefer_not_to_say"] | None = None
    gender: str | None = Field(None, max_length=80)
    height_cm: float | None = Field(None, ge=100, le=250)
    weight_kg: float | None = Field(None, ge=25, le=250)
    running_years: float | None = Field(None, ge=0, le=90)
    pbs: list[PB] = Field(default_factory=list, max_length=100)
    recent_weekly_km: float | None = Field(None, ge=0, le=250)
    resting_hr: float | None = Field(None, ge=20, le=220)
    hrv_ms: float | None = Field(None, gt=0, le=500)
    vo2max: float | None = Field(None, ge=10, le=100)
    threshold_pace: float | None = Field(
        None, ge=120, le=1200, description="seconds/km"
    )
    threshold_hr: float | None = Field(None, ge=60, le=230)
    max_hr: float | None = Field(None, ge=80, le=240)
    health_history: list[HealthPoint] = Field(default_factory=list, max_length=730)
    injury_history: str = Field("", max_length=2000)
    active_injury: bool = False
    constraints: str = Field("", max_length=2000)
    available_days: list[int] = Field(
        default_factory=lambda: [1, 3, 5], min_length=1, max_length=7
    )
    max_session_minutes: int = Field(60, ge=10, le=240)
    race_priority: Literal["A", "B", "C"] = "A"
    long_run_day: int | None = Field(None, ge=0, le=6)
    include_strength: bool = False
    strength_days: list[int] = Field(default_factory=list, max_length=3)

    @field_validator("available_days", "strength_days")
    @classmethod
    def valid_days(cls, v):
        if len(v) != len(set(v)) or any(d < 0 or d > 6 for d in v):
            raise ValueError("Use unique weekdays from Monday=0 to Sunday=6.")
        return sorted(v)

    @model_validator(mode="after")
    def heart_rates(self):
        if self.long_run_day is not None and self.long_run_day not in self.available_days:
            raise ValueError("Long-run day must be an available day.")
        if self.include_strength and not self.strength_days:
            raise ValueError("Choose one to three days for strength training; these can be non-running days.")
        if self.max_hr and self.threshold_hr and self.threshold_hr > self.max_hr:
            raise ValueError("Threshold HR cannot exceed maximum HR.")
        if self.resting_hr and self.max_hr and self.resting_hr >= self.max_hr:
            raise ValueError("Resting HR must be below maximum HR.")
        if len({p.date for p in self.health_history}) != len(self.health_history):
            raise ValueError("Health history needs unique dates.")
        return self


class GeneratePlan(StrictModel):
    start_date: Date | None = None
    start_mode: Literal["custom", "today", "next_monday", "recommended"] = "custom"
    duration_weeks: int | None = Field(None, ge=1, le=32)
    replace_existing: bool = False


class Decision(StrictModel):
    choice: Literal["accept", "decline"]


class Split(StrictModel):
    distance_km: float = Field(gt=0, le=100)
    duration_seconds: float = Field(gt=0, le=100000)
    average_hr: float | None = Field(None, ge=30, le=240)


class Execution(StrictModel):
    activity_id: int | None = Field(None, gt=0)
    distance_km: float | None = Field(None, ge=0, le=300)
    duration_seconds: float | None = Field(None, ge=0, le=200000)
    average_hr: float | None = Field(None, ge=30, le=240)
    rpe: float | None = Field(None, ge=0, le=10)
    pain: bool = False
    completed: bool
    splits: list[Split] = Field(default_factory=list, max_length=300)
    notes: str = Field("", max_length=2000)

    @model_validator(mode="after")
    def manual_metrics(self):
        if self.activity_id is None and (
            self.distance_km is None or self.duration_seconds is None
        ):
            raise ValueError(
                "Link a synced activity or provide distance and duration, including zero for a skipped run."
            )
        if (self.distance_km or 0) > 0 and self.duration_seconds == 0:
            raise ValueError("A run with distance needs a positive duration.")
        return self
