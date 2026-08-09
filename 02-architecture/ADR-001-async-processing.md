# ADR-001 — Asynchronous Workout Processing

## Decision
Use a durable message queue between workout ingestion and downstream analysis.

## Rationale
Workout completion can be bursty. Asynchronous processing absorbs spikes and allows independent worker scaling.

## Trade-offs
**Pros:** resilience, elasticity, decoupling.

**Cons:** eventual consistency, operational complexity, retry/deduplication requirements.
