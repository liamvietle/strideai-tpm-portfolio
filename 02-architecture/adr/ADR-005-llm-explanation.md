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
