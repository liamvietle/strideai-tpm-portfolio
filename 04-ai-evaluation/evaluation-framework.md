# AI Evaluation Framework

## Principle

Do not treat “AI accuracy” as a single universal metric.

StrideAI evaluates four layers:

1. Model quality
2. Recommendation quality
3. Safety
4. User outcomes

## 1. Model quality

Potential measures:
- Precision
- Recall
- F1
- Confusion matrix
- Calibration
- False-positive rate
- False-negative rate

## 2. Recommendation quality

Use multiple evidence sources:

### Expert review
Qualified running/sports-science reviewers assess anonymized scenarios.

### Recommendation-quality definition

For the MVP launch gate, recommendation quality is measured as **expert agreement rate**: the percentage of evaluation scenarios in which qualified reviewers judge the proposed training adaptation to be appropriate against a predefined evaluation rubric.
The production target is **≥80% expert agreement** on the agreed evaluation dataset.
The 74% → 80% program risk therefore refers to expert-rated recommendation appropriateness, not a generic model-accuracy metric.
Expert agreement is combined with historical backtesting and safety evaluation before production rollout.

### Historical backtesting
Replay historical data and compare simulated recommendations with subsequent outcomes.

### Combined decision quality
Use expert agreement and backtesting as complementary evidence rather than claiming either is perfect ground truth.

## 3. Safety

Safety is a separate gate.

Example critical metric:

**Critical safety violation rate = 0**

A system may tolerate imperfect general recommendation quality; it should not tolerate confirmed critical safety violations.

## 4. User outcomes

Track:
- Recommendation acceptance
- Override rate
- User satisfaction
- Training adherence
- Retention
- Negative feedback

Acceptance is not treated as proof of correctness.

## Quality dashboard

Simulated program metric

| Metric | Target | Category |
|---|---:|---|
| Fatigue model F1 | DS-defined gate | Model |
| Expert agreement | ≥80% target | Decision quality |
| Critical safety violations | 0 | Safety |
| Recommendation acceptance | >70% | Product |
| 30-day retention | >50% | Product |
| Recommendation latency | Defined SLO | Technical |
| Low-confidence auto-adjustments | 0 | Safety |

## Model versioning

Every recommendation should record:
- Recommendation ID
- Model version
- Rules version
- Input timestamp
- Confidence
- Decision

This enables traceability and rollback.

## Production monitoring

Monitor:
- Input distribution drift
- Missing-data rate
- Recommendation distribution
- Confidence distribution
- Expert disagreement
- User overrides
- Quality degradation

## Rollout gates

### Internal
Safety and system tests must pass.

### Beta
Validate real-world behavior against offline evaluation.

### 20%
Expand only if quality, safety, and reliability gates pass.

### 40%
Repeat production evaluation and check for degradation.

### 100%
Only after agreed production thresholds are met and no critical safety issues remain.

## Rollback

Immediate rollback/pause if:
- Critical safety violation is confirmed.
- Quality falls below the agreed production threshold.
- Data-integrity failure materially affects users.
