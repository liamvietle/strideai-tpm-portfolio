# ADR-004 — Wearable Abstraction Layer

## Decision
Normalize provider-specific wearable data before it reaches core coaching services.

## Rationale
The coaching engine should not be coupled to Garmin or any other individual provider.

## Trade-offs
Adds an integration layer but simplifies future provider expansion and isolates API changes.
