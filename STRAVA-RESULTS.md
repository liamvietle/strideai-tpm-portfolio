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
