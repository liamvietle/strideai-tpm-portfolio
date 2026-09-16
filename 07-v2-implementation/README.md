# StrideAI v2 Implementation

StrideAI v1 documented the product, architecture, program-management approach, and AI evaluation strategy. StrideAI v2 converts that design into running software while preserving the core architecture principle:

> Deterministic logic makes the coaching decision; the LLM explains it.

## Milestone 1: deterministic coaching API

Implemented:

- `POST /v1/recommendations`
- Pydantic input/output contracts
- deterministic fatigue and risk rules
- confidence-based autonomy
- safety override for pain and severe soreness
- auditable decision factors
- rules versioning
- automated tests

## Milestone 2: retrieved context + guarded AI explanation

Implemented:

- `POST /v2/recommendations`
- transparent retrieval of similar historical training cases
- immutable evidence package passed to the explanation layer
- optional OpenAI Responses API explanation generation
- deterministic explanation fallback when no API key is configured or the model call fails
- guardrail that rejects an explanation if its declared action differs from the approved deterministic action
- request trace containing provider, model, prompt version, latency, retrieval count, token usage, fallback status, and optional estimated cost
- JSONL trace logging under `logs/`
- regression tests preserving the v1 contract

### End-to-end flow

```text
Workout + recovery signals
        |
        v
Deterministic decision engine
        |
        +--> approved action / safety flags / confidence
        |
        v
Historical context retrieval
        |
        v
Immutable evidence package
        |
        v
LLM explanation (optional)
        |
        v
Action-consistency guardrail
     /      \
   pass    fail/error
    |          |
    v          v
LLM text   deterministic fallback
     \        /
        v
Recommendation + explanation + trace
```

The LLM never owns or mutates the structured coaching recommendation. The deterministic recommendation remains authoritative throughout the request.

## Run locally

```bash
cd 07-v2-implementation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```bash
pytest -q
```

## Call the deterministic endpoint

```bash
curl -X POST http://127.0.0.1:8000/v1/recommendations \
  -H "Content-Type: application/json" \
  --data @examples/workout_fatigued.json
```

## Call the v2 endpoint

Without an API key, `/v2/recommendations` still runs end to end and uses the deterministic explanation fallback.

```bash
curl -X POST http://127.0.0.1:8000/v2/recommendations \
  -H "Content-Type: application/json" \
  --data @examples/workout_fatigued.json
```

To enable real LLM explanations, configure environment variables before starting the API:

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.6-luna"
```

On Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="..."
$env:OPENAI_MODEL="gpt-5.6-luna"
```

Optional cost estimation uses provider prices supplied as environment variables rather than hard-coding prices that may change:

```bash
export OPENAI_INPUT_COST_PER_MTOK="..."
export OPENAI_OUTPUT_COST_PER_MTOK="..."
```

## Historical retrieval

Milestone 2 intentionally uses a simple, inspectable retrieval algorithm rather than embeddings. Similar cases receive points for:

- overlapping decision-factor codes,
- matching planned workout intensity,
- matching approved action,
- matching athlete.

This makes the retrieval decision auditable and easy to test. Vector or semantic retrieval can be introduced later when the knowledge base becomes large enough to justify it.

## Guardrail behavior

A generated explanation must start with exactly the deterministic engine's approved action, for example:

```text
Approved action: recovery_only.
```

If the model declares another action, returns an invalid response, times out, or raises an error, StrideAI discards that explanation and returns a deterministic fallback instead. The structured `recommendation.action` is never sourced from the LLM.

## Current test coverage

The Milestone 2 test suite covers:

- normal recovery
- multi-signal fatigue
- pain safety override
- missing-data behavior
- historical retrieval ranking
- deterministic fallback without an API key
- rejection of an LLM attempt to change the approved action
- acceptance of an action-consistent explanation
- v1 API regression
- v2 recommendation/evidence consistency

Local validation before commit: **10 tests passed**.

## Next milestone

Milestone 3 should move from sample historical cases toward a more realistic deployed system:

1. persistent storage for workouts, recommendations, and outcomes,
2. ingestion of real exported Garmin/Strava training data,
3. knowledge retrieval from coaching guidance in addition to personal history,
4. a small evaluation dataset and automated evaluation runner,
5. Docker packaging and CI,
6. a minimal user-facing interface.
