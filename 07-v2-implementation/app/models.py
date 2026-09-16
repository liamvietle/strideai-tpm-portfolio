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


class SubjectiveFatigue(str, Enum):
    fresh = "fresh"
    normal = "normal"
    slightly_tired = "slightly_tired"
    tired = "tired"
    very_tired = "very_tired"


class AccumulatedFatigueState(str, Enum):
    low = "low"
    elevated = "elevated"
    high = "high"
    critical = "critical"


class OutcomeAssessment(str, Enum):
    warning_useful_directionally = "warning_useful_directionally"
    neutral_or_unknown = "neutral_or_unknown"
    false_alarm = "false_alarm"


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


class RecoverySnapshot(BaseModel):
    day_index: int = Field(ge=0)
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=24)
    hrv_ms: Optional[float] = Field(default=None, ge=0)
    hrv_baseline_low: Optional[float] = Field(default=None, ge=0)
    hrv_baseline_high: Optional[float] = Field(default=None, ge=0)
    resting_hr_bpm: Optional[float] = Field(default=None, ge=20, le=220)
    soreness_0_10: Optional[int] = Field(default=None, ge=0, le=10)
    pain_flag: bool = False
    subjective_fatigue: SubjectiveFatigue = SubjectiveFatigue.normal
    recent_load_ratio: Optional[float] = Field(default=None, ge=0)


class AccumulatedWorkoutInput(WorkoutInput):
    day_index: int = Field(ge=0)
    hrv_ms: Optional[float] = Field(default=None, ge=0)
    hrv_baseline_low: Optional[float] = Field(default=None, ge=0)
    hrv_baseline_high: Optional[float] = Field(default=None, ge=0)
    resting_hr_bpm: Optional[float] = Field(default=None, ge=20, le=220)
    subjective_fatigue: SubjectiveFatigue = SubjectiveFatigue.normal
    days_until_event: Optional[int] = Field(default=None, ge=0, le=365)
    recovery_history: List[RecoverySnapshot] = Field(default_factory=list)


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


class AccumulatedFatigueAssessment(BaseModel):
    state: AccumulatedFatigueState
    score: int = Field(ge=0)
    has_warning: bool
    observed_days_3: int = Field(ge=0, le=3)
    observed_days_7: int = Field(ge=0, le=7)
    average_sleep_3d: Optional[float] = Field(default=None, ge=0, le=24)
    average_sleep_7d: Optional[float] = Field(default=None, ge=0, le=24)
    low_sleep_observations_7d: int = Field(ge=0)
    very_low_sleep_observations_7d: int = Field(ge=0)
    hrv_status: str
    hrv_trend_pct: Optional[float] = None
    resting_hr_change_bpm: Optional[float] = None
    contributors: List[str]


class HistoricalCase(BaseModel):
    athlete_id: str
    session_date: str
    planned_intensity: str
    factor_codes: List[str]
    action: RecommendationAction
    outcome: str


class RetrievedCase(HistoricalCase):
    similarity_score: float = Field(ge=0)


class EvidencePackage(BaseModel):
    athlete_id: str
    planned_intensity: str
    approved_action: RecommendationAction
    volume_change_pct: int
    fatigue_state: FatigueState
    risk_level: RiskLevel
    confidence: float
    autonomy_mode: AutonomyMode
    factor_details: List[str]
    safety_flags: List[str]
    retrieved_context: List[RetrievedCase]


class ExplanationTrace(BaseModel):
    request_id: str
    provider: str
    model: str
    prompt_version: str
    latency_ms: int = Field(ge=0)
    retrieval_count: int = Field(ge=0)
    guardrail_passed: bool
    used_fallback: bool
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None


class CoachingResponse(BaseModel):
    recommendation: CoachingRecommendation
    explanation: str
    evidence: EvidencePackage
    trace: ExplanationTrace


