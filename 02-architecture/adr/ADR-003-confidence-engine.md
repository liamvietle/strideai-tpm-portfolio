# ADR-003 — Confidence-Based AI Autonomy

## Decision
Use recommendation confidence to determine whether StrideAI can automatically modify training.

## Rationale
Incomplete or conflicting data should reduce autonomy rather than force an uncertain action.

## Behavior
High confidence → automatic adjustment.

Medium confidence → user confirmation.

Low confidence → no automatic adjustment.
