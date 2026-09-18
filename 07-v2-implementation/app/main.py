from __future__ import annotations

import hmac
import os

import httpx
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.accumulated_fatigue import evaluate_workout_v21
from app.activity_weather import enrich_weather, recent_activities
from app.dashboard import DASHBOARD_HTML
from app.journey import router as journey_router
from app.journey_ui import enhance_journey_ui
from app.engine import evaluate_workout
from app.explanation import build_evidence_package, generate_explanation
from app.ingestion import parse_garmin_summary_csv, parse_tcx
from app.models import (
    AccumulatedWorkoutInput,
    CoachingRecommendation,
    CoachingResponse,
    DeploymentMetrics,
    ExplanationQualitySummary,
    ImportSummary,
    OutcomeInput,
    PersistedCoachingResponse,
    StoredActivity,
    V5CoachingResponse,
    WorkoutInput,
)
from app.observability import write_trace
from app.persisted_history import load_persisted_history
from app.personal_history import list_personal_history
from app.personal_models import DailyCheckInInput, PersonalRecommendationResponse
from app.personal_service import create_personal_recommendation
from app.personal_storage import init_personal_app_db
from app.personal_ui import PERSONAL_APP_HTML
from app.privacy import PRIVACY_HTML
from app.quality import summarize_explanation_records
from app.retrieval import load_history, retrieve_similar_history
from app.storage import (
    get_deployment_metrics,
    init_db,
    list_activities,
    list_explanation_records,
    save_outcome,
    save_recommendation,
    upsert_activities,
)
from app.strava_integration import (
    complete_authorization,
    create_authorization_url,
    disconnect_strava,
    init_strava_db,
    strava_status,
    sync_strava_activities,
)
from app.strava_ui import enhance_personal_app
from app.training_plan import RaceGoal, PlanImport, get_goal, save_goal, save_plan, plan_progress
from app.run_weather import RunWeatherInput, find_places, forecast_guidance
from app.plan_ui import enhance_plan_ui
from app.athlete_api import router as athlete_router
from app.athlete_store import init_athlete_db
from app.athlete_ui import enhance_athlete_ui
from app.apple_health import (
    AppleHealthSyncInput,
    AppleHealthSyncResult,
    apple_health_status,
    daily_state as apple_health_daily_state,
    delete_apple_health,
    init_apple_health_db,
    upsert_apple_health,
)

app = FastAPI(
    title="StrideAI",
    version="1.1.0-personal",
    description="Personal AI-assisted running coach with accumulated-recovery assessment, Strava activity sync, guarded explanations, outcome feedback, and real-world validation.",
)

app.include_router(athlete_router)

APP_KEY = os.getenv("STRIDEAI_APP_KEY", "").strip()
PUBLIC_PATHS = {"/", "/app", "/privacy", "/health", "/app/api/strava/callback"}


@app.middleware("http")
async def optional_personal_access_key(request: Request, call_next):
    """Protect personal data when STRIDEAI_APP_KEY is configured.

    The app shell, health endpoint and OAuth callback stay public. The callback
    is protected by a short-lived one-time OAuth state stored in SQLite.
    """
    if APP_KEY and request.url.path not in PUBLIC_PATHS:
        supplied = request.headers.get("X-StrideAI-Key", "")
        if not hmac.compare_digest(supplied, APP_KEY):
            return JSONResponse(status_code=401, content={"detail": "StrideAI access key required."})
    return await call_next(request)


@app.on_event("startup")
def initialize() -> None:
    init_personal_app_db()
    init_strava_db()
    init_athlete_db()
    init_apple_health_db()


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/app")


app.include_router(journey_router)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
def personal_app() -> str:
    return enhance_journey_ui(enhance_athlete_ui(enhance_plan_ui(enhance_personal_app(PERSONAL_APP_HTML))))


@app.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
def privacy_policy() -> str:
    return PRIVACY_HTML


@app.get('/app/api/plan')
def get_training_progress(athlete_id: str = 'viet'):
    return plan_progress(athlete_id)


@app.put('/app/api/goal')
def update_race_goal(payload: RaceGoal, athlete_id: str = 'viet'):
    return save_goal(payload, athlete_id)


@app.post('/app/api/plan')
def import_training_plan(payload: PlanImport, athlete_id: str = 'viet'):
    return save_plan(payload, athlete_id)


@app.get('/app/api/weather/places')
def weather_places(name: str = Query(min_length=2, max_length=100)):
    try:
        return find_places(name)
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, 'Location search unavailable. Please try again.')


@app.post('/app/api/weather/forecast')
def next_run_forecast(payload: RunWeatherInput):
    return forecast_guidance(payload)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.post("/app/api/recommendations", response_model=PersonalRecommendationResponse)
def personal_recommendation(payload: DailyCheckInInput) -> PersonalRecommendationResponse:
    return create_personal_recommendation(payload)


@app.get("/app/api/history")
def personal_history(
    athlete_id: str = "viet",
    limit: int = Query(default=30, ge=1, le=365),
) -> list[dict]:
    return list_personal_history(athlete_id, limit=limit)


