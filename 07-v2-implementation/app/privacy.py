"""Public privacy notice for the personal StrideAI deployment."""

PRIVACY_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="How StrideAI handles training, recovery and connected activity data.">
<title>Privacy Policy | StrideAI</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f4f7f8;color:#183039;font:17px/1.7 system-ui,sans-serif}
main{max-width:820px;margin:40px auto;padding:40px;background:white;border:1px solid #dce6e8;border-radius:20px}
a{color:#087469;text-underline-offset:3px}a:focus-visible{outline:3px solid #087469;outline-offset:4px}
.brand{font-weight:750;letter-spacing:-.03em}h1{font-size:clamp(2.2rem,6vw,3.4rem);line-height:1.1;margin:24px 0 16px;letter-spacing:-.045em}
h2{font-size:1.25rem;margin-top:32px;line-height:1.4}.meta{color:#566b72}.intro{font-size:1.15rem}li{margin:8px 0}
footer{border-top:1px solid #dce6e8;margin-top:32px;padding-top:20px}@media(max-width:600px){main{margin:12px;padding:24px;border-radius:14px}}
</style></head><body><main>
<a class="brand" href="/app">StrideAI</a>
<h1>Privacy policy</h1>
<p class="meta">Effective date: 19 September 2026</p>
<p class="intro">StrideAI is an early-stage personal running-coach application operated by Viet Le in Vietnam. This notice explains how information is handled when you use StrideAI at stride-ai.app.</p>
<h2>Information we handle</h2>
<ul>
<li><strong>Training and recovery inputs:</strong> athlete identifier, race goals, training plans, workout dates, distance and intensity, sleep, heart-rate variability, resting heart rate, soreness, pain indicators, fatigue, training decisions, and outcome notes you provide.</li>
<li><strong>Connected activities:</strong> after you authorize Strava, we receive your Strava athlete identifier and name, authorization tokens and permissions, and activity summaries. These can include activity names and types, dates, distance, duration, heart rate, elevation, cadence, and location or route information included in the source summary. Private activities are included if you grant that permission. Activity summaries are stored for training-history and recovery features.</li>
<li><strong>Uploaded activities:</strong> information parsed from Garmin CSV or TCX files you choose to upload. Direct Garmin Connect API access is not currently enabled.</li>
<li><strong>Imported Garmin recovery summaries:</strong> sleep duration, resting heart rate, HRV values and their Garmin baseline limits, with their original dates. We store only these selected recovery fields from prepared export files, separately from activity history. Direct Garmin API access is not enabled.</li>
<li><strong>Apple Health recovery summaries:</strong> after you grant read permission in the StrideAI iPhone companion, the companion reads sleep analysis, resting heart rate and heart-rate variability (SDNN). It combines those samples on your phone and sends daily summary values, sample counts, dates, time zone and source names to StrideAI. StrideAI does not request permission to write to Apple Health and does not upload raw HealthKit samples.</li>
<li><strong>Generated information:</strong> load calculations, recovery assessments, recommendations, explanations, weather context, outcome comparisons, and diagnostic records.</li>
<li><strong>Technical and contact information:</strong> your browser sends ordinary request information, including IP address and browser details, to the hosting service. If you contact us, we receive your email address and message.</li>
</ul>
<h2>Why information is used</h2>
<p>We use information to provide your training history, assess recovery and recent load, suggest workout adjustments, explain recommendations, show relevant weather, maintain connected services, troubleshoot problems, and respond to requests. Recommendations support your own decisions; they are not medical diagnoses or treatment.</p>
<p>We do not sell personal data or use activity and recovery information for advertising. Connecting Strava and providing optional recovery measurements are voluntary. Without them, some recommendations or features may be unavailable or less complete.</p>
<h2>Services that receive information</h2>
<ul>
<li><strong>Railway:</strong> hosts the application and its persistent database. The current application is deployed in the United States, so information may be processed outside your country.</li>
<li><strong>Strava:</strong> handles your authorization and receives API requests needed to retrieve activities and refresh access tokens. StrideAI does not ask for your Strava password.</li>
<li><strong>Open-Meteo:</strong> receives activity-start coordinates and dates when StrideAI adds historical weather after a Strava sync. For a forecast, it receives the selected coordinates and date; its geocoding service receives place names you search. These requests do not include your Strava tokens or athlete name.</li>
<li><strong>AI explanations:</strong> StrideAI supports optional OpenAI-generated explanations. If enabled, the approved coaching action, recovery factors, safety flags and selected historical outcome context are sent to OpenAI. Without that configuration, explanations are generated within StrideAI. Strava authorization tokens are not part of the explanation prompt.</li>
<li><strong>Email services:</strong> process correspondence when you contact the operator.</li>
</ul>
<p>Service providers also handle information under their own policies. Information may additionally be disclosed when legally required or necessary to address misuse or protect the service and its users.</p>
<h2>Storage, access and retention</h2>
<p>Training records and connection details are stored in the application's database. Access to personal API data is restricted by the deployment's access key; website connections use HTTPS. No storage or transmission method can guarantee absolute security.</p>
<p>The current personal deployment has no automatic expiry for stored training records. Records remain until the operator removes them. Retention is reviewed when you request deletion or stop using the service, taking into account maintaining requested training history, resolving support or security issues, and any applicable legal obligations. There is no self-service account deletion screen.</p>
<h2>Your choices and requests</h2>
<p>You can stop uploading or entering information, disconnect Strava in the app, and revoke authorization in Strava's own settings. You can revoke StrideAI's Apple Health permissions in the Health app and delete stored Apple Health summaries through the protected StrideAI API. Disconnecting or revoking authorization stops future access but does not automatically delete previously imported activities or recommendations.</p>
<p>Contact Viet Le to request access, a copy, correction or deletion of your stored information, or to raise a privacy concern. We may ask for enough information to verify the request. Depending on your location and applicable law, you may also have rights to restrict or object to processing, withdraw consent, or complain to a privacy regulator. Withdrawing authorization stops future access but does not itself erase previously stored data.</p>
<h2>Browser storage</h2>
<p>If you save an access key, StrideAI stores it in your browser's local storage and sends it to the app with protected requests. You can remove it by clearing the key in the app or clearing site data in your browser. This deployment does not include advertising trackers or third-party analytics scripts.</p>
<h2>Children and changes</h2>
<p>StrideAI is intended for adult personal and beta use. Please contact us if a child's information has been submitted. We will update this notice and its effective date when data practices change, including before introducing direct Garmin Connect access or materially different uses.</p>
<footer><strong>Privacy contact: Viet Le</strong><br><a href="mailto:viet@stride-ai.app">viet@stride-ai.app</a><br><a href="/app">Return to StrideAI</a></footer>
</main></body></html>"""
