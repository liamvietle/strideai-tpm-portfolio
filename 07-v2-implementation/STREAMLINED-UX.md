# Streamlined daily coaching and race weather

- Daily check-in no longer asks for days until the target race. The recommendation service derives this from the saved race and check-in date, scoped to the athlete.
- One feeling selector replaces the numeric soreness input. Sore muscles maps to the existing moderate-soreness category (5), and movement-affecting soreness maps to severe (8), preserving the recovery-only guardrail. These are category encodings, not measured scores. Fatigue-only selections leave soreness unknown. Pain remains separate. Legacy numeric APIs remain supported.
- Optional health measurements, run weather, prediction evidence, detailed splits, historical health and basic outcome entry use collapsed disclosures. Athlete Intelligence moves to Progress under “What StrideAI has learned”; traits without observations do not clutter that list. It continues feeding coaching in the backend.
- Race goals accept an optional confirmed location (name, coordinates, IANA time zone) and local start time. Training timezone remains independent. Existing saved goals need no backfill.
- Weather fetches automatically when race estimates load. Within seven days, use race-hour forecasts. Otherwise sample the same calendar week over three past years, clearly labelled historical conditions, not a race-day forecast or climate normal. Race hours include estimated finish duration and midnight crossings.
- Weather affects the slower end of the estimate range only. Unknown PB weather prevents a defensible normalization of the central estimate. The explicit experimental allowance is 0.4% per apparent-temperature degree over 20°C, capped at 8%. This is a product uncertainty heuristic, not a validated performance or safety model. Failures apply no weather adjustment.
- Additive storage: optional fields in existing race-goal JSON; lazy `race_weather_cache(cache_key, result_json, expires_at)` table. Six-hour successful cache, five-minute failure cache. No new environment variables.
- No changes to Strava sync, account isolation, Apple Health ingestion or plan activation.

Provider references: https://open-meteo.com/en/docs and https://open-meteo.com/en/docs/historical-weather-api.

Validation: Python regressions cover weather source switching, caching, outages, midnight hours, location/timezone round-trip, athlete scoping and automatic race countdown with severe-soreness safety. Mobile browser covers setup, generated/imported plans, simplified inputs, race location selection, prediction and post-run evaluation. Weather UI uses provider doubles; tests do not depend on a live weather service.

## Guided Today flow

Today now presents the next saved step: check in, review the run, run and record, then review and learn. Workout guidance and execution forms render inline; no tab changes are needed. Session fields stay collapsed unless an imported session needs intensity or a non-running activity needs confirmation. Prediction and execution forms are separated. Already-completed runs can skip prediction explicitly. The current step is derived from stored check-ins, predictions, choices and results, so it survives reloads.

Calendar, progress and profile are secondary menu destinations with a return-to-Today action. Weekly review is also available directly from Today. Non-running days retain the shorter check-in flow and do not imply completion from a check-in alone.

Additional mobile verification: generated and imported full loops without navigation between steps, reload after accepting a target, tennis/strength check-in, and recording a run with no prior prediction. 114 backend tests still pass.
