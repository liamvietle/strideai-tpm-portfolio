# RAID Log

## Risks

| ID | Risk | Probability | Impact | Owner | Trigger | Mitigation | Contingency |
|---|---|---|---|---|---|---|---|
| R-001 | Recommendation quality below threshold | High | Critical | DS Lead | Week-3 gate missed | Fatigue task force, alternative signals, resource assessment | Controlled rollout |
| R-002 | Insufficient recovery data | High | High | DS Lead | Missing critical signals | Confidence reduction, alternative signals | No auto-adjustment |
| R-003 | Wearable API instability | Medium | High | API Lead | Error/sync spike | Retry, monitoring, abstraction, re-sync | Safe no-adaptation mode |
| R-004 | Peak traffic overload | Medium | High | Platform Lead | Queue/load threshold exceeded | Queue + autoscaling + load test | Prioritize critical processing |
| R-005 | AI infrastructure cost too high | Medium | Medium | Platform/Product | Cost threshold exceeded | Model routing, caching, tiered storage | Reduce expensive processing |
| R-006 | User distrust | Medium | High | Product | Acceptance/override deterioration | Explainability + control | Revisit recommendation strategy |
| R-007 | Safety defect | Low | Critical | Eng + DS | Confirmed critical violation | Deterministic rules + tests | Immediate pause/rollback |

## Assumptions

| ID | Assumption | Owner | Validation |
|---|---|---|---|
| A-001 | Wearable providers expose sufficient MVP data | API Lead | API validation |
| A-002 | Historical data supports fatigue-model evaluation | DS Lead | Dataset assessment |
| A-003 | Current staffing supports six-week MVP | TPM | Capacity plan |
| A-004 | Evaluation methodology supports meaningful quality gates | DS Lead | Evaluation design |

## Issues

| ID | Issue | Status | Owner | Action |
|---|---|---|---|---|
| I-001 | Recommendation quality below target | 🔴 Open | DS Lead | Fatigue-model task force |
| I-002 | Mobile blocked by API contract | 🟡 Open | Backend + Mobile | Joint working session |

## Dependencies

| ID | Dependency | Critical? | Owner |
|---|---|---|---|
| D-001 | Garmin API | Yes | API Lead |
| D-002 | Validated data → fatigue model | Yes | DS Lead |
| D-003 | Fatigue model → adaptation | Yes | DS + Backend |
| D-004 | Recommendation API → mobile | Yes | Backend + Mobile |
| D-005 | Safety validation → launch | Yes | QA + DS |

## Escalation criteria

Escalate when:
- Critical milestone forecast slips beyond tolerance.
- Recommendation quality materially misses the gate.
- Any critical safety issue appears.
- Budget/cost exceeds agreed tolerance.
- External dependency threatens the critical path.
- Cross-functional decision cannot be resolved within the agreed timeframe.
