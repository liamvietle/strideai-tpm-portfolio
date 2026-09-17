from __future__ import annotations


FORM_HANDLER = r'''document.addEventListener('submit',async e=>{
  if(e.target.id!=='checkinForm')return;
  e.preventDefault();
  const $=id=>document.getElementById(id);
  const button=$('recommendBtn');
  const activity=$('planned_activity_type').value;
  const isRun=activity==='run';
  const sleepText=$('sleep_hours').value.trim();
  const parseSleep=value=>{
    if(!value)return null;
    const m=value.match(/^(\d{1,2}):(\d{2})$/);
    if(!m)throw new Error('Enter sleep as HH:MM, for example 06:35.');
    const h=Number(m[1]),min=Number(m[2]);
    if(h>24||min>59||(h===24&&min!==0))throw new Error('Sleep must be between 00:00 and 24:00.');
    return Math.round((h+min/60)*10000)/10000;
  };
  const optional=id=>{const v=$(id)?.value?.trim()??'';return v===''?null:Number(v)};
  const accessKey=()=>localStorage.getItem('strideai_app_key')||'';
  const call=async(url,options={})=>{
    const headers=new Headers(options.headers||{});if(accessKey())headers.set('X-StrideAI-Key',accessKey());
    const r=await fetch(url,{...options,headers});let p={};try{p=await r.json()}catch{}
    if(!r.ok)throw new Error(p.detail||`Request failed (${r.status})`);return p;
  };
  const pretty=v=>(v||'').replaceAll('_',' ');
  const formatHours=value=>{
    if(value==null)return '—';const total=Math.round(Number(value)*60);return `${String(Math.floor(total/60)).padStart(2,'0')}:${String(total%60).padStart(2,'0')}`;
  };
  try{
    button.disabled=true;
    $('submitStatus').textContent=isRun?'Refreshing Strava and running StrideAI…':'Saving daily recovery check-in…';
    if(isRun){try{await call('/app/api/strava/sync',{method:'POST'})}catch(err){console.warn('Pre-recommendation Strava refresh skipped:',err.message)}}
    const payload={
      athlete_id:'viet',checkin_date:$('checkin_date').value,planned_activity_type:activity,
      planned_distance_km:activity==='rest'?0:(optional('planned_distance_km')??0),
      planned_intensity:activity==='rest'?null:$('planned_intensity').value,
      planned_activity_note:$('planned_activity_note').value.trim()||null,
      sleep_hours:parseSleep(sleepText),hrv_ms:optional('hrv_ms'),hrv_baseline_low:optional('hrv_baseline_low'),
      hrv_baseline_high:optional('hrv_baseline_high'),resting_hr_bpm:optional('resting_hr_bpm'),
      soreness_0_10:optional('soreness_0_10'),pain_flag:$('pain_flag').checked,
      subjective_fatigue:$('subjective_fatigue').value,recent_load_ratio:optional('recent_load_ratio'),
      days_until_event:optional('days_until_event'),human_decision:isRun?$('human_decision').value:null
    };
    const d=await call('/app/api/daily-checkin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    if(d.mode==='recovery_only_checkin'){
      $('result').classList.remove('show');$('submitStatus').textContent=d.message;
      const toast=$('toast');toast.textContent='Recovery check-in saved';toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),2400);
      return;
    }
    $('action').textContent=pretty(d.recommendation.action);
    $('fatigueBadge').textContent=`${d.accumulated_fatigue.state} fatigue`;$('fatigueBadge').className=`badge ${d.accumulated_fatigue.state}`;
    $('comparison').textContent=`You chose ${pretty(d.human_decision)}. StrideAI chose ${pretty(d.recommendation.action)}.`;
    $('sleepAvg').textContent=formatHours(d.accumulated_fatigue.average_sleep_7d);
    $('hrvStatus').textContent=(d.accumulated_fatigue.hrv_status||'—').replaceAll('_',' ');
    const lr=payload.recent_load_ratio??d.calculated_load_ratio;$('loadRatio').textContent=lr==null?'—':lr;
    $('explanation').textContent=d.explanation;$('factors').innerHTML=d.recommendation.decision_factors.map(f=>`<li>${f.detail}</li>`).join('')||'<li>No fatigue contributors detected.</li>';
    const outcomeContainer=$('currentOutcome');
    outcomeContainer.innerHTML=`<div class="status">Recommendation saved. Record the workout outcome later from History.</div>`;
    $('result').classList.add('show');$('result').scrollIntoView({behavior:'smooth',block:'start'});$('submitStatus').textContent='Decision locked and recommendation saved.';
  }catch(err){$('submitStatus').textContent=err.message;const toast=$('toast');toast.textContent=err.message;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),2400)}
  finally{button.disabled=false}
},true);
'''


