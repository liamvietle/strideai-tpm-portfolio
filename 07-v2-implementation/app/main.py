from fastapi import FastAPI

from app.engine import evaluate_workout
from app.explanation import build_evidence_package, generate_explanation
from app.models import CoachingRecommendation, CoachingResponse, WorkoutInput
from app.observability import write_trace
from app.retrieval import retrieve_similar_history

app = FastAPI(
    title="StrideAI v2",
    version="0.2.0",
    description="Deterministic coaching decisions with retrieved context and guarded LLM explanations.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/recommendations", response_model=CoachingRecommendation)
def create_v1_recommendation(payload: WorkoutInput) -> CoachingRecommendation:
    return evaluate_workout(payload)


@app.post("/v2/recommendations", response_model=CoachingResponse)
def create_v2_recommendation(payload: WorkoutInput) -> CoachingResponse:
    recommendation = evaluate_workout(payload)
    history = retrieve_similar_history(payload, recommendation)
    evidence = build_evidence_package(payload, recommendation, history)
    explanation, trace = generate_explanation(evidence)
    write_trace(
        trace,
        athlete_id=payload.athlete_id,
        approved_action=recommendation.action,
    )
    return CoachingResponse(
        recommendation=recommendation,
        explanation=explanation,
        evidence=evidence,
        trace=trace,
    )
