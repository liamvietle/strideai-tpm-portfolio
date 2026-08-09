# ADR-003 — Confidence-Based AI Autonomy

## Decision
Use recommendation confidence to determine whether StrideAI can automatically modify training.

## Rationale
Incomplete or conflicting data should reduce autonomy rather than force an uncertain action.

## Behavior
High confidence → automatic adjustment.

Medium confidence → user confirmation.

Low confidence → no automatic adjustment.

## Alternatives considered

### Always automatic

Automatically apply every model recommendation.

**Pros:** lowest user friction.

**Cons:** unsafe when data is incomplete, conflicting, or uncertain.

### Always require user confirmation

Require confirmation for every recommendation.

**Pros:** conservative and easy to control.

**Cons:** creates unnecessary friction for high-confidence recommendations and reduces the value of adaptive coaching.

### Confidence-based autonomy

Use confidence thresholds to determine the level of automation.

**Pros:** balances safety, user control, and convenience.

**Cons:** requires calibrated confidence thresholds and monitoring.

## Decision rationale

Confidence-based autonomy provides a graduated control model: high confidence can automate, medium confidence requires confirmation, and low confidence does not automatically change the plan.
