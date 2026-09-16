from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from app.engine import evaluate_workout
from app.explanation import build_evidence_package, generate_explanation
from app.ingestion import parse_garmin_summary_csv, parse_tcx
from app.models import (
    CoachingRecommendation,
    CoachingResponse,
    ImportSummary,
    OutcomeInput,
    PersistedCoachingResponse,
    StoredActivity,
    WorkoutInput,
)
from app.observability import write_trace
from app.retrieval import retrieve_similar_history
from app.storage import init_db, list_activities, save_outcome, save_recommendation, upsert_activities

app = FastAPI(
    title="StrideAI v2",
    version="0.3.0",
    description="Persistent running-data ingestion, deterministic coaching, retrieved context, and guarded LLM explanations.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/recommendations", response_model=CoachingRecommendation)
def create_v1_recommendation(payload: WorkoutInput) -> CoachingRecommendation:
    return evaluate_workout(payload)


def _create_v2_response(payload: WorkoutInput) -> CoachingResponse:
    recommendation = evaluate_workout(payload)
    history = retrieve_similar_history(payload, recommendation)
    evidence = build_evidence_package(payload, recommendation, history)
    explanation, trace = generate_explanation(evidence)
    write_trace(trace, athlete_id=payload.athlete_id, approved_action=recommendation.action)
    return CoachingResponse(
        recommendation=recommendation,
        explanation=explanation,
        evidence=evidence,
        trace=trace,
    )


@app.post("/v2/recommendations", response_model=CoachingResponse)
def create_v2_recommendation(payload: WorkoutInput) -> CoachingResponse:
    return _create_v2_response(payload)


@app.post("/v3/recommendations", response_model=PersistedCoachingResponse)
def create_v3_recommendation(payload: WorkoutInput) -> PersistedCoachingResponse:
    response = _create_v2_response(payload)
    init_db()
    recommendation_id = save_recommendation(payload, response.recommendation, response.trace)
    return PersistedCoachingResponse(
        **response.model_dump(),
        recommendation_id=recommendation_id,
    )


@app.put("/v3/recommendations/{recommendation_id}/outcome")
def record_outcome(recommendation_id: int, payload: OutcomeInput) -> dict[str, object]:
    init_db()
    save_outcome(recommendation_id, payload)
    return {"recommendation_id": recommendation_id, "saved": True}


@app.post("/v3/activities/import/tcx", response_model=ImportSummary)
async def import_tcx_activity(
    athlete_id: str,
    file: UploadFile = File(...),
    source: str = Query(default="garmin", pattern="^(garmin|strava|other)$"),
) -> ImportSummary:
    try:
        content = (await file.read()).decode("utf-8-sig")
        records = parse_tcx(content, athlete_id=athlete_id, source=source)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid TCX export: {exc}") from exc
    init_db()
    inserted, updated = upsert_activities(records)
    return ImportSummary(
        source=source,
        format="tcx",
        parsed=len(records),
        inserted=inserted,
        updated=updated,
        skipped=max(0, len(records) - inserted - updated),
    )


@app.post("/v3/activities/import/garmin-csv", response_model=ImportSummary)
async def import_garmin_csv_activity(
    athlete_id: str,
    file: UploadFile = File(...),
) -> ImportSummary:
    try:
        content = (await file.read()).decode("utf-8-sig")
        records = parse_garmin_summary_csv(content, athlete_id=athlete_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Garmin CSV export: {exc}") from exc
    init_db()
    inserted, updated = upsert_activities(records)
    return ImportSummary(
        source="garmin",
        format="garmin-csv",
        parsed=len(records),
        inserted=inserted,
        updated=updated,
        skipped=max(0, len(records) - inserted - updated),
    )


@app.get("/v3/activities", response_model=list[StoredActivity])
def get_activities(athlete_id: str, limit: int = Query(default=100, ge=1, le=1000)) -> list[StoredActivity]:
    init_db()
    return [StoredActivity(**row) for row in list_activities(athlete_id, limit=limit)]
