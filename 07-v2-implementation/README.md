# StrideAI v2 Implementation

## Milestone 1: Working deterministic coaching API

StrideAI v1 documented the product, architecture, program-management approach, and AI evaluation strategy. StrideAI v2 starts converting that design into running software.

This milestone intentionally keeps the architecture principle:

> Deterministic logic makes the coaching decision; the LLM explains it.

## What is implemented

- FastAPI endpoint: `POST /v1/recommendations`
- Pydantic input/output contracts
- Deterministic fatigue and risk rules
- Confidence-based autonomy
- Safety override for pain and severe soreness
- Decision factors for traceability
- Rules versioning
- Automated tests
- Example input payload

## Run locally

```bash
cd 07-v2-implementation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open Swagger UI at:

```text
http://127.0.0.1:8000/docs
```

Run tests:

```bash
pytest -q
```

Example API call:

```bash
curl -X POST http://127.0.0.1:8000/v1/recommendations \
  -H "Content-Type: application/json" \
  --data @examples/workout_fatigued.json
```

## Current design

Inputs such as HRV vs baseline, resting-HR delta, sleep, load ratio, soreness, pain, and recent racing are converted into:

- fatigue state
- risk level
- confidence
- autonomy mode
- recommended action
- volume adjustment
- auditable decision factors
- safety flags

High-risk or safety-triggered cases are routed to human review rather than automatic progression.

## Next milestone

Milestone 2 will add:

1. historical training-context retrieval,
2. a structured evidence package for explanations,
3. LLM-generated explanation with deterministic fallback,
4. guardrails preventing the LLM from changing the approved coaching action,
5. trace logging for model, prompt, latency, cost, and retrieved evidence.
