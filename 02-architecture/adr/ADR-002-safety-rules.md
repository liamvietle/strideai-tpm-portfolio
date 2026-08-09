# ADR-002 — Deterministic Safety Rules

## Decision
Keep hard safety constraints outside the LLM.

## Rationale
Safety behavior must be predictable, testable, observable, and independently versioned.

## Trade-offs
Rules add engineering work and may reduce flexibility, but the increased control is appropriate for MVP.

## Alternatives considered

### Safety rules inside the LLM

Allow the LLM to interpret all inputs and determine safety behavior.

**Pros:** flexible and potentially simpler orchestration.

**Cons:** behavior is less deterministic and harder to test, constrain, audit, and guarantee.

### Deterministic safety layer

Evaluate predefined safety constraints separately from generative behavior.

**Pros:** predictable, testable, observable, and independently versioned.

**Cons:** requires additional engineering and maintenance of explicit rules.

## Decision rationale

Because workout adaptation can affect physical training behavior, critical safety constraints require deterministic enforcement independent of the LLM.
