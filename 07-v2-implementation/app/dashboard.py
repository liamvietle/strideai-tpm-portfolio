DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>StrideAI Deployment Dashboard</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 40px auto; padding: 0 20px; background: #f7f7f8; color: #18181b; }
    h1 { margin-bottom: 4px; }
    .muted { color: #71717a; margin-top: 0; }
    .toolbar { display: flex; gap: 8px; margin: 24px 0; }
    input, button { padding: 10px 12px; font-size: 14px; }
    input { flex: 1; }
    button { cursor: pointer; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
    .card { background: white; border: 1px solid #e4e4e7; border-radius: 10px; padding: 16px; }
    .label { color: #71717a; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
    .value { font-size: 28px; font-weight: 650; margin-top: 6px; }
    section { margin-top: 28px; }
    pre { background: #18181b; color: #fafafa; padding: 16px; border-radius: 10px; overflow: auto; }
  </style>
</head>
<body>
  <h1>StrideAI Deployment Dashboard</h1>
  <p class="muted">Operational adoption, safety, guardrail and explanation-quality signals.</p>
  <div class="toolbar">
    <input id="athlete" placeholder="Athlete ID (leave blank for all data)" />
    <button onclick="loadDashboard()">Refresh</button>
  </div>

  <section>
    <h2>Deployment metrics</h2>
    <div id="metrics" class="grid"></div>
  </section>

  <section>
    <h2>Explanation quality</h2>
    <div id="quality" class="grid"></div>
  </section>

  <section>
    <h2>Raw snapshot</h2>
    <pre id="raw">Loading...</pre>
  </section>

<script>
function pct(value) {
  return value === null || value === undefined ? 'n/a' : `${(value * 100).toFixed(1)}%`;
}
function card(label, value) {
  return `<div class="card"><div class="label">${label}</div><div class="value">${value}</div></div>`;
}
async function loadDashboard() {
  const athlete = document.getElementById('athlete').value.trim();
  const suffix = athlete ? `?athlete_id=${encodeURIComponent(athlete)}` : '';
  const [metricsResponse, qualityResponse] = await Promise.all([
    fetch(`/v4/metrics${suffix}`),
    fetch(`/v4/quality/explanations${suffix}`)
  ]);
  const metrics = await metricsResponse.json();
  const quality = await qualityResponse.json();
  document.getElementById('metrics').innerHTML = [
    card('Recommendations', metrics.total_recommendations),
    card('Outcome coverage', pct(metrics.outcome_coverage_rate)),
    card('Acceptance', pct(metrics.acceptance_rate)),
    card('Override', pct(metrics.override_rate)),
    card('Completion', pct(metrics.completion_rate)),
    card('Pain after', pct(metrics.pain_after_rate)),
    card('Human review', pct(metrics.human_review_rate)),
    card('Guardrail pass', pct(metrics.guardrail_pass_rate)),
    card('Fallback', pct(metrics.fallback_rate))
  ].join('');
  document.getElementById('quality').innerHTML = [
    card('Evaluated explanations', quality.evaluated),
    card('Groundedness', pct(quality.groundedness_rate)),
    card('Action consistency', pct(quality.action_consistency_rate)),
    card('Unsupported numbers', quality.unsupported_numeric_claims),
    card('Avg groundedness score', pct(quality.average_groundedness_score))
  ].join('');
  document.getElementById('raw').textContent = JSON.stringify({metrics, quality}, null, 2);
}
loadDashboard();
</script>
</body>
</html>
"""
