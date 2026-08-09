# ADR-002 — Deterministic Safety Rules

## Decision
Keep hard safety constraints outside the LLM.

## Rationale
Safety behavior must be predictable, testable, observable, and independently versioned.

## Trade-offs
Rules add engineering work and may reduce flexibility, but the increased control is appropriate for MVP.
