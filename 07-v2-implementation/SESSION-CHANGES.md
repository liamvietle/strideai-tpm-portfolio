# Athlete session changes

Today has one collapsed Change today’s session control. Choose swap, distance or skip; select availability, fatigue, feeling good or other, and optionally add a note. Preview lists every changed day, before/after totals for each affected week, and relevant warnings. A separate confirmation commits atomically. Preview tokens include current workouts and recovery/profile state and reject stale writes.

Original prescriptions remain unchanged. Current targets and legacy calendar snapshots update together. Reasons and before/after values use the existing coach_plan_changes audit table; current workout JSON holds structured athlete_change metadata for subsequent coaching context. No schema migration or configuration required.

Swaps move running prescriptions while keeping date-specific phase and strength assignments. Skips remove the session without distributing make-up mileage. Increases are athlete requests, never labelled coach approval. Warnings flag consecutive demanding sessions, session-time constraints, and distance increases over 30%. These warnings are conservative product heuristics, not physiological validation. Active injury, pain or severe soreness blocks scheduling running; skipping remains available. Fatigue changes cannot increase or redistribute distance. Race days, past dates, synced run dates, and locked/executed sessions cannot be rewritten. Structured interval distance edits are rejected to avoid invalid segment prescriptions.

For locked or completed sessions, record actual execution, which can differ from the expectation. Evaluation and learning use the revised pre-run target where available while retaining original-plan comparisons.

Validation: 117 pytest tests passed including swap totals, cross-week changes, skip/increase, athlete isolation, stale preview, injury and locked-session checks. Mobile browser verified 26/8 swap, distance increase, fatigue skip, persistence after reload and zero-running guidance after skip.
