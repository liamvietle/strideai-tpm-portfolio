# Race outlook and coaching questions

This version adds an expandable **Ask your coach** panel on Today. Suggested questions, free text, an optional completed-session selector, and follow-ups share the same flow. Answers include a suggested next step and expandable evidence/source links. They do not edit the training plan.

## Question architecture

- Athlete identity is injected by the existing account middleware. Workout selection, answer retrieval, history and follow-up parent IDs are checked against that athlete.
- Retrieval uses a 180-day window, question words, optional selected-session type, and recency. Up to ten evaluated sessions plus ten recent unlinked runs are supplied. This is deterministic retrieval, not embedding search. Selected workout details and joint pace/HR analysis are included.
- Context also includes current profile measurements, up to 14 recent check-ins, six-week training trend/volume, seven upcoming sessions, up to four prior exchanges and race outlook for race-related questions. Raw Strava payloads, credentials and route coordinates are excluded.
- Four curated research references provide short summaries and explicit limitations. The model must distinguish athlete observations from possible explanations and general research. References are not searched live on each question.
- The existing Responses API configuration is reused with `store:false`, structured output, allowed evidence IDs, and code-owned next steps. Unknown citations/actions are rejected. Model text is still probabilistic and needs ongoing evaluation. No claim-level entailment validator is implemented.
- Profile/recent check-in pain and recent recovery restrictions constrain next steps. A small English symptom phrase check routes certain urgent concerns to urgent guidance. This is not comprehensive medical triage; prompts also prohibit diagnosis or encouraging training through pain.
- Up to 20 new questions per rolling 24 hours, a 15-second interval, and a per-input claim prevent duplicate concurrent requests. Successful answers cache for an hour. Failed AI answers can retry after one minute and explicitly show a data summary. Client polling stops after 45 seconds; stale claims can retry after 90 seconds.

## Schema/configuration

One additive SQLite table, `coach_questions`, stores athlete/question/workout/parent IDs, context fingerprint, creation time and answer JSON (including evidence and provider trace). An athlete/time index supports history and limits. Created automatically on use. Rows older than 90 days are removed when that athlete submits another question. The existing daily `coach_race_forecasts` table is reused.

No new environment variables. Existing `STRIDEAI_COACH_AI_ENABLED`, `OPENAI_API_KEY`, and `STRIDEAI_COACH_MODEL` (or `OPENAI_MODEL`) apply. Questions incur normal provider usage. No additional provider or vector database is required.

## Race estimate changes

A same-distance performance within 90 days is preferred. Otherwise recent race-equivalent estimates are weighted by recency and distance similarity. Older anchors, differing estimates, and short-race-to-marathon extrapolation widen the planning range. The latest pre-today daily forecast supplies the displayed change.

Six-week training comparisons now include synced easy-like runs screened against saved maximum HR, without requiring reported effort. Existing linked runs are not double counted. Matching uses HR, duration, reported effort when available, and available temperature/ascent. At least three distinct dates per period and 21 days between the earliest/latest samples are required. Half the observed pace change can adjust the anchor, capped at ±3%. Only training after the selected anchor contributes to that adjustment.

Weather retains the existing distinction: forecasts within seven days, three prior years' seasonal samples further out. Similar-temperature historical easy-like runs now provide context. Weather broadens the planning range rather than applying an unvalidated individual time penalty. Volume and longest run are shown as support, not automatic time gains. Missing uploads are not counted as proof of missed training.

## Limits and next phase

The predictor is still heuristic, not a validated accuracy improvement or calibrated probability interval. It does not assume future gains between today and race day. Race-labelled sessions may be submaximal. Course, race-specific endurance, personal heat response, and future taper effects need better modelling and validation. Next work: prospective forecast-vs-race outcome calibration, explicit all-out/training race labels, more condition-matched performance anchors, broader reviewed knowledge, richer retrieval and controlled plan-change proposals.

Validation covers account/CSRF isolation, selected execution retrieval, follow-up context, rate limits, fallback/caching, unsupported citations, safety actions, no plan mutation, training without ratings and weather-confounded comparisons. Mobile UI is tested on an isolated local database. Live private data and live model prose are not used for these tests.
