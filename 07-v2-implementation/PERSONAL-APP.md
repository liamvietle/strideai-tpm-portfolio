# StrideAI Personal App v1

This is the personal-use StrideAI application for daily training decisions and prospective validation.

## Daily workflow

Every day can have a recovery check-in, including rest and cross-training days.

### Running day

1. Open `/app` on a phone or browser. StrideAI refreshes connected Strava activity history automatically.
2. Choose **Run** and enter the planned distance/intensity.
3. Enter morning recovery data. Sleep is entered as `HH:MM`, matching Garmin Connect.
4. Record the athlete's own decision **before** revealing StrideAI.
5. Submit once. The morning decision becomes locked for that calendar date.
6. Review the StrideAI recommendation, accumulated-fatigue state and explanation.
7. After the run, record completion, RPE, whether StrideAI was followed, any override, pain and notes from **History**.

### Rest or non-running day

1. Choose **Rest / recovery day**, Strength, Cycling, Tennis, Football or Other.
2. Enter the same morning recovery signals.
3. Optionally add a short activity note, such as `60 min tennis`.
4. Save the recovery check-in.

These days do not receive a run-specific volume/intensity recommendation. They still feed the rolling recovery history used by future running recommendations.

## Recovery inputs

Morning wellness values currently remain manual while Garmin API access is pending:

- sleep (`HH:MM` in the UI, converted internally to hours)
- HRV
- Garmin HRV baseline low/high
- resting heart rate
- soreness
- pain/injury concern
- subjective fatigue

Prior daily check-ins are loaded automatically into the 3-day/7-day accumulated-fatigue assessment.

## Strava activity data

StrideAI connects to Strava through OAuth 2.0. Once connected, the browser refreshes Strava automatically when the app is opened; **Sync now** remains as a fallback.

All recent Strava activity types are stored, including runs and cross-training activities. The current recent-load proxy intentionally remains run-specific:

```text
prior 7-day running distance
----------------------------
prior 28-day weekly average running distance
```

Cross-training is retained for future modeling but is not converted into arbitrary running-equivalent kilometers.

## Personal-data boundary

The app stores:

- daily recovery check-ins, including rest days
- planned activity type and optional notes
- the athlete's pre-recommendation decision on running days
- StrideAI recommendations and explanations
- Strava activity summaries across activity types
- post-run outcomes and overrides
- Strava OAuth tokens in the private production database

The public repository contains no personal production database or Strava secrets/tokens.

## Access protection

For an internet deployment, set:

```text
STRIDEAI_APP_KEY=<long random private value>
```

The HTML shell and `/health` remain reachable, while personal data/API endpoints require the key in the `X-StrideAI-Key` header. The web interface stores the key only in that browser.

This is lightweight protection for a single-user prototype, not production-grade account authentication.

## Strava configuration

Set these on the deployment platform, never in GitHub:

```text
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
STRAVA_REDIRECT_URI=https://<domain>/app/api/strava/callback
```

The app requests `read,activity:read_all`, persists rotating access/refresh tokens in SQLite and refreshes access tokens automatically.

## Local use

```bash
cd 07-v2-implementation
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/app
```

Optional environment variables:

```text
STRIDEAI_APP_KEY=...
OPENAI_API_KEY=...
STRIDEAI_DB_PATH=data/strideai.db
```

Without `OPENAI_API_KEY`, StrideAI uses the deterministic explanation fallback.

## Railway deployment

The Dockerfile is suitable for a small personal deployment.

1. Deploy the GitHub repository with root directory `07-v2-implementation`.
2. Add a persistent volume at `/app/data`.
3. Set `STRIDEAI_DB_PATH=/app/data/strideai.db`.
4. Configure `STRIDEAI_APP_KEY` and the Strava variables above.
5. Use `/health` as the health-check path.
6. Open `/app` and save the private access key in each browser/device.

The persistent volume is required so check-ins, activity history and OAuth tokens survive deployments and restarts.

## Deliberate current limits

- single athlete (`viet`) in the UI
- no user accounts or password recovery
- no direct Garmin OAuth/API synchronization yet
- Garmin morning wellness values are entered manually
- Strava refresh is app-triggered rather than a server-side webhook push
- cross-training is stored but not yet converted into the run-load metric
- no push notifications
- no native iOS/Android application
- SQLite is used instead of a managed cloud database

These boundaries keep the product useful without prematurely turning a personal validation app into a commercial platform.

## Recent activities and weather

Data > Recent Activities shows the newest 30 synced Strava activities, including
non-running activities. Activity times use the browser's local time zone. Missing
metrics are omitted, not shown as zero. Running cadence converts Strava's cycle
cadence to steps/min. Names are rendered as text, never HTML.

Each successful app-triggered Strava sync queues best-effort weather enrichment
using already stored summary payloads. No additional Strava requests are needed.
Open-Meteo receives only start coordinates, UTC date and requested weather fields.
Indoor/trainer and virtual activities are excluded. No location or valid UTC time
means no lookup. Weather estimates represent the start location and containing
UTC hour, not the whole route or watch measurements. Recorded Strava temperature
is shown separately.

Activities under seven days old use Open-Meteo's forecast/past-day model data;
older activities use its historical reanalysis API. Results are cached in a new
activity_weather table. Existing activity IDs, raw data, recovery records and
recommendations are unchanged. A changed time/location invalidates the cache.
Failures remain unavailable and become eligible for retry after six hours.
Background work is bounded to 20 requests and a 20-second scheduling budget per
sync (an in-flight request can finish after that budget). Historical backfill
continues on later syncs, newest first. Restarted jobs resume on the next sync.
One worker per process prevents duplicate work in this single-process deployment.
The UI refreshes after sync and again after 25 seconds; Refresh activities can
also retrieve the latest result. Weather never enters recommendation inputs.

References: https://open-meteo.com/en/docs and
https://open-meteo.com/en/docs/historical-weather-api . The free API is for this
non-commercial personal app; review provider terms before commercial rollout.
