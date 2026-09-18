# StrideAI v2 Implementation

StrideAI v2 converts the original TPM/architecture case study into working software while preserving one core rule:

> Deterministic logic makes the coaching decision; the LLM explains it.

## Milestone progression

### Milestone 1 — deterministic coaching API

- `POST /v1/recommendations`
- structured Pydantic contracts
- fatigue/risk rules
- confidence-based autonomy
- hard safety overrides
- auditable decision factors and rule versions

### Milestone 2 — retrieval + guarded AI explanation

- `POST /v2/recommendations`
- transparent historical retrieval
- immutable evidence package
- optional OpenAI Responses API explanation generation
- deterministic fallback
- action-consistency guardrail
- latency/token/fallback observability

The LLM never owns or mutates the structured recommendation.

### Milestone 3 — real export ingestion + persistence

- SQLite persistence for activities, recommendations, and outcomes
- TCX ingestion for Garmin Connect and Strava exports
- Garmin activity-summary CSV ingestion
- idempotent imports
- `POST /v3/recommendations`
- Docker packaging
- GitHub Actions CI

### Milestone 4 — production feedback + quality gates

- recommendation acceptance and override status
- outcome coverage, completion, pain-after, human-review, guardrail and fallback metrics
- deterministic explanation-groundedness checks
- persisted recommendation/outcome retrieval
- regression baseline and release gate
- `/v4/metrics`
- `/v4/quality/explanations`
- lightweight `/dashboard`

### Milestone 5 — accumulated recovery debt + real validation

Milestone 5 came from a real retrospective validation sequence rather than a planned infrastructure feature.

The initial comparison made StrideAI look too conservative because the athlete maintained most sessions while the engine repeatedly warned about poor recovery. A later below-expectation target event changed the interpretation: the athlete judged those earlier warnings as directionally useful in hindsight.

That led to a new v2.1 model that distinguishes an isolated warning from accumulating fatigue.

Implemented:

- `POST /v5/recommendations`
- accumulated-fatigue states: `low`, `elevated`, `high`, `critical`
- 3-day and 7-day observed recovery windows
- repeated low-sleep detection
- HRV comparison against the wearable's actual baseline range instead of a range midpoint
- recent HRV trend
- recent resting-HR rise
- load, subjective fatigue, soreness and event-proximity contributors
- single bad night can warn without automatically cutting training
- only pain/severe soreness can force `recovery_only`
- sanitized real validation sequence with separate contemporaneous and hindsight labels
- outcome-aligned warning metric
- real-validation gate in CI

See [Milestone 5 — Real Validation and Accumulated Recovery Debt](MILESTONE-5-REAL-VALIDATION.md).

## v5 decision flow

```text
Current recovery snapshot
        +
recent recovery observations
        |
        v
Observed 3-day / 7-day windows
        |
        +--> repeated short sleep
        +--> HRV baseline position
        +--> HRV trend
        +--> resting-HR change
        +--> load / subjective fatigue / soreness
        +--> event proximity
        |
        v
Accumulated fatigue assessment
        |
        +--> LOW      -> maintain
        +--> ELEVATED -> warn / usually maintain
        +--> HIGH     -> reduce intensity
        +--> CRITICAL -> reduce volume / human review
        |
        +--> pain or severe soreness -> recovery only
        |
        v
Historical retrieval
        |
        v
Immutable evidence package
        |
        v
Guarded LLM explanation
        |
        v
Persistent recommendation + trace
        |
        v
Observed outcome / override
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

## Example v5 request

```json
{
  "athlete_id": "local-athlete",
  "day_index": 12,
  "planned_distance_km": 12,
  "planned_intensity": "moderate",
  "recent_load_ratio": 1.35,
  "sleep_hours": 4.5,
  "soreness_0_10": 2,
  "pain_flag": false,
  "hrv_ms": 48,
  "hrv_baseline_low": 46,
  "hrv_baseline_high": 77,
  "resting_hr_bpm": 52,
  "subjective_fatigue": "slightly_tired",
  "days_until_event": 3,
  "recovery_history": [
    {
      "day_index": 10,
      "sleep_hours": 5.0,
      "hrv_ms": 55,
      "hrv_baseline_low": 46,
      "hrv_baseline_high": 77,
      "resting_hr_bpm": 48,
      "soreness_0_10": 1,
      "subjective_fatigue": "normal",
      "recent_load_ratio": 1.2
    },
    {
      "day_index": 11,
      "sleep_hours": 4.0,
      "hrv_ms": 51,
      "hrv_baseline_low": 46,
      "hrv_baseline_high": 77,
      "resting_hr_bpm": 50,
      "soreness_0_10": 1,
      "subjective_fatigue": "normal",
      "recent_load_ratio": 1.3
    }
  ]
}
```

`day_index` is an arbitrary monotonic day number. It allows rolling-window evaluation without requiring calendar dates in validation fixtures.

## Real activity ingestion

### Apple Health recovery sync

The companion app in [`../08-ios-companion`](../08-ios-companion/README.md) reads Sleep Analysis, Resting Heart Rate and HRV SDNN on iPhone. It sends privacy-minimized daily summaries to:

```text
POST /app/api/apple-health/sync
GET  /app/api/apple-health/status
GET  /app/api/apple-health/daily-state?date=YYYY-MM-DD
DELETE /app/api/apple-health/data
```

The coaching workflow fills missing daily recovery fields from these summaries and includes synced days in the rolling seven-day recovery history even when no manual check-in was made. HRV baseline bounds use the 10th and 90th percentiles of up to 28 prior daily medians, with at least seven observations required.

Raw HealthKit samples are aggregated on the iPhone and are not uploaded.

Import a Garmin or Strava TCX file locally:

```bash
python -m app.import_cli \
  --file /path/to/activity.tcx \
  --athlete-id local-athlete \
  --format tcx \
  --source garmin
