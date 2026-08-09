# ADR-001 — Asynchronous Workout Processing

## Decision
Use a durable message queue between workout ingestion and downstream analysis.

## Rationale
Workout completion can be bursty. Asynchronous processing absorbs spikes and allows independent worker scaling.

## Trade-offs
**Pros:** resilience, elasticity, decoupling.

**Cons:** eventual consistency, operational complexity, retry/deduplication requirements.

## Alternatives considered

### Synchronous processing

Process workout data and generate the recommendation directly within the API request.

**Pros:** simpler initial architecture and immediate response.

**Cons:** less resilient to traffic spikes, tighter coupling between ingestion and analysis, and harder to scale processing independently.

### Asynchronous processing

Use a durable message queue between ingestion and downstream analysis.

**Pros:** absorbs bursts, enables independent worker scaling, and isolates ingestion from downstream processing.

**Cons:** introduces eventual consistency, retry handling, and additional operational complexity.

## Decision rationale

As workout completion can create bursty workloads and downstream AI processing may have variable latency, resilience and independent scaling are more important than strict synchronous response behavior for the MVP.
