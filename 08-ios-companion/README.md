# StrideAI Apple Health companion

This lightweight iPhone app reads three HealthKit types with explicit permission:

- Sleep Analysis
- Resting Heart Rate
- Heart Rate Variability (SDNN)

It aggregates samples on the phone and sends daily summaries to the protected StrideAI API. Strava remains the source for running activities.

## Why a companion app is required

Apple Health does not expose a server API to the Railway web application. HealthKit reads must happen inside an authorized iOS app on the user's iPhone.

## Build and install

An Apple Developer account is required to sign an installable iPhone build. EAS Build can perform the iOS build in the cloud, so a Mac is not required.

```bash
cd 08-ios-companion
npm install
npx eas-cli login
npx eas-cli init
npx eas-cli build --platform ios --profile preview
```

`eas init` adds the EAS project ID to `app.json`. During the first iOS build, EAS prompts for Apple Developer signing credentials and device registration for an internal build. Install the resulting build link on the registered iPhone.

In the app:

1. Keep the server URL as `https://stride-ai.app`.
2. Enter the same private access key used by the StrideAI web app.
3. Tap **Authorize & sync Apple Health** and allow the three requested read permissions.

The access key and device identifier are stored in the iOS Keychain through Expo SecureStore. A successful sync backfills up to 35 days and later app launches refresh the summaries automatically.

This app requires a custom development or signed build. It cannot run inside Expo Go because HealthKit is native code.
