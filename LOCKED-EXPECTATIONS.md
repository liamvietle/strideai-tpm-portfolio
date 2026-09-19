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
