# Milestone 5 — Real Validation and Accumulated Recovery Debt

Milestone 5 was triggered by a real validation sequence rather than a planned infrastructure feature.

## What changed the product hypothesis

The first retrospective comparison appeared to show StrideAI was too conservative: the athlete chose to maintain most sessions while the existing engine repeatedly suggested reducing training because of very short sleep and later-declining recovery signals.

The downstream target-event result changed that interpretation. Despite roughly high-but-controlled effort, performance was materially below expectation. In hindsight, the athlete judged the earlier warnings as directionally useful and believed accumulated fatigue from repeated poor sleep and deteriorating recovery contributed to the result.

This does **not** prove causality or prove that following StrideAI would have improved the event. It does show that exact agreement with the athlete's morning decision is not a sufficient validation metric.

## Product-learning conclusion

The key problem is not simply that sleep is weighted too heavily. The previous engine is too focused on **today's snapshot**.

Milestone 5 therefore distinguishes:

- an isolated bad night,
- repeated short sleep across an observed window,
- HRV position relative to the wearable's actual baseline range,
- HRV trend across recent observations,
- resting-HR rise,
- training-load elevation,
- subjective fatigue,
- soreness or pain,
- proximity to a target event.

## v2.1 behavior

A single bad night can produce an **elevated warning** while the structured action remains `maintain`.

Repeated poor recovery increases accumulated-fatigue severity:

```text
isolated warning
    ↓
accumulated recovery debt
    ↓
reduce intensity
    ↓
reduce volume / human review
```

Only hard safety signals such as reported pain or severe soreness can force `recovery_only`.

## HRV correction

The initial retrospective analysis approximated HRV status against the midpoint of the wearable baseline range. That was too crude.

v2.1 uses the baseline range directly:

- inside the range → no below-baseline penalty,
- below the lower bound → warning,
- materially below the lower bound → stronger warning.

This prevents an HRV value that is still inside the wearable's own baseline range from being mislabeled as severely suppressed.

## Real validation labels

The sanitized validation sequence preserves three different concepts:

1. **Human action at the time** — what the athlete chose that morning.
2. **StrideAI recommendation** — the deterministic system output.
3. **Outcome-informed assessment** — whether later evidence suggested the earlier warning had directional value.

These labels are intentionally not collapsed into one gold-standard answer.

## Privacy

The public validation file is not a raw wearable export.

It removes calendar dates and identity, rounds sleep values, transforms HRV levels while preserving trend and baseline relationships, and shifts resting-HR levels while preserving differences. The purpose is to test system behavior without publishing exact personal biometric history.

## Evaluation philosophy

Milestone 5 reports both:

- exact agreement with the contemporaneous athlete decision, and
- outcome-aligned warning detection.

A useful early warning does not require the system to force a training change immediately. This makes it possible to measure whether StrideAI recognized deterioration before the athlete changed behavior.

The real-validation set is small and retrospective. It is a product-learning artifact, not proof of coaching accuracy.

## Next validation step

Future cases should be prospective:

1. record recovery signals before the session,
2. record the athlete's independent decision,
3. reveal the StrideAI recommendation,
4. record the actual workout and subsequent outcome,
5. review disagreements without changing labels after the fact.

That prospective dataset will be more important than adding semantic retrieval, multi-agent orchestration, or additional infrastructure.
