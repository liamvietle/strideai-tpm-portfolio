# Personal coaching before and after each run

The workout now leads with a short **Your coach** message. Before running it connects the saved check-in, recovery/load, race phase, comparable outcomes, weather and prescribed workout. After evaluation it interprets the actual run against prior comparable sessions and explains a permitted next step. The comparison table stays available in a collapsed disclosure.

The LLM writes three evidence-linked insights: the main interpretation, historical context, and what this observation contributes to learning. It selects a next-step ID from a code-owned menu. Availability-related shortening can prompt schedule planning rather than a fatigue conclusion. Missing RPE can prompt effort recording next time. Pain and recovery reductions restrict the menu. Existing numerical prescriptions and hard safety decisions are unchanged.

## Data and AI architecture

- New authenticated, CSRF-protected `POST /app/api/coach/workouts/{id}/briefing` endpoint. Existing per-user middleware and ownership lookup apply before cache access.
- New additive SQLite table `coach_briefings`, created lazily on first use. Key: athlete, workout, pre/post stage, context fingerprint. Stores commentary, evidence, prompt version, provider/model, timestamp and returned token usage.
- Identical inputs reuse the saved response, including failures. Concurrent calls share an in-flight claim; stale claims can recover after 90 seconds. Explicit retries of failures have a 60-second cooldown. Successful entries are reused even on retry.
- Generation starts when the relevant workout card opens. Pending messages poll the cache briefly without repeating the provider request. It runs outside SQLite write transactions. No new inference is triggered simply by background Strava ingestion.
- Uses the existing Responses API, `STRIDEAI_COACH_AI_ENABLED`, `OPENAI_API_KEY`, and `STRIDEAI_COACH_MODEL` (fallback `OPENAI_MODEL`). No new variables required. `store=false`, low reasoning effort, 2,400 output-token cap, 25-second request timeout.
- The previous candidate-selection model still selects pre-run recommendations. This new request interprets those choices and selects an approved coaching next step. It does not replace the numerical estimator or automatically rewrite future sessions.
- Post-run retrieval excludes the current day and future activities from historical comparators. Retrospective estimates remain distinct from locked prospective predictions. Current profile safety state and upcoming plan are identified as current context.
- AI narratives do not feed back into the numerical athlete model as facts. Existing deterministic observation learning continues. Schema validation checks action IDs and evidence references, but is not a semantic proof of every prose assertion.

## UX and failure behavior

The card shows the model when commentary succeeds, or explicitly says saved guidance is being used when AI is unavailable. Sources, learning, uncertainty and matching run examples are expandable. Failed requests never block check-ins, execution recording or evaluation. The AI action text is rendered from the approved menu rather than arbitrary model-authored prescriptions. DOM content uses textContent.

## Validation

154 Python tests passed. New coverage includes pre-run caching, account isolation, injury restrictions, retrospective history cutoff, unchanged evaluations/plans, unsupported AI actions/citations, token usage capture, pending requests and quota failure. Provider responses are mocked; this does not claim live-model coaching quality has been verified. Existing evaluation, quality-regression and sanitized fatigue gates passed.

Mobile browser checks cover automatic Strava linking, review without RPE, visible fallback coaching, compact comparison details, and the guided pre-run/post-run flow. The old journey test selectors were updated to match the current sync/manual-entry UI.

## Later work

Review live model outputs with real athlete cases after deployment. Add an explicit qualitative coaching evaluation set and cost/quality monitoring. Longer coach conversations, model-proposed multi-session changes with review/acceptance, and AI weekly narratives are separate follow-ups. This release provides individual pre/post-run interpretation and constrained next steps.