```

Import a Garmin activity-summary CSV:

```bash
python -m app.import_cli \
  --file /path/to/activities.csv \
  --athlete-id local-athlete \
  --format garmin-csv
```

No personal raw activity export is committed to this public repository.

## Real-validation labels

The sanitized validation set keeps three concepts separate:

1. **human action at the time** — what the athlete chose that morning,
2. **StrideAI output** — what the deterministic system recommended,
3. **outcome-informed assessment** — whether later evidence suggested the earlier warning had directional value.

The third label is retrospective judgment, not causal proof.

Run it with:

```bash
python -m app.real_validation evaluation/real-validation-sanitized.json
```

The main new metric is `outcome_aligned_warning_rate`. This is intentionally reported alongside exact contemporaneous agreement rather than replacing it.

## Existing deployment metrics

```text
GET /v4/metrics?athlete_id=local-athlete
GET /v4/quality/explanations?athlete_id=local-athlete
```

Metrics include coverage, acceptance, override, completion, pain-after, human review, guardrail pass, fallback and explanation latency.

## Tests and release gates

```bash
pytest -q
python -m app.evaluation evaluation/cases.json
python -m app.quality evaluation/cases.json evaluation/baseline-m3.json
python -m app.real_validation evaluation/real-validation-sanitized.json
```

CI fails if the deterministic baseline regresses materially, safety violations increase, explanation quality falls below the existing gate, or the sanitized real-validation sequence loses most of its outcome-aligned warning detection.

## Privacy boundary

`evaluation/real-validation-sanitized.json` is **not** a raw wearable export. Calendar dates and identity are removed, sleep is rounded, HRV levels are transformed while preserving baseline relationships/trends, and resting-HR levels are shifted while preserving deltas.

## Current limitations

- raw Garmin wellness FIT data such as HRV and sleep is not ingested automatically
- the real-validation set has sparse recovery observations rather than every calendar day
- retrospective outcome labels are useful for product learning but are vulnerable to hindsight bias
- accumulated-fatigue thresholds are heuristics, not medically validated cutoffs
- rule-based retrieval is still used instead of embeddings
- the real-validation sample is small

These are explicit boundaries rather than hidden gaps.

## Next step

The next step is **prospective validation**, not another infrastructure milestone:

1. record recovery signals before a future training session,
2. lock the athlete's independent decision,
3. reveal the v5 recommendation,
4. record the actual session and subsequent outcome,
5. analyze disagreements without rewriting the original labels.

A growing prospective failure/override set is more valuable now than adding agents, Kubernetes, or a vector database.


## Athlete coaching loop

The Athlete, Coach and Review tabs add profile-based planning, saved pre-run expectations, execution/outcome comparisons, bounded athlete learning and living-plan revisions. See [ATHLETE-LOOP.md](ATHLETE-LOOP.md) for the workflow, additive migration, AI configuration and current limitations.
