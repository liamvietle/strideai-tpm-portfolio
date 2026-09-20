# Optional late check-in and AI test

Recorded workouts show a collapsed late-check-in form in workout details, including
Today review. It captures recalled pre-run feeling, optional sleep hours, optional
pain and notes. Late notes are timestamped and marked retrospective. They do not
replace daily_checkins, produce predictions, alter the training plan or enter
prediction accuracy/athlete learning. A run must already exist. Notes can be updated.

A separate Test AI connection button sends a synthetic request through the same
coach choose() HTTP and structured-output validation path. It uses the configured
key, enable flag and model, and reports success only after valid provider output.
It does not send the recalled notes or write coaching predictions/decisions. Standard
provider charges apply. Tests are rate-limited per athlete to one per minute,
including simultaneous requests, using a SQLite transaction. Errors are sanitized;
keys and raw provider responses are never returned. The last result is persisted.

Lazy additive tables: coach_late_checkins and coach_ai_tests. Existing auth/CSRF
middleware applies. No new environment variables. These diagnostics do not prove
that the model contributed to any previous workout.

Validation: 147 tests passed, including account ownership, retrospective isolation,
immutable evaluation, live-path mocked success, timeout and cooldown. No real
production inference has been verified during implementation.
Mobile browser test also passed: saved late feelings, verified persistence and
retrospective label, exercised the disabled-provider result, and checked overflow.
