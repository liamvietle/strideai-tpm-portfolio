from fastapi import FastAPI

from app.engine import evaluate_workout
from app.models import CoachingRecommendation, WorkoutInput

app = FastAPI(
    title="StrideAI v2",
    version="0.1.0",
    description="Milestone 1: deterministic coaching decision API.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/recommendations", response_model=CoachingRecommendation)
def create_recommendation(payload: WorkoutInput) -> CoachingRecommendation:
    return evaluate_workout(payload)
