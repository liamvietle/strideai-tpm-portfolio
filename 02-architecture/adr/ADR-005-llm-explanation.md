# ADR-005 — LLM for Explanation, Not Core Safety Decisions

## Decision
Use ML/decision logic for the coaching recommendation and an LLM primarily for explanation.

Alternative A: LLM directly generates workout adaptation
- Pros: flexible, simpler initial orchestration
- Cons: harder to guarantee behavior, evaluate, and constrain

Alternative B: deterministic/ML decision + LLM explanation
- Pros: predictable, testable, auditable
- Cons: more components and engineering effort

Decision: B for MVP.

## Rationale
The MVP prioritizes recommendation quality, predictability, safety, and testability.

## Future option
Revisit LLM-driven decisioning after production evidence demonstrates measurable benefit and sufficient controls.

## Alternatives considered

### LLM makes the coaching decision

Use the LLM to directly determine workout adaptations from the available user data.

**Pros:** highly flexible and potentially simpler for rapidly changing coaching logic.

**Cons:** behavior is less deterministic, harder to validate exhaustively, and more difficult to constrain for safety-critical decisions.

### Deterministic/ML decision + LLM explanation

Use ML models and deterministic logic to make the coaching decision, then provide structured decision factors to the LLM for explanation.

**Pros:** predictable decision behavior, clearer evaluation boundaries, stronger safety controls, and auditable recommendations.

**Cons:** requires additional architecture and limits the LLM's role in generating novel adaptations.

## Decision rationale

Adaptive coaching is the primary product differentiator, so recommendation quality and predictable behavior take priority over maximizing LLM flexibility for the MVP. The LLM should improve the user experience through explanation without independently inventing safety-critical workout changes.

## Revisit criteria

This decision should be revisited after production evidence is available. A future architecture could allow greater LLM autonomy if it can demonstrate equivalent or better recommendation quality, safety, observability, and controllability.
