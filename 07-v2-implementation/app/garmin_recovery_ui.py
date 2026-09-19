"""A private recovery import and history card in app settings."""
SCRIPT = r'''<script>(()=>{
const host=document.getElementById('journey-you')||document.getElementById('data');
if(!host)return;
const card=document.createElement('div');card.className='card';
card.innerHTML='<h2>Garmin recovery history</h2><p class="hint">Sleep, resting heart rate and HRV from your Garmin export. Original dates are preserved. These records do not create check-ins or add activities.</p><p id="garminRecoverySummary" role="status">Loading recovery history…</p><label for="garminRecoveryFile">Prepared recovery file</label><input id="garminRecoveryFile" type="file" accept=".json,application/json"><button type="button" class="secondary" id="garminRecoveryImport">Import recovery file</button><p id="garminRecoveryResult" role="status"></p><details><summary>Recent imported measurements</summary><div style="overflow-x:auto" id="garminRecoveryRows"></div></details>';
host.append(card);
const el=id=>document.getElementById(id);
async function call(url,options={}){const headers=new Headers(options.headers||{});const key=localStorage.getItem('strideai_app_key');if(key)headers.set('X-StrideAI-Key',key);const r=await fetch(url,{...options,headers});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Import rejected. Check the recovery file.');return d;}
async function load(){const d=await call('/app/api/garmin-recovery/history?limit=30');el('garminRecoverySummary').textContent=d.days?`${d.days} days · ${d.first_date} to ${d.latest_date}. Sleep: ${d.counts.sleep_hours}; resting HR: ${d.counts.resting_hr_bpm}; HRV: ${d.counts.hrv_ms}.`:'No Garmin recovery measurements imported.';const table=document.createElement('table');table.style.cssText='width:100%;text-align:left';const head=table.createTHead().insertRow();for(const label of ['Date','Sleep (h)','Resting HR (bpm)','HRV (ms)']){const th=document.createElement('th');th.textContent=label;head.append(th)}for(const r of d.rows){const row=table.insertRow();for(const v of [r.checkin_date,r.sleep_hours==null?'—':Number(r.sleep_hours).toFixed(2),r.resting_hr_bpm??'—',r.hrv_ms??'—'])row.insertCell().textContent=v;}el('garminRecoveryRows').replaceChildren(table);}
el('garminRecoveryImport').onclick=async()=>{const button=el('garminRecoveryImport');try{const file=el('garminRecoveryFile').files[0];if(!file)throw Error('Choose the prepared recovery JSON file first.');if(file.size>2000000)throw Error('Recovery file is too large.');const payload=JSON.parse(await file.text());button.disabled=true;el('garminRecoveryResult').textContent='Importing…';const d=await call('/app/api/garmin-recovery/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});el('garminRecoveryResult').textContent=`Imported ${d.inserted} new days; ${d.updated} updated; ${d.unchanged} unchanged. Activities and check-ins were not changed.`;await load();}catch(e){el('garminRecoveryResult').textContent=e.message}finally{button.disabled=false}};
load().catch(e=>el('garminRecoverySummary').textContent=e.message);
})();</script>'''


def enhance_garmin_recovery_ui(html):
    return html.replace('</body>', SCRIPT + '</body>', 1)