HISTORY_FUNCTION = r'''async function loadHistory(){
  const rows=await api(`/app/api/history?athlete_id=${encodeURIComponent(athlete)}&limit=30`);
  const formatHours=value=>{if(value==null)return '—';const total=Math.round(Number(value)*60);return `${String(Math.floor(total/60)).padStart(2,'0')}:${String(total%60).padStart(2,'0')}`};
  if(!rows.length){$('historyList').innerHTML='<div class="empty">No check-ins yet.</div>';return}
  $('historyList').innerHTML=rows.map(r=>{
    const rec=r.recommendation||{};const activity=r.planned_activity_type||'run';const isRun=activity==='run';
    const activityLabel=activity==='rest'?'Rest day':activity.charAt(0).toUpperCase()+activity.slice(1);
    const session=isRun?`${r.planned_distance_km} km · ${r.planned_intensity}`:`${activityLabel}${r.planned_activity_note?' · '+r.planned_activity_note:''}`;
    if(!r.recommendation_id){return `<div class="history-item"><div class="history-top"><div><div class="history-date">${r.checkin_date}</div><div class="mini">${session} · sleep ${formatHours(r.sleep_hours)}</div></div><div class="history-action">Recovery logged</div></div><div class="mini">${prettyAction(r.subjective_fatigue)} · soreness ${r.soreness_0_10??'—'}/10${r.pain_flag?' · pain flagged':''}</div></div>`}
    const done=r.completed===null||r.completed===undefined?'Outcome pending':(r.completed?'Completed':'Not completed');
    return `<div class="history-item"><div class="history-top"><div><div class="history-date">${r.checkin_date}</div><div class="mini">${session} · sleep ${formatHours(r.sleep_hours)}</div></div><div class="history-action">${prettyAction(rec.action||'pending')}</div></div><div class="mini">You: ${prettyAction(r.human_decision)} · Fatigue: ${prettyAction(rec.fatigue_state||'—')} · ${done}</div>${r.explanation?`<div class="mini" style="margin-top:7px">${r.explanation}</div>`:''}<div class="history-actions"><button type="button" data-toggle="outcome-${r.id}">Record / edit outcome</button></div><div id="outcome-${r.id}">${outcomeForm(r.recommendation_id,false)}</div></div>`
  }).join('');
  document.querySelectorAll('[data-toggle]').forEach(b=>b.addEventListener('click',()=>{const f=document.querySelector(`#${b.dataset.toggle} .outcome-form`);if(f)f.classList.toggle('show')}));
}

'''


