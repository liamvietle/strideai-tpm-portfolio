# StrideAI v2 Implementation

StrideAI v1 documented the product, architecture, program-management approach, and AI evaluation strategy. StrideAI v2 converts that design into running software while preserving one core rule:

> Deterministic logic makes the coaching decision; the LLM explains it.

## Milestone progression

### Milestone 1: deterministic coaching API

- `POST /v1/recommendations`
- structured Pydantic contracts
- fatigue and risk rules
- confidence-based autonomy
- safety overrides
- auditable decision factors and rules versioning

### Milestone 2: retrieved context + guarded AI explanation

- `POST /v2/recommendations`
- retrieval of similar historical cases
- immutable evidence package
- optional OpenAI Responses API explanation generation
- deterministic fallback
- guardrail preventing the LLM from changing the approved action
- request tracing for provider, model, prompt, latency, retrieval count, tokens, fallback, and optional cost

The LLM never owns or mutates the structured recommendation.

### Milestone 3: real export ingestion + persistence + evaluation

- SQLite persistence for activities, recommendations, and outcomes
- TCX ingestion compatible with Garmin Connect and Strava exports
- Garmin activity-summary CSV ingestion
- idempotent activity upserts
- `POST /v3/recommendations` with persistent recommendation IDs
- outcome capture
- Docker packaging
- GitHub Actions CI

### Milestone 4: production feedback + quality gates

Milestone 4 turns post-deployment behavior into measurable signals.

Implemented:

- persisted recommendation acceptance and override status
- persisted explanation, evidence package, provider and guardrail metadata
- deployment metrics for outcome coverage, acceptance, override, completion, pain-after, human review, guardrail pass and fallback
- deterministic explanation-groundedness evaluation
- unsupported numeric-claim detection
- retrieval from prior persisted recommendation/outcome history
- Milestone 3 regression baseline and automated release gate
- `/v4/metrics`
- `/v4/quality/explanations`
- lightweight `/dashboard` operational view

## End-to-end data flow

```text
Garmin / Strava export
        |
        v
TCX / Garmin CSV parser
        |
        v
SQLite activity history
        |
        v
Workout + recovery signals
        |
        v
Deterministic decision engine
        |
        +------------------------------+
        |                              |
        v                              v
static reference cases      persisted recommendations + outcomes
        |                              |
        +--------------+---------------+
                       v
              historical retrieval
                       |
                       v
              immutable evidence
                       |
                       v
              LLM explanation
                       |
                       v
              action guardrail
                       |
                       v
       persistent recommendation + trace
                       |
                       v
            user outcome / override
                       |
          +------------+-------------+
          |                          |
          v                          v
  deployment metrics       explanation quality
          |                          |
          +------------+-------------+
                       v
              regression / release gate
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

Operational dashboard:

```text
http://127.0.0.1:8000/dashboard
```

Run tests and evaluation gates:

```bash
pytest -q
python -m app.evaluation evaluation/cases.json
python -m app.quality evaluation/cases.json evaluation/baseline-m3.json
```

## Real activity ingestion

Import a Garmin or Strava TCX file locally:

```bash
python -m app.import_cli \
  --file /path/to/activity.tcx \
  --athlete-id viet \
  --format tcx \
  --source garmin
```

Import a Garmin activity-summary CSV:

```bash
python -m app.import_cli \
  --file /path/to/activities.csv \
  --athlete-id viet \
  --format garmin-csv
```

No personal raw activity export is committed to this public repository.

## Outcome feedback

An outcome can now distinguish completing a session from actually following StrideAI's recommendation:

```json
{
  "completed": true,
  "perceived_effort_0_10": 6,
  "pain_after": false,
  "followed_recommendation": false,
  "override_action": "reduce_volume",
  "notes": "Reduced the session, but not as much as recommended."
}
```

This separation avoids treating missing follow/override feedback as implicit acceptance.

## Deployment metrics

```text
GET /v4/metrics?athlete_id=viet
```

The response includes:

- outcome coverage
- recommendation acceptance and override rates
- completion and pain-after rates
- average perceived effort
- human-review rate
- trace coverage
- guardrail pass rate
- deterministic-fallback rate
- average explanation latency

Metrics expose their own coverage instead of hiding missing feedback.

## Explanation groundedness

```text
GET /v4/quality/explanations?athlete_id=viet
```

The first quality evaluator is intentionally deterministic rather than another LLM judge. It checks:

1. the explanation still declares the approved deterministic action,
2. numeric claims are present in the evidence package,
3. the explanation overlaps with the actual decision factors.

The resulting groundedness score is a regression signal, not a claim of medical or coaching correctness.

## Persisted outcome retrieval

Milestone 2 used a static reference-case file. Milestone 4 also converts completed recommendation/outcome records into `HistoricalCase` objects. New persisted recommendations can therefore retrieve relevant prior outcomes using the same transparent similarity scoring used for reference cases.

Only records with an observed outcome enter this persisted-history source.

## Regression gate

`evaluation/baseline-m3.json` captures the Milestone 3 deterministic baseline. CI compares the current candidate against it and fails if:

- action accuracy falls by more than 2 percentage points,
- safety violations increase,
- explanation groundedness falls below 90%, or
- explanation action consistency falls below 99%.

The current hand-authored evaluation set is intentionally small. It demonstrates deployment discipline and release gating; it does not prove real-world coaching accuracy.

## Docker

```bash
docker build -t strideai-v2 .
docker run --rm -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  strideai-v2
```

The application still works without an OpenAI API key by using deterministic explanation fallback.

## CI

`.github/workflows/strideai-v2-ci.yml` runs:

1. dependency installation,
2. the full pytest suite,
3. deterministic action/safety evaluation,
4. the Milestone 4 deployment-quality regression gate.

## Current limitations

- raw Garmin wellness FIT data such as HRV and sleep is not yet ingested
- daily recovery signals still enter the recommendation API separately
- the persisted-history retriever uses transparent rule-based similarity rather than embeddings
- the evaluation set is small and hand-authored
- outcome metrics become representative only after enough user feedback is captured
- deterministic groundedness checks catch obvious unsupported claims but are not full semantic verification

These are deliberate boundaries rather than hidden gaps.

## Next milestone

The next useful step is not more infrastructure. It is to validate the system with a real private activity export and grow the evaluation set from observed failure/override cases. After that, semantic retrieval and richer model-based evaluation would have enough data to justify their complexity.
