# Athlete learning loop

This change adds a persistent coaching loop to the existing FastAPI personal app. The original recommendation API, Strava OAuth/sync, Garmin ingestion, health check-in, non-running days and weather workflows remain available.

## Use the loop

1. Open **Athlete**. Save the information you have. All biometrics are optional; availability defaults to three days and a 60-minute session limit. Change these to your actual availability. Historical activities come from existing ingestion. Additional CSV/TCX and dated health observations can be imported here.
2. Save the race, date and time goal in **Plan**. Race priority is set in Athlete.
3. Open **Coach**, choose a start date and generate a first-pass plan. Replacing a plan requires the explicit replacement checkbox. Past and locked sessions retain their records.
4. Open today's workout and use its distance/intensity in the existing recovery check-in. Save the check-in, then **Lock pre-run expectation** before starting. Predictions cannot be created for past/future days or after today's run has already been ingested.
5. Review execution instructions, pace/HR/RPE, uncertainty, warnings and effects on the remaining week. Accept or decline. The choice is immutable; a declined safety warning remains a warning.
6. After syncing, link the exact run or enter actual distance/time. Add RPE, completion and pain; optionally enter full-run splits. Save and evaluate. A recorded execution can be evaluated again safely after an interrupted request.
7. Review Expected vs Actual, learned traits and future changes. Open **Review** for mileage/load, key sessions, recovery, new observations and next-week changes.

The legacy Plan screen remains a snapshot/progress view. **Coach is authoritative for live workout revisions.** Changing a race goal does not silently regenerate its workouts; generate a new first pass explicitly.

## Planning and analytics

- Initial volume uses 28-day running history when sufficiently covered, otherwise reported weekly distance, otherwise a conservative 9 km/week starting assumption. Availability and maximum session time cap volume. Zero reported mileage produces recovery days until the athlete updates their starting volume.
- A capped progression, regular easier weeks and a race-priority taper provide an initial structure. This is a heuristic first pass, not a validated race-performance prescription. Short preparation time or low baseline volume is flagged for review.
- Threshold pace, recent observed pace or a dated recent PB can seed provisional pace. Unknown pace/HR remain null. Race ambition never becomes a fitness estimate. Height, weight, sex and VO2max are recorded but do not currently drive prescriptions.
- Key sessions carry purpose and targets. Threshold sessions distinguish work segments from whole-run averages. Missing comparable whole-run evidence does not produce a fabricated interval/race pace prediction.
- Prospective expectations are immutable and separate from original plan, current plan, user choice and execution. Comparisons have signed pace (sec/km and percent), HR and RPE errors. Positive pace error means slower; positive HR/RPE means higher response.
- Faster alone is not “better.” Better requires lower effort, normal HR and controlled pace. Materially different pace without physiological deterioration is labeled different execution, not forced into a success/failure verdict.
- HR drift uses speed/HR decoupling across split halves only for steady easy/long runs with at least four full-coverage splits, HR in every split and pace CV ≤10%. Pace consistency uses split pace CV. Summaries alone cannot supply drift.
- Accepted adjustments revise the remaining week's unlocked key sessions without redistributing missed mileage. Pain/strained outcomes protect the following seven days, with an append-only change log. Pain also marks the profile's active-injury flag; reassess it before regenerating running sessions.
- Evaluated executions backfill existing outcome metrics only if no independent legacy outcome already exists.

## Athlete learning

Traits include paired easy-run HR/pace medians, HRV variability, poor-sleep completion associations, observed weekly volume, long-run/threshold completion, race HR and post-long-run soreness. Each includes sample count, confidence, evidence description and observation date. Historical-review calculations do not overwrite current traits.

A moderate reduction can become less conservative only for an easy run with at least five comparable prospective successful declines, normal HR/effort, no pain, and good next-day recovery evidence. Matching requires workout type, distance, identical fatigue factors, similar sleep and recent load. At least 80% of the available matched cases must qualify. Accumulated recovery debt, load warnings, severe fatigue and injury cannot be relaxed. These conservative thresholds are implementation heuristics requiring prospective calibration, not proof of causal treatment effects.

Outcome retrieval is flat and bounded; prior AI evidence packages are never recursively embedded in later packages. Repeated evaluation does not increment samples twice. No learning is inferred from acceptance/decline alone.

Heat sensitivity, HRV readiness-predictor reliability and broader recovery kinetics remain collecting traits. Fitness trend is an observational easy-pace comparison only when sufficient similar-HR low-effort sessions exist; otherwise the review explicitly says evidence is insufficient.

## AI architecture

The existing explanation-only layer is preserved. A separate optional coach layer can **select** between deterministic safe candidates using profile, health state, recent load, race phase, planned workout, learned traits, matched prior recommendations, choices and outcomes.

The server constructs all candidate distances, intensity limits and targets before calling the model. The Responses API returns a strict structured candidate ID and evidence IDs. The server validates candidate membership and citations; it never accepts model-authored numbers or free-form prescriptions. The athlete sees deterministic instructions for the validated selection. Provider errors, unknown candidates, unsupported citations or missing configuration use a labeled deterministic fallback. Full model chain-of-thought is neither requested nor stored.

