# StrideAI v2 Implementation

StrideAI v1 documented the product, architecture, program-management approach, and AI evaluation strategy. StrideAI v2 converts that design into running software while preserving one core rule:

> Deterministic logic makes the coaching decision; the LLM explains it.

## Milestone 1: deterministic coaching API

- `POST /v1/recommendations`
- structured Pydantic contracts
- fatigue and risk rules
- confidence-based autonomy
- safety overrides
- auditable decision factors
- rules versioning

## Milestone 2: retrieved context + guarded AI explanation

- `POST /v2/recommendations`
- retrieval of similar historical cases
- immutable evidence package
- optional OpenAI Responses API explanation generation
- deterministic fallback
- guardrail preventing the LLM from changing the approved action
- request tracing for provider, model, prompt, latency, retrieval count, tokens, fallback, and optional cost
- JSONL observability logs

The LLM never owns or mutates the structured recommendation.

## Milestone 3: real export ingestion + persistence + evaluation

Milestone 3 adds the deployment plumbing needed to move from a demo request to an accumulating coaching system.

Implemented:

- SQLite persistence for activities, recommendations, and outcomes
- TCX ingestion compatible with exports from Garmin Connect and Strava
- Garmin activity-summary CSV ingestion
- idempotent activity upserts
- `POST /v3/recommendations` with persistent recommendation IDs
- outcome capture for completed/rejected recommendations
- activity import/list API endpoints
- CLI import path for local exports
- automated evaluation dataset and evaluation runner
- Docker packaging
- GitHub Actions CI

### Why TCX is the primary activity adapter

Both Garmin Connect and Strava support TCX activity exports. TCX provides a structured activity representation and can include heart-rate data, which makes it a more reliable first integration contract than depending on changing spreadsheet column layouts.

Garmin summary CSV is also supported for bulk activity summaries.

FIT ingestion is intentionally deferred. FIT is richer but binary and would add a separate dependency; TCX is enough to validate the ingestion and persistence architecture first.

## Data flow

```text
Garmin / Strava export
        |
        v
TCX / Garmin CSV parser
        |
        v
Normalized ActivityRecord
        |
        v
SQLite activity history
        |
        +-------------------------------+
        |                               |
        v                               v
Workout + recovery signals      prior recommendations/outcomes
        |                               |
        v                               |
Deterministic decision engine           |
        |                               |
        v                               |
Historical-context retrieval <----------+
        |
        v
Immutable evidence package
        |
        v
Optional LLM explanation
        |
        v
Action-consistency guardrail
        |
        v
Persistent recommendation + trace
        |
        v
User outcome / override
```

## Run locally

```bash
cd 07-v2-implementation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```bash
pytest -q
```

Run the deterministic evaluation suite:

```bash
python -m app.evaluation evaluation/cases.json
```

## Import a real TCX activity

Garmin Connect and Strava can both export an activity as TCX.

```bash
python -m app.import_cli \
  --file /path/to/activity.tcx \
  --athlete-id viet \
  --format tcx \
  --source garmin
```

For a Strava TCX export:

```bash
python -m app.import_cli \
  --file /path/to/activity.tcx \
  --athlete-id viet \
  --format tcx \
  --source strava
```

Import a Garmin activity-list CSV:

```bash
python -m app.import_cli \
  --file /path/to/activities.csv \
  --athlete-id viet \
  --format garmin-csv
```

No personal raw activity export is committed to this public repository. Real exports should remain local or be sanitized before sharing.

## v3 API

Import TCX:

```text
POST /v3/activities/import/tcx?athlete_id=viet&source=garmin
```

Import Garmin CSV:

```text
POST /v3/activities/import/garmin-csv?athlete_id=viet
```

List persisted activities:

```text
GET /v3/activities?athlete_id=viet
```

Create and persist an explained recommendation:

```text
POST /v3/recommendations
```

Record the observed outcome:

```text
PUT /v3/recommendations/{recommendation_id}/outcome
```

## Persistence

The default database is:

```text
data/strideai.db
```

Override it with:

```bash
export STRIDEAI_DB_PATH=/path/to/strideai.db
```

The database stores three separate layers:

1. raw-normalized activity history,
2. recommendation requests and deterministic outputs,
3. observed user outcomes.

This separation allows later evaluation of recommendation quality and user overrides without rewriting historical source data.

## Evaluation

`evaluation/cases.json` is a small deterministic regression set. It currently measures:

- expected-action accuracy,
- safety violations,
- cases routed to human review.

The dataset is intentionally small and synthetic at this stage. It validates the evaluation pipeline; it does not claim clinical or coaching accuracy.

Example output:

```json
{
  "cases": 6,
  "correct_actions": 6,
  "action_accuracy": 1.0,
  "safety_violations": 0,
  "human_review_cases": 4
}
```

## Docker

Build:

```bash
docker build -t strideai-v2 .
```

Run:

```bash
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  strideai-v2
```

The application works without an OpenAI API key; the explanation layer falls back deterministically.

## CI

`.github/workflows/strideai-v2-ci.yml` runs on changes to the v2 implementation and executes:

1. dependency installation,
2. the pytest suite,
3. the deterministic evaluation runner.

## Current limitations

- raw Garmin wellness FIT data such as HRV/sleep is not yet ingested
- TCX activities provide workout history, but daily recovery signals still enter the recommendation API separately
- historical retrieval still uses the Milestone 2 reference-case store rather than querying learned similarity from the SQLite history
- evaluation cases are small and hand-authored
- no user-facing UI yet

These are deliberate boundaries rather than hidden gaps.

## Next milestone

Milestone 4 should focus on measurable AI quality rather than adding more product surface:

1. generate evaluation cases from persisted history,
2. score explanation groundedness and action consistency,
3. track human overrides and recommendation acceptance,
4. retrieve from persisted recommendations/outcomes,
5. add a minimal dashboard for traces, evaluations, and outcomes,
6. optionally add FIT/wellness ingestion for HRV and sleep.
