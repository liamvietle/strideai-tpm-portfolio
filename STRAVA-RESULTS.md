# Automatic Strava results

A completed Strava sync reconciles existing active workouts with stored activities.
The app also reconciles on workout refresh, so already-synced runs are supported.
Exactly one run and one unexecuted workout must exist on the athlete's local date.
The workout must currently prescribe running. Multiple runs, duplicate providers,
rest days, other athletes and existing executions are never automatically replaced.

Distance, moving duration and average HR come from the activity; absent HR stays
unknown. Completion is inferred from 90% of the current planned distance, and can
be corrected in optional feedback before evaluation. No pain-free claim or RPE
is inferred from objective metrics. An explicit valid perceived_exertion field is
accepted opportunistically if supplied by Strava, but is not a documented API
guarantee. suffer_score is never converted into RPE. No additional API calls or
scopes are required.

The user taps Review my result, optionally adding RPE or reporting pain/incompletion.
Evaluation and existing learning/plan adjustments then run. Missing RPE never
blocks evaluation; it limits the expectation verdict and learning confidence.
Feedback cannot overwrite an evaluated outcome. Existing manual entry and ambiguous
activity selection remain inside a disclosure. Repeated sync does not duplicate
executions or revise previously reviewed results. Later Strava metric edits and
split ingestion are not implemented in this change.

Sync remains app-driven (including a throttled refresh on returning to the app),
not a new background webhook service. No schema migrations or environment changes.

Validation: 130 pytest tests; tests/strava_results_browser.cjs at mobile width.

## Expected values and perceived effort

Strava Perceived Exertion uses 1–10, mapped directly to RPE. Pending linked-workout
candidates receive a bounded best-effort activity-detail lookup (maximum five per
sync, five-second timeout each). Missing fields, errors or invalid values leave
RPE unknown; Relative Effort/suffer_score is not converted.

Workout responses now include comparison_metrics for both new and legacy results.
Valid pre-run predictions take priority per metric; saved plan targets supply the
fallback. New executions freeze their target snapshot. Legacy results without a
valid prediction use original saved plan targets, not reconstructed forecasts.
Distance and duration are included. Differences against ranges use their midpoint.
These display comparisons do not alter prediction_valid, evaluation history or
learning eligibility. Imported plans without pace/HR/RPE retain missing values.

Validation after this addition: 134 pytest tests and mobile browser review passed.