Calls use `store: false`, a 20-second timeout and no tools. Raw activity payloads, precise locations, credentials and identifying profile fields are excluded. Structured health/training information is sent when the feature is enabled. Trace metadata includes prompt version, model, latency, fallback status and evidence references. A live provider call must be verified in the configured deployment; local tests mock the provider and exercise valid, invalid and unavailable responses.

## Configuration

| Variable | Meaning |
|---|---|
| `STRIDEAI_DB_PATH` | Existing SQLite database on the persistent volume; unchanged |
| `STRIDEAI_APP_KEY` | Existing personal-app access key; protects new endpoints too |
| `OPENAI_API_KEY` | Existing server-side OpenAI credential |
| `STRIDEAI_COACH_AI_ENABLED` | `true` enables the new candidate-selection layer; default `false` |
| `STRIDEAI_COACH_MODEL` | Optional override; otherwise existing `OPENAI_MODEL`, then the app's default model |

There are no new Python runtime dependencies, Strava scopes, Garmin requirements or scheduled jobs. Browser smoke testing uses Playwright separately from production dependencies.

## SQLite migration

Startup calls the idempotent `init_athlete_db`. It creates only new tables and indexes; existing tables and activity payloads are not rewritten. The existing storage schema remains version 3; the independent `athlete_loop_migrations` ledger records version 1.

| Table | Purpose |
|---|---|
| `athlete_profiles` | Optional validated profile and update timestamp |
| `coach_workouts` | Original/current workout JSON, race, date, lifecycle and active revision |
| `coach_predictions` | Immutable pre-run prediction/evidence and legacy recommendation link |
| `coach_decisions` | Accept/decline and timestamp |
| `coach_executions` | Actual metrics, optional activity ID and source |
| `coach_evaluations` | Immutable comparison, errors and resulting changes |
| `coach_traits` | Recomputed structured traits with evidence/sample counts |
| `coach_plan_changes` | Append-only before/after snapshots, reason and originating session |
| `athlete_loop_migrations` | Migration ledger |

A partial unique index permits one active workout per athlete/date. A second unique index prevents one activity from being linked to multiple workouts for the same athlete. Mutation transactions protect prediction locks, decisions, execution/evaluation and plan changes. All activity links verify ownership, running type and local date.

Before deploying, take a normal SQLite backup of the persistent database. Running the prior application remains possible because its schema is unchanged; leave the additive tables in place. Do not replace the live database with a test database.

## Verification

Run from `07-v2-implementation`:

```sh
python -m pytest -q
python -m app.evaluation evaluation/cases.json
python -m app.quality evaluation/cases.json evaluation/baseline-m3.json
python -m app.real_validation evaluation/real-validation-sanitized.json
```

The new suite covers partial profiles, plan bounds, cold starts, the full loop, immutable/idempotent writes, safety propagation, imported health history, late predictions, wrong-athlete activity links, split validation/drift, future dates, AI constraints, learning eligibility, migration repeatability and existing access protection.

## Later phases and boundaries

- Automatic Strava stream/lap retrieval; currently link activity summaries and enter splits for drift. No real-time watch coaching.
- Better heat/terrain matching, calibrated prediction intervals, HRV predictor reliability, recovery kinetics and prospective model evaluation.
- Automatic race-effort recommendations, multi-race scheduling and advanced interval-periodization.
- Audited corrections to locked execution/evaluation records; current records intentionally cannot be overwritten.
- Automatic live-plan revision after editing a goal/profile or manually editing the legacy plan. Currently regenerate future unlocked workouts explicitly.
- Missing runs remain unknown. RPE-load coverage is shown; non-running activity remains supported in ingestion/check-ins but is not mixed into running distance or running load.
- Manual entries without a timestamped wearable start are self-reported prospective evidence. Imported summaries with unknown time zone are not scored against a supposedly pre-run prediction.
- Cross-provider duplicate imports are not automatically merged. Link the correct activity and avoid importing the same run from multiple providers when interpreting totals.
- Existing app-key access is a single-user gate, not multi-tenant authentication.

The mobile browser smoke test is `tests/browser_smoke.cjs`. With Playwright and Chromium installed, start the app against a fresh temporary database at `127.0.0.1:8765`, then run `node tests/browser_smoke.cjs`. Optional `CHROMIUM_EXECUTABLE` points to an installed Chromium. It exercises profile → race → plan → check-in → prediction → acceptance → execution/evaluation → review at 390 px width, rejects coach API errors/JavaScript errors and checks horizontal overflow. Do not run it against a real athlete database.
# Combined calendar and forecast additions

The existing athlete loop remains authoritative. Optional `long_run_day`,
`include_strength`, and `strength_days` extend its profile JSON without replacing
existing profiles or locked workouts. Strength supplements respect the session
time cap and are omitted during active injury and race week.

Plan generation supports custom, today, next-Monday and recommended starts, with
an optional 1–32 week race-specific block for the recommended start option.
`GET /app/api/coach/plan-setup` returns the suggested duration and date.

`GET /app/api/coach/race-prediction` exposes a provisional race-equivalence
estimate from dated PBs within 180 days. Newer performances replace stale anchors.
Daily snapshots use the additive `coach_race_forecasts` table. The displayed range
is heuristic, not calibrated. Workout completion alone does not change the time
estimate; evaluated workouts continue to feed the existing athlete-learning loop.
No extra environment variables are required.