@app.get("/app/api/strava/status")
def get_strava_status(athlete_id: str = "viet") -> dict[str, object]:
    return strava_status(athlete_id)


@app.get("/app/api/strava/auth-url")
def get_strava_auth_url(athlete_id: str = "viet") -> dict[str, str]:
    try:
        return {"url": create_authorization_url(athlete_id)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/app/api/strava/callback", include_in_schema=False)
def strava_callback(
    code: str | None = None,
    state: str | None = None,
    scope: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    if error or not code or not state:
        return RedirectResponse(url="/app?strava=denied")
    try:
        complete_authorization(code=code, state=state, scope=scope)
    except Exception:
        return RedirectResponse(url="/app?strava=error")
    return RedirectResponse(url="/app?strava=connected")


@app.post("/app/api/strava/sync")
def sync_strava(background_tasks: BackgroundTasks, athlete_id: str = "viet") -> dict[str, object]:
    try:
        result = sync_strava_activities(athlete_id)
        background_tasks.add_task(enrich_weather, athlete_id)
        return result
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(status_code=502, detail=f"Strava API returned HTTP {status}.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail='Strava could not be reached. Your saved data is unchanged; try syncing again shortly.') from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/app/api/strava/connection")
def remove_strava_connection(athlete_id: str = "viet") -> dict[str, bool]:
    disconnect_strava(athlete_id)
    return {"disconnected": True}


@app.get("/app/api/activities")
def get_recent_activities(
    athlete_id: str = "viet", limit: int = Query(default=30, ge=1, le=100),
) -> list[dict]:
    return recent_activities(athlete_id, limit)


@app.post("/app/api/apple-health/sync", response_model=AppleHealthSyncResult)
def sync_apple_health(payload: AppleHealthSyncInput) -> AppleHealthSyncResult:
    return upsert_apple_health(payload)


@app.get("/app/api/apple-health/status")
def get_apple_health_status(athlete_id: str = "viet") -> dict:
    return apple_health_status(athlete_id)


@app.get("/app/api/apple-health/daily-state")
def get_apple_health_daily_state(
    health_date: str = Query(alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    athlete_id: str = "viet",
) -> dict:
    try:
        state = apple_health_daily_state(athlete_id, health_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid health summary date.") from exc
    return {"available": state is not None, "state": state}


@app.delete("/app/api/apple-health/data")
def remove_apple_health_data(athlete_id: str = "viet") -> dict[str, int | bool]:
    deleted = delete_apple_health(athlete_id)
    return {"deleted": deleted, "disconnected": True}


@app.post("/v1/recommendations", response_model=CoachingRecommendation)
def create_v1_recommendation(payload: WorkoutInput) -> CoachingRecommendation:
    return evaluate_workout(payload)


def _create_v2_response(payload: WorkoutInput, *, include_persisted_history: bool = False) -> CoachingResponse:
    recommendation = evaluate_workout(payload)
    history = None
    if include_persisted_history:
        history = [*load_history(), *load_persisted_history(payload.athlete_id)]
    retrieved = retrieve_similar_history(payload, recommendation, history=history)
    evidence = build_evidence_package(payload, recommendation, retrieved)
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
    init_db()
    response = _create_v2_response(payload, include_persisted_history=True)
    recommendation_id = save_recommendation(
        payload,
        response.recommendation,
        response.trace,
        explanation=response.explanation,
        evidence=response.evidence,
    )
    return PersistedCoachingResponse(
        **response.model_dump(),
        recommendation_id=recommendation_id,
    )


@app.post("/v5/recommendations", response_model=V5CoachingResponse)
def create_v5_recommendation(payload: AccumulatedWorkoutInput) -> V5CoachingResponse:
    init_db()
    recommendation, accumulated_fatigue = evaluate_workout_v21(payload)
    history = [*load_history(), *load_persisted_history(payload.athlete_id)]
    retrieved = retrieve_similar_history(payload, recommendation, history=history)
    evidence = build_evidence_package(payload, recommendation, retrieved)
    explanation, trace = generate_explanation(evidence)
    write_trace(trace, athlete_id=payload.athlete_id, approved_action=recommendation.action)
    recommendation_id = save_recommendation(
        payload,
        recommendation,
        trace,
        explanation=explanation,
        evidence=evidence,
    )
    return V5CoachingResponse(
        recommendation=recommendation,
        accumulated_fatigue=accumulated_fatigue,
        explanation=explanation,
        evidence=evidence,
        trace=trace,
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


@app.get("/v4/metrics", response_model=DeploymentMetrics)
def deployment_metrics(athlete_id: str | None = None) -> DeploymentMetrics:
    init_db()
    return get_deployment_metrics(athlete_id)


@app.get("/v4/quality/explanations", response_model=ExplanationQualitySummary)
def explanation_quality(
    athlete_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> ExplanationQualitySummary:
    init_db()
    records = list_explanation_records(athlete_id=athlete_id, limit=limit)
    return summarize_explanation_records(records)
