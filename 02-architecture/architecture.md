# StrideAI Architecture

## High-level architecture

```mermaid
flowchart TD
    A[Runner] --> B[Mobile App]
    B --> C[API Gateway]
    C --> D[Workout Service]
    C --> E[User Service]
    D --> F[Wearable Integration]
    F --> G[Message Queue]
    G --> H[Data Processing]
    H --> I[(Data Store)]
    H --> J[Training Load Engine]
    H --> K[Recovery Signals]
    J --> L[Fatigue Model]
    K --> L
    L --> M[Confidence Engine]
    M --> N[Adaptation Engine]
    N --> O[Safety Rules]
    O --> P[Final Recommendation]
    P --> Q[LLM Explanation]
    P --> I
    Q --> B
```

## Key components

### Wearable integration
Normalizes provider-specific APIs into a common StrideAI schema.

### Message queue
Decouples ingestion from processing and absorbs bursts.

### Data processing
Validates data, detects duplicates, records provenance, and handles incomplete inputs.

### Training-load and recovery engines
Transform raw data into structured coaching signals.

### Fatigue model
Produces a state such as Normal, Elevated, Extreme, or Unknown plus confidence information.

### Confidence engine
Controls AI autonomy:
- High confidence → automatic adjustment
- Medium confidence → recommendation + confirmation
- Low confidence → no automatic change

### Adaptation engine
Converts model outputs into workout changes such as intensity, pace, distance, duration, or workout type.

### Safety rules
Deterministic constraints that cannot be overridden by generative behavior.

### LLM explanation
Generates human-readable explanations from structured decision factors. It should not independently invent safety-critical workout changes.

## Failure handling

| Failure | Expected behavior |
|---|---|
| Wearable API unavailable | Do not adapt using missing critical data |
| Invalid workout data | Reject/flag data |
| Duplicate workout | Deduplicate |
| Queue backlog | Scale workers |
| Model unavailable | Safe fallback |
| Low confidence | No automatic change |
| Explanation service unavailable | Predefined explanation fallback |
| Critical safety violation | Pause/rollback affected behavior |

## Scalability

- Kubernetes/autoscaling for compute
- Message queue for burst absorption
- Model routing for cost control
- Caching for reusable environmental information
- Tiered storage for recent vs. historical data

## Observability

Monitor:
- API latency/errors
- Queue depth
- Processing failures
- Sync success
- Recommendation latency
- Model quality
- Confidence distribution
- Infrastructure utilization
- Cost per active runner

## Security & data governance

Wearable and health-related data should be encrypted in transit and at rest, access-controlled by service/user identity, retained only as long as required, and audited for sensitive-data access. Provider OAuth tokens should be stored separately from coaching data.