EXTRA_SCRIPT = r'''
<script>
(()=>{
  const $=id=>document.getElementById(id);
  const activity=$('planned_activity_type');
  if(!activity)return;
  const distanceField=$('planned_distance_km').closest('.field');
  const intensityField=$('planned_intensity').closest('.field');
  const decisionField=$('human_decision').closest('.field');
  const noteField=$('planned_activity_note').closest('.field');
  const setOptions=(values)=>{$('planned_intensity').innerHTML=values.map(v=>`<option value="${v}">${v.charAt(0).toUpperCase()+v.slice(1)}</option>`).join('')};
  function updateMode(){
    const type=activity.value;const run=type==='run';const rest=type==='rest';const cycling=type==='cycling';
    distanceField.style.display=(run||cycling)?'':'none';intensityField.style.display=rest?'none':'';decisionField.style.display=run?'':'none';noteField.style.display=run?'none':'';
    $('planned_distance_km').required=run;$('human_decision').required=run;
    if(run){$('planned_distance_km').min='0.1';setOptions(['easy','moderate','threshold','interval','race']);$('recommendBtn').textContent='Lock my decision & get StrideAI'}
    else if(rest){$('planned_distance_km').value='0';$('recommendBtn').textContent='Save recovery check-in'}
    else{if(!cycling)$('planned_distance_km').value='0';setOptions(['easy','moderate','hard']);$('recommendBtn').textContent='Save recovery + planned activity'}
  }
  activity.addEventListener('change',updateMode);updateMode();
})();
</script>
'''


def enhance_daily_ui(html: str) -> str:
    html = html.replace(
        '<div class="field"><label>Date</label><input id="checkin_date" type="date" required></div>\n          <div class="field"><label>Planned distance (km)</label><input id="planned_distance_km" type="number" min="0.1" max="100" step="0.1" required></div>',
        '<div class="field"><label>Date</label><input id="checkin_date" type="date" required></div>\n          <div class="field"><label>Planned activity</label><select id="planned_activity_type"><option value="run">Run</option><option value="rest">Rest / recovery day</option><option value="strength">Strength</option><option value="cycling">Cycling</option><option value="tennis">Tennis</option><option value="football">Football</option><option value="other">Other</option></select></div>\n          <div class="field"><label>Planned distance (km)</label><input id="planned_distance_km" type="number" min="0.1" max="300" step="any" required></div>',
        1,
    )
    html = html.replace(
        '<div class="field full"><label>My decision before seeing StrideAI</label><select id="human_decision" required>',
        '<div class="field full"><label>Activity note</label><input id="planned_activity_note" type="text" maxlength="200" placeholder="Optional, e.g. 60 min tennis"></div>\n          <div class="field full"><label>My decision before seeing StrideAI</label><select id="human_decision" required>',
        1,
    )
    html = html.replace(
        '<div class="field"><label>Sleep (hours)</label><input id="sleep_hours" type="number" min="0" max="24" step="0.05" placeholder="e.g. 6.5"></div>',
        '<div class="field"><label>Sleep (HH:MM)</label><input id="sleep_hours" type="text" inputmode="numeric" pattern="[0-9]{1,2}:[0-9]{2}" placeholder="e.g. 06:35"></div>',
        1,
    )
    html = html.replace('placeholder="Auto if Garmin data exists"', 'placeholder="Auto from Strava running history"', 1)
    html = html.replace('Pain before running', 'Pain / injury concern today', 1)
    garmin_card = '<div class="card"><h2>Garmin activity data</h2><p class="hint">Upload Garmin Connect\'s Activities CSV occasionally. StrideAI uses imported running distance to calculate the recent-load ratio automatically.</p><div class="upload"><input id="csvFile" type="file" accept=".csv,text/csv"><button id="uploadBtn" class="secondary" type="button">Import Garmin CSV</button><div id="uploadStatus" class="status"></div></div></div>'
    html = html.replace(garmin_card, '', 1)

    start = html.find("$('checkinForm').addEventListener('submit'")
    end = html.find('async function loadHistory()', start)
    if start >= 0 and end > start:
        html = html[:start] + FORM_HANDLER + html[end:]
    history_start = html.find('async function loadHistory()')
    history_end = html.find("$('uploadBtn').addEventListener", history_start)
    if history_start >= 0 and history_end > history_start:
        metrics_start = html.find('async function loadMetrics()', history_end)
        if metrics_start > history_end:
            html = html[:history_start] + HISTORY_FUNCTION + html[metrics_start:]
    return html.replace('</body>', EXTRA_SCRIPT + '</body>', 1)