class ActivityRecord(BaseModel):
    source: str
    source_activity_id: str
    athlete_id: str
    start_time: str
    activity_type: str
    name: Optional[str] = None
    distance_km: Optional[float] = Field(default=None, ge=0)
    duration_seconds: Optional[int] = Field(default=None, ge=0)
    average_hr: Optional[float] = Field(default=None, ge=0)
    max_hr: Optional[float] = Field(default=None, ge=0)
    calories: Optional[float] = Field(default=None, ge=0)
    raw_format: str
    raw_payload: Optional[str] = None


class ImportSummary(BaseModel):
    source: str
    format: str
    parsed: int
    inserted: int
    updated: int
    skipped: int


class OutcomeInput(BaseModel):
    completed: bool
    perceived_effort_0_10: Optional[int] = Field(default=None, ge=0, le=10)
    pain_after: bool = False
    followed_recommendation: Optional[bool] = None
    override_action: Optional[RecommendationAction] = None
    notes: Optional[str] = None


class EvaluationSummary(BaseModel):
    cases: int
    correct_actions: int
    action_accuracy: float
    safety_violations: int
    human_review_cases: int


class ExplanationQuality(BaseModel):
    action_consistent: bool
    evidence_support_rate: float = Field(ge=0, le=1)
    unsupported_numeric_claims: List[str]
    groundedness_score: float = Field(ge=0, le=1)
    grounded: bool


class ExplanationQualitySummary(BaseModel):
    evaluated: int
    grounded: int
    groundedness_rate: float = Field(ge=0, le=1)
    action_consistent: int
    action_consistency_rate: float = Field(ge=0, le=1)
    unsupported_numeric_claims: int
    average_groundedness_score: float = Field(ge=0, le=1)


class QualityEvaluationSummary(EvaluationSummary):
    explanations_grounded: int
    explanation_groundedness_rate: float = Field(ge=0, le=1)
    action_consistency_rate: float = Field(ge=0, le=1)
    unsupported_numeric_claims: int


class RegressionComparison(BaseModel):
    baseline_label: str
    candidate_label: str
    baseline_action_accuracy: float
    candidate_action_accuracy: float
    action_accuracy_delta: float
    baseline_safety_violations: int
    candidate_safety_violations: int
    safety_violation_delta: int
    explanation_groundedness_rate: float
    gate_passed: bool
    reasons: List[str]


class DeploymentMetrics(BaseModel):
    athlete_id: Optional[str] = None
    total_recommendations: int
    outcomes_recorded: int
    outcome_coverage_rate: float = Field(ge=0, le=1)
    follow_status_recorded: int
    followed_count: int
    overridden_count: int
    acceptance_rate: Optional[float] = Field(default=None, ge=0, le=1)
    override_rate: Optional[float] = Field(default=None, ge=0, le=1)
    completed_count: int
    completion_rate: Optional[float] = Field(default=None, ge=0, le=1)
    pain_after_count: int
    pain_after_rate: Optional[float] = Field(default=None, ge=0, le=1)
    average_perceived_effort: Optional[float] = Field(default=None, ge=0, le=10)
    human_review_recommendations: int
    human_review_rate: float = Field(ge=0, le=1)
    trace_coverage_rate: float = Field(ge=0, le=1)
    guardrail_pass_rate: Optional[float] = Field(default=None, ge=0, le=1)
    fallback_rate: Optional[float] = Field(default=None, ge=0, le=1)
    average_latency_ms: Optional[float] = Field(default=None, ge=0)


class RealValidationSummary(BaseModel):
    cases: int
    human_exact_agreement: int
    human_agreement_rate: float = Field(ge=0, le=1)
    warnings_issued: int
    action_changes: int
    useful_warning_cases: int
    useful_warnings_detected: int
    outcome_aligned_warning_rate: float = Field(ge=0, le=1)
    missed_deterioration: int
    false_alarms: int


class StoredActivity(ActivityRecord):
    id: int
    created_at: str
    updated_at: str


class PersistedCoachingResponse(CoachingResponse):
    recommendation_id: int


class V5CoachingResponse(CoachingResponse):
    recommendation_id: int
    accumulated_fatigue: AccumulatedFatigueAssessment
