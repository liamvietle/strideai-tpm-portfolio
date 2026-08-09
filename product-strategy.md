# Product Strategy

## Problem

Static training plans do not continuously respond to changes in a runner's performance, recovery, wearable signals, or environment.

## Target users

Recreational runners from 5K through marathon.

## Product promise

StrideAI continuously reassesses the runner and adapts upcoming training while controlling the level of automation based on recommendation confidence.

## Product principles

1. Adaptive coaching is the primary differentiator.
2. Safety overrides convenience.
3. Incomplete data should reduce AI autonomy.
4. Users retain control except where predefined safety constraints require intervention.
5. Secondary features should be deferred when they threaten the quality of adaptive coaching.

## MVP prioritization

P0:
- Wearable data
- Training load
- Recovery/fatigue
- Confidence engine
- Adaptation engine
- Safety rules
- Basic explanation

Phase 2:
- Race predictor
- Weekly summaries
- Advanced progress tracking

## Example decision

If performance and recovery signals indicate elevated fatigue with high confidence, reduce the intensity of the next hard workout.

If confidence is medium, recommend the change and request confirmation.

If confidence is low, do not automatically change the plan and explain the data limitation.
