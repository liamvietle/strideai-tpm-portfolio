PERSONAL_APP_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#111827">
<title>StrideAI</title>
<style>
:root{--bg:#f5f7fb;--card:#fff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--accent:#2563eb;--accent2:#dbeafe;--good:#047857;--warn:#b45309;--bad:#b91c1c;--shadow:0 8px 28px rgba(17,24,39,.08)}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text)}
button,input,select,textarea{font:inherit}.shell{max-width:760px;margin:0 auto;padding:18px 14px 88px}.top{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}.brand{font-size:24px;font-weight:800;letter-spacing:-.04em}.sub{font-size:13px;color:var(--muted)}
.nav{position:sticky;top:0;z-index:20;background:rgba(245,247,251,.94);backdrop-filter:blur(8px);display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:8px 0 12px}.nav button{border:1px solid var(--line);background:#fff;border-radius:12px;padding:11px 8px;font-weight:700;color:var(--muted)}.nav button.active{background:var(--text);border-color:var(--text);color:#fff}
.panel{display:none}.panel.active{display:block}.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px;margin-bottom:12px;box-shadow:var(--shadow)}h2{font-size:17px;margin:0 0 4px}h3{font-size:15px;margin:0 0 10px}.hint{font-size:13px;color:var(--muted);line-height:1.45;margin:0 0 14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.full{grid-column:1/-1}.field label{display:block;font-size:12px;font-weight:700;color:#4b5563;margin-bottom:6px}.field input,.field select,.field textarea{width:100%;min-height:44px;border:1px solid #d1d5db;border-radius:11px;background:#fff;padding:10px 11px;color:var(--text)}.field textarea{min-height:76px;resize:vertical}.checks{display:flex;gap:16px;align-items:center;min-height:44px}.checks label{font-size:14px;font-weight:600;color:var(--text);display:flex;align-items:center;gap:7px}.checks input{width:18px;height:18px}
.primary,.secondary,.danger{border:0;border-radius:12px;min-height:46px;padding:11px 16px;font-weight:800;cursor:pointer}.primary{background:var(--accent);color:#fff;width:100%}.secondary{background:#eef2ff;color:#3730a3}.danger{background:#fee2e2;color:#991b1b}.primary:disabled{opacity:.55;cursor:not-allowed}.status{font-size:13px;margin-top:9px;color:var(--muted)}
.result{display:none}.result.show{display:block}.hero{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.action{font-size:28px;font-weight:900;letter-spacing:-.04em;text-transform:capitalize}.badge{display:inline-flex;align-items:center;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:800;background:#f3f4f6}.badge.low{background:#dcfce7;color:#166534}.badge.elevated{background:#fef3c7;color:#92400e}.badge.high,.badge.critical{background:#fee2e2;color:#991b1b}.metricrow{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}.metric{background:#f9fafb;border-radius:12px;padding:10px}.metric b{display:block;font-size:17px}.metric span{font-size:11px;color:var(--muted)}.explain{line-height:1.5;font-size:14px;margin-top:14px}.factors{margin:10px 0 0;padding-left:20px;color:#374151;font-size:13px;line-height:1.5}
.history-item{padding:14px 0;border-bottom:1px solid var(--line)}.history-item:last-child{border-bottom:0}.history-top{display:flex;justify-content:space-between;gap:10px}.history-date{font-weight:800}.history-action{font-size:13px;font-weight:800}.mini{font-size:12px;color:var(--muted);margin-top:4px}.history-actions{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}.history-actions button{min-height:38px;padding:7px 10px;border-radius:10px;border:1px solid var(--line);background:#fff;font-weight:700}.outcome-form{display:none;margin-top:12px;padding:12px;background:#f9fafb;border-radius:12px}.outcome-form.show{display:block}
.upload{border:1px dashed #9ca3af;border-radius:14px;padding:16px;text-align:center}.upload input{width:100%;margin:10px 0}.keyrow{display:flex;gap:8px}.keyrow input{flex:1;min-height:44px;border:1px solid #d1d5db;border-radius:11px;padding:10px}.empty{padding:22px;text-align:center;color:var(--muted);font-size:14px}.toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:#111827;color:#fff;border-radius:12px;padding:10px 14px;font-size:13px;display:none;z-index:100;max-width:90%}.toast.show{display:block}.compare{font-size:13px;margin-top:8px;padding:9px 10px;border-radius:10px;background:#eff6ff;color:#1e3a8a}
@media(max-width:560px){.shell{padding-left:10px;padding-right:10px}.grid{grid-template-columns:1fr}.full{grid-column:auto}.metricrow{grid-template-columns:1fr 1fr}.card{border-radius:15px;padding:14px}.action{font-size:24px}}
</style>
</head>
<body>
<div class="shell">
  <div class="top"><div><div class="brand">StrideAI</div><div class="sub">Personal training decision assistant</div></div><span class="badge">v2.1</span></div>
  <div class="nav" role="tablist">
    <button class="active" data-tab="today">Today</button><button data-tab="history">History</button><button data-tab="data">Data</button>
  </div>

  <section id="today" class="panel active">
    <form id="checkinForm">
      <div class="card">
        <h2>Today's session</h2><p class="hint">Record what you planned and what you would choose yourself before StrideAI shows its recommendation.</p>
        <div class="grid">
          <div class="field"><label>Date</label><input id="checkin_date" type="date" required></div>
          <div class="field"><label>Planned distance (km)</label><input id="planned_distance_km" type="number" min="0.1" max="100" step="0.1" required></div>
          <div class="field"><label>Planned intensity</label><select id="planned_intensity"><option>easy</option><option>moderate</option><option>threshold</option><option>interval</option><option>race</option></select></div>
          <input id="days_until_event" type="hidden">
          <div class="field full"><label>My decision before seeing StrideAI</label><select id="human_decision" required><option value="maintain">Maintain</option><option value="reduce_intensity">Reduce intensity</option><option value="reduce_volume">Reduce volume</option><option value="recovery_only">Recovery only</option></select></div>
        </div>
      </div>
      <div class="card">
        <h2>Morning recovery</h2><p class="hint">Use the numbers shown in Garmin that morning. Missing optional fields are allowed.</p>
        <div class="grid">
          <div class="field"><label>Sleep (hours)</label><input id="sleep_hours" type="number" min="0" max="24" step="0.05" placeholder="e.g. 6.5"></div>
          <div class="field"><label>HRV (ms)</label><input id="hrv_ms" type="number" min="0" step="1"></div>
          <div class="field"><label>HRV baseline low</label><input id="hrv_baseline_low" type="number" min="0" step="1"></div>
          <div class="field"><label>HRV baseline high</label><input id="hrv_baseline_high" type="number" min="0" step="1"></div>
          <div class="field"><label>Resting HR</label><input id="resting_hr_bpm" type="number" min="20" max="220" step="1"></div>
          <input id="soreness_0_10" type="hidden">
          <div class="field"><label>How do you feel?</label><select id="subjective_fatigue"><option value="fresh">Fresh</option><option value="normal" selected>Normal</option><option value="slightly_tired">Slightly tired</option><option value="tired">Tired</option><option value="very_tired">Very tired</option><option value="sore">Sore muscles</option><option value="very_sore">Very sore / movement affected</option></select></div>
          <div class="field"><label>Load ratio</label><input id="recent_load_ratio" type="number" min="0" step="0.01" placeholder="Auto if Garmin data exists"></div>
          <div class="field full"><div class="checks"><label><input id="pain_flag" type="checkbox"> Pain before running</label></div></div>
        </div>
        <button id="recommendBtn" class="primary" type="submit">Lock my decision & get StrideAI</button>
        <div id="submitStatus" class="status"></div>
      </div>
    </form>

    <div id="result" class="result">
      <div class="card">
        <div class="hero"><div><div class="sub">StrideAI recommendation</div><div id="action" class="action"></div></div><span id="fatigueBadge" class="badge"></span></div>
        <div id="comparison" class="compare"></div>
        <div class="metricrow">
          <div class="metric"><b id="sleepAvg">—</b><span>7-day avg sleep</span></div>
          <div class="metric"><b id="hrvStatus">—</b><span>HRV status</span></div>
          <div class="metric"><b id="loadRatio">—</b><span>Recent load</span></div>
        </div>
        <div id="explanation" class="explain"></div>
        <ul id="factors" class="factors"></ul>
      </div>
      <div class="card">
        <h3>After the run</h3><p class="hint">You can record the outcome now or come back later from History.</p>
        <div id="currentOutcome"></div>
      </div>
    </div>
  </section>

  <section id="history" class="panel">
    <div class="card"><h2>Training decisions</h2><p class="hint">Morning decision → StrideAI → actual outcome. This is the evidence set for future improvements.</p><div id="historyList"><div class="empty">No check-ins yet.</div></div></div>
  </section>

  <section id="data" class="panel">
    <div class="card"><h2>Garmin activity data</h2><p class="hint">Upload Garmin Connect's Activities CSV occasionally. StrideAI uses imported running distance to calculate the recent-load ratio automatically.</p><div class="upload"><input id="csvFile" type="file" accept=".csv,text/csv"><button id="uploadBtn" class="secondary" type="button">Import Garmin CSV</button><div id="uploadStatus" class="status"></div></div></div>
    <div class="card"><h2>Private access key</h2><p class="hint">If your deployed app has STRIDEAI_APP_KEY configured, enter it here. It stays only in this browser.</p><div class="keyrow"><input id="appKey" type="password" placeholder="Access key"><button id="saveKey" class="secondary" type="button">Save</button></div></div>
    <div class="card"><h2>Deployment metrics</h2><div id="metrics" class="empty">Open this tab to load metrics.</div></div>
  </section>
</div>
<footer style="text-align:center;padding:16px 24px 28px"><a href="/privacy" style="color:inherit">Privacy policy</a></footer>
<div id="toast" class="toast" role="status"></div>
<script>
(()=>{
const athlete='viet';
const $=id=>document.getElementById(id);
const optionalNumber=id=>{const v=$(id).value.trim();return v===''?null:Number(v)};
const key=()=>localStorage.getItem('strideai_app_key')||'';
async function api(url,options={}){const headers=new Headers(options.headers||{});if(key())headers.set('X-StrideAI-Key',key());const r=await fetch(url,{...options,headers});if(!r.ok){let d='';try{d=(await r.json()).detail||''}catch{}throw new Error(d||`Request failed (${r.status})`)}return r.status===204?null:r.json()}
function toast(msg){$('toast').textContent=msg;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),2400)}
function prettyAction(v){return (v||'').replaceAll('_',' ')}
function setToday(){const d=new Date();const local=new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,10);$('checkin_date').value=local}
function outcomeForm(recId,compact=false){return `<form class="outcome-form ${compact?'show':''}" data-rec="${recId}"><div class="grid"><div class="field"><label>Completed?</label><select name="completed"><option value="true">Yes</option><option value="false">No</option></select></div><div class="field"><label>RPE 0–10</label><input name="rpe" type="number" min="0" max="10" step="1"></div><div class="field"><label>Followed StrideAI?</label><select name="followed"><option value="">Not recorded</option><option value="true">Yes</option><option value="false">No</option></select></div><div class="field"><label>If overridden</label><select name="override"><option value="">None</option><option value="maintain">Maintain</option><option value="reduce_intensity">Reduce intensity</option><option value="reduce_volume">Reduce volume</option><option value="recovery_only">Recovery only</option></select></div><div class="field full"><div class="checks"><label><input name="pain" type="checkbox"> Pain during/after</label></div></div><div class="field full"><label>Notes</label><textarea name="notes" placeholder="How did the session feel?"></textarea></div></div><button class="primary" type="submit">Save outcome</button></form>`}
async function saveOutcome(form){const rec=form.dataset.rec;const followed=form.elements.followed.value;const payload={completed:form.elements.completed.value==='true',perceived_effort_0_10:form.elements.rpe.value===''?null:Number(form.elements.rpe.value),pain_after:form.elements.pain.checked,followed_recommendation:followed===''?null:followed==='true',override_action:form.elements.override.value||null,notes:form.elements.notes.value||null};await api(`/v3/recommendations/${rec}/outcome`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});toast('Outcome saved');await loadHistory()}
document.addEventListener('submit',e=>{if(e.target.classList.contains('outcome-form')){e.preventDefault();saveOutcome(e.target).catch(err=>toast(err.message))}})

document.querySelectorAll('.nav button').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nav button').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');$(b.dataset.tab).classList.add('active');if(b.dataset.tab==='history')loadHistory().catch(err=>toast(err.message));if(b.dataset.tab==='data')loadMetrics().catch(err=>toast(err.message))}))

$('checkinForm').addEventListener('submit',async e=>{e.preventDefault();$('recommendBtn').disabled=true;$('submitStatus').textContent='Saving your decision and running StrideAI…';const payload={athlete_id:athlete,checkin_date:$('checkin_date').value,planned_distance_km:Number($('planned_distance_km').value),planned_intensity:$('planned_intensity').value,sleep_hours:optionalNumber('sleep_hours'),hrv_ms:optionalNumber('hrv_ms'),hrv_baseline_low:optionalNumber('hrv_baseline_low'),hrv_baseline_high:optionalNumber('hrv_baseline_high'),resting_hr_bpm:optionalNumber('resting_hr_bpm'),soreness_0_10:optionalNumber('soreness_0_10'),pain_flag:$('pain_flag').checked,subjective_fatigue:$('subjective_fatigue').value,recent_load_ratio:optionalNumber('recent_load_ratio'),days_until_event:optionalNumber('days_until_event'),human_decision:$('human_decision').value};
try{const d=await api('/app/api/recommendations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});$('action').textContent=prettyAction(d.recommendation.action);$('fatigueBadge').textContent=`${d.accumulated_fatigue.state} fatigue`;$('fatigueBadge').className=`badge ${d.accumulated_fatigue.state}`;$('comparison').textContent=`You chose ${prettyAction(d.human_decision)}. StrideAI chose ${prettyAction(d.recommendation.action)}.`;$('sleepAvg').textContent=d.accumulated_fatigue.average_sleep_7d==null?'—':`${d.accumulated_fatigue.average_sleep_7d}h`;$('hrvStatus').textContent=(d.accumulated_fatigue.hrv_status||'—').replaceAll('_',' ');const lr=payload.recent_load_ratio??d.calculated_load_ratio;$('loadRatio').textContent=lr==null?'—':lr;$('explanation').textContent=d.explanation;$('factors').innerHTML=d.recommendation.decision_factors.map(f=>`<li>${f.detail}</li>`).join('')||'<li>No fatigue contributors detected.</li>';$('currentOutcome').innerHTML=outcomeForm(d.recommendation_id,true);$('result').classList.add('show');$('result').scrollIntoView({behavior:'smooth',block:'start'});$('submitStatus').textContent='Decision locked and recommendation saved.';}
catch(err){$('submitStatus').textContent=err.message;toast(err.message)}finally{$('recommendBtn').disabled=false}})

async function loadHistory(){const rows=await api(`/app/api/history?athlete_id=${encodeURIComponent(athlete)}&limit=30`);if(!rows.length){$('historyList').innerHTML='<div class="empty">No check-ins yet.</div>';return}$('historyList').innerHTML=rows.map(r=>{const rec=r.recommendation||{};const done=r.completed===null||r.completed===undefined?'Outcome pending':(r.completed?'Completed':'Not completed');return `<div class="history-item"><div class="history-top"><div><div class="history-date">${r.checkin_date}</div><div class="mini">${r.planned_distance_km} km · ${r.planned_intensity} · sleep ${r.sleep_hours??'—'}h</div></div><div class="history-action">${prettyAction(rec.action||'pending')}</div></div><div class="mini">You: ${prettyAction(r.human_decision)} · Fatigue: ${prettyAction(rec.fatigue_state||'—')} · ${done}</div>${r.explanation?`<div class="mini" style="margin-top:7px">${r.explanation}</div>`:''}<div class="history-actions">${r.recommendation_id?`<button type="button" data-toggle="outcome-${r.id}">Record / edit outcome</button>`:''}</div>${r.recommendation_id?`<div id="outcome-${r.id}">${outcomeForm(r.recommendation_id,false)}</div>`:''}</div>`}).join('');document.querySelectorAll('[data-toggle]').forEach(b=>b.addEventListener('click',()=>{const f=document.querySelector(`#${b.dataset.toggle} .outcome-form`);if(f)f.classList.toggle('show')}))}

$('uploadBtn').addEventListener('click',async()=>{const f=$('csvFile').files[0];if(!f){toast('Choose a Garmin CSV first');return}const fd=new FormData();fd.append('file',f);$('uploadStatus').textContent='Importing…';try{const d=await api(`/v3/activities/import/garmin-csv?athlete_id=${encodeURIComponent(athlete)}`,{method:'POST',body:fd});$('uploadStatus').textContent=`Imported ${d.parsed}: ${d.inserted} new, ${d.updated} updated.`;toast('Garmin data imported')}catch(err){$('uploadStatus').textContent=err.message}})
async function loadMetrics(){const d=await api(`/v4/metrics?athlete_id=${encodeURIComponent(athlete)}`);$('metrics').className='';$('metrics').innerHTML=`<div class="metricrow"><div class="metric"><b>${d.total_recommendations}</b><span>Recommendations</span></div><div class="metric"><b>${d.outcomes_recorded}</b><span>Outcomes</span></div><div class="metric"><b>${d.acceptance_rate==null?'—':Math.round(d.acceptance_rate*100)+'%'}</b><span>Followed</span></div><div class="metric"><b>${d.override_rate==null?'—':Math.round(d.override_rate*100)+'%'}</b><span>Overridden</span></div><div class="metric"><b>${d.average_perceived_effort??'—'}</b><span>Avg RPE</span></div><div class="metric"><b>${d.pain_after_rate==null?'—':Math.round(d.pain_after_rate*100)+'%'}</b><span>Pain after</span></div></div>`}
$('saveKey').addEventListener('click',()=>{localStorage.setItem('strideai_app_key',$('appKey').value.trim());toast('Access key saved')});$('appKey').value=key();setToday();
})();
</script>
</body>
</html>'''
