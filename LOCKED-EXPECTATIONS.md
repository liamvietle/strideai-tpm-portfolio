# Revised workout expectations

The original plan is retained for audit. New predictions use the current revised
workout. A check-in distance saved after the latest plan change can supersede that
workout when locking expectations; a later calendar swap wins over a stale check-in.
Changes are audited, and locked predictions remain immutable. Structured intervals
require editing the plan instead of silently scaling a check-in distance.

Legacy execution comparisons recover the last audited workout prescription before
execution recording, rather than always showing original_json. This repairs swapped
distance displays without fabricating predictions or rerunning old evaluations.
New executions already freeze target_snapshot. No schema or configuration changes.

Historical estimates use up to 20 prior runs from the preceding 180 days, within
20% of target distance and 15% of target pace when present. Easy/long runs exclude
known races, hard sessions, reported effort above 5 and HR above 85% of known max.
Unlabelled sessions may remain uncertain. Other intensity types require matching
session labels. Evaluated manual runs are included. Current-day/future activities
are excluded. Each metric requires three observations; median estimates and robust
descriptive ranges are stored with counts, sources and evidence IDs. RPE is only
learned from reported effort. Missing history falls back to explicit target-based
estimates when supported, otherwise null. These estimates are not yet adjusted for
heat or terrain and are not calibrated probability intervals. Health influences
the recommended workout and uncertainty rather than an invented numerical HR shift.

Prediction evidence exposes per-metric coverage and limitations. Reopening a locked
prediction never recomputes it from later results. Tests: 143 passed; mobile review
flow passed. Existing reductions are not undone by this display/prediction change.

## Weather and terrain conditioning

Historical weather from activity_weather and Strava total ascent now support
condition-matched estimates. The pre-run forecast saved with the daily check-in
supplies apparent temperature; an optional route-details field supplies expected
ascent (zero means flat; blank means unknown). Shortened recommendation candidates
assume proportional ascent, preserving the entered ascent per kilometre.

For the existing comparable pool, match apparent temperature within 3°C and ascent
per kilometre within max(3 metres/km, 30% of expected ascent density). When both
conditions are supplied, require both. Each metric needs three matching observations
to replace its baseline. Preserve baseline, delta, matching IDs, coverage and input
conditions in the locked prediction. No forecast or missing altitude is not treated
as cool or flat. Insufficient coverage preserves baseline explicitly. HR and RPE
are not assigned invented universal heat/hill multipliers. Existing weather safety
rules still restrict candidates before prediction.

These descriptive matches supersede the earlier lack of condition adjustment;
they do not isolate causal heat versus hill effects, model grade profiles, technical
surface, net descent or wind direction. Thresholds are product matching heuristics.
Validation: full 143-test suite passed, plus two added condition-matching tests;
mobile review flow passed. No additional provider credentials or schema changes.
