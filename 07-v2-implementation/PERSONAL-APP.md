# StrideAI Personal App v1

This is the first version intended for daily personal use during a training block.

## Daily workflow

1. Open `/app` on a phone or browser.
2. Enter the planned session and morning recovery data.
3. Record the athlete's own decision **before** revealing StrideAI.
4. Submit once. The morning decision becomes locked for that calendar date.
5. Review the StrideAI recommendation, accumulated-fatigue state and explanation.
6. After the run, open **History** and record completion, RPE, whether StrideAI was followed, any override, pain and notes.

The next morning automatically uses prior check-ins as recovery history. The user does not manually build `recovery_history` arrays.

## Garmin activity data

Use **Data → Garmin activity data** to upload the Activities CSV exported from Garmin Connect.

Imported running distance is used to derive the recent-load proxy:

```text
prior 7-day running distance
----------------------------
prior 28-day weekly average
```

If no usable activity history exists, the load signal is left missing unless the user enters a value manually.

## Personal-data boundary

The app stores:

- morning recovery check-ins
- planned workouts
- the athlete's pre-recommendation decision
- StrideAI recommendations and explanations
- imported Garmin/Strava activity summaries
- post-run outcomes and overrides

The public repository contains no personal production database.

## Access protection

For an internet deployment, set:

```text
STRIDEAI_APP_KEY=<long random private value>
```

The HTML shell and `/health` remain reachable, while all data/API endpoints require the key in the `X-StrideAI-Key` header. The personal web interface stores the key in that browser and sends it with API requests.

This is lightweight protection for a single-user prototype, not production-grade account authentication.

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

The current Dockerfile is suitable for a small personal deployment.

1. Create a Railway project from the GitHub repository.
2. Set the service root directory to `07-v2-implementation`.
3. Let Railway build from the Dockerfile.
4. Add a persistent volume mounted at `/app/data`.
5. Set `STRIDEAI_DB_PATH=/app/data/strideai.db`.
6. Set a strong `STRIDEAI_APP_KEY`.
7. Optionally set `OPENAI_API_KEY` for generated explanations.
8. Set the health-check path to `/health` if desired.
9. Generate a public domain and open `/app`.
10. Enter the same access key in **Data → Private access key** on each browser/device you use.

A persistent volume is important because SQLite data must survive deploys and restarts.

## Deliberate v1 limits

- single athlete (`viet`) in the UI
- no user accounts or password recovery
- no direct Garmin OAuth/API synchronization
- morning wellness values are entered manually
- Garmin activity CSV is uploaded periodically
- no push notifications
- no native iOS/Android application
- SQLite is used instead of a managed cloud database

These boundaries keep the product useful without turning a personal validation app into a commercial platform prematurely.
