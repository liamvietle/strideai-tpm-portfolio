# Strava run details and effort

## What changes

The Strava detail lookup previously called `/athlete/activities/{id}`, which is not the single-activity endpoint. It now requests `/activities/{id}` and `/activities/{id}/streams` for time, distance, heart rate and moving flags. It imports available metric pace splits, laps, HR splits, Relative Effort (`suffer_score`) and reported effort (`perceived_exertion`). No GPS coordinates are requested by this feature.

Streams are normalized into kilometre splits including the partial final kilometre. HR is time-weighted, with at least 95% HR interval coverage required within a split. Full-run distance and moving-time totals must match within the existing tolerance. Mismatched arrays, non-finite values, large gaps and implausible speed jumps are rejected. Metric splits or full-run laps are fallback sources. Laps with better HR coverage can supply HR analysis while metric pace splits remain available separately. Overall average HR is never copied into individual splits.

Pace variation and HR drift are computed when coverage permits. Drift requires at least four HR splits, steady pacing and an easy, long or unclassified custom session. Known threshold/race sessions remain excluded. These are descriptive measures, not proof of adaptation.

## Effort throughout the coaching loop

- Manual RPE entry is removed from workout and legacy outcome forms. Imported effort appears in run review.
- Relative Effort retains its native workload-score units. Reported effort is a separate optional 1–10 rating, never synthesized from Relative Effort.
- Prospective Relative Effort estimates require at least three earlier runs matched by distance, pace and duration. Estimates are frozen with existing pre-run prediction snapshots.
- Expected-versus-actual includes Relative Effort when available. Older results may use clearly labelled retrospective estimates.
- Missing reported effort no longer blocks pace/HR expectation comparisons or descriptive easy-run HR/pace traits. Missing splits only limits split-based analysis.
- Weekly review shows summed Strava Relative Effort and coverage. Athlete intelligence records workload-score patterns.
- Bounded recommendation learning can use comparable prospective Relative Effort outcomes plus the existing physiological and next-day recovery requirements when a reported rating is absent. Relative Effort and HR are not treated as independent strain signals.
- LLM context includes imported effort/splits and updated analytics. Prompt instructions distinguish workload from perceived exertion, forbid guessing why the athlete changed distance, and avoid internal terms such as `prediction_valid`.

Historical `rpe` fields, old ratings, legacy API inputs and old load fields are retained for compatibility and audit. The visible product no longer requires RPE input. Removing stored historical ratings or relabelling Relative Effort as a subjective rating would destroy useful provenance.

## Safe refresh and schema

Two additive SQLite tables are created automatically: `strava_run_details` and `strava_detail_sync`. Enriched data lives separately from activity summaries so subsequent summary syncs cannot erase it.

Existing linked/evaluated runs receive a read-time enrichment in the UI, coach evidence and athlete observations. Saved execution/evaluation JSON, prediction snapshots and already-applied plan changes remain unchanged. New split analytics are labelled as refreshed. Importing late details does not rerun old plan adjustments.

Each sync imports at most three eligible running activities (up to six detail/stream requests), with a five-minute per-athlete cooldown and an approximate time budget. Recent runs refresh on a six-hour cycle; older runs refresh on a thirty-day cycle. Never-enriched historical runs are filled in newest-first across subsequent syncs. Rate-limit headers and 429 responses stop enrichment. Failures retain existing summaries and valid saved details. Strava not supplying a score, HR stream or splits remains a real coverage limitation.

No new credentials or environment variables. Existing Strava permissions and authentication are reused. Non-running activity ingestion and health workflows remain intact. Backfill runs during existing app-triggered syncs, not as a new server scheduler.

## Validation

169 Python tests pass, including new cases for full/missing/malformed streams, pace and lap fallback, effort source separation, late enrichment of evaluated runs, unchanged decision history, tenant isolation, summary refresh persistence, rate limits and bounded backfill. Existing quality and sanitized fatigue regression gates pass. Mobile checks cover synced review with no subjective rating and imported effort/HR split display.

Provider requests are mocked in tests. Live coverage depends on what Strava returns for each authorized activity and needs checking after deployment. The first sync will not backfill an entire historical archive at once.
