PLAN_PANEL = r'''
<section id="plan" class="panel">
 <div class="card"><h2>Race goal</h2><p class="hint">Your target stays yours. Daily recommendations never change it automatically.</p>
 <div id="goalSummary" class="compare">Add a race below.</div>
 <form id="goalForm"><div class="grid">
 <div class="field"><label for="raceName">Race name</label><input id="raceName" maxlength="120" required></div>
 <div class="field"><label for="raceDate">Race date</label><input id="raceDate" type="date" required></div>
 <div class="field"><label for="raceDistance">Distance (km)</label><input id="raceDistance" type="number" min="0.1" max="300" step="any" value="42.195" required></div>
 <div class="field"><label for="raceTime">Finish-time goal (HH:MM)</label><input id="raceTime" placeholder="03:50" pattern="[0-9]{1,3}:[0-5][0-9]" required></div>
 <div class="field"><label for="planTimezone">Training time zone</label><input id="planTimezone" value="Asia/Ho_Chi_Minh" required></div>
 <div class="checks"><label><input id="newRace" type="checkbox"> Start a new race and plan</label></div>
 </div><button class="primary">Save race goal</button></form><p id="goalStatus" class="status"></p></div>
 <div class="card"><h2>Plan and progress</h2><p id="planReview" class="compare"></p>
 <p class="hint">Recorded distance comes from Strava runs. An absent run is unknown, not a confirmed missed session. Reductions are recommendations, not proof that you ran less. Review the gap after confirming sync and outcomes; do not cram missed distance.</p>
 <p id="planSource" class="mini"></p><div id="weekTable" style="overflow-x:auto"></div>
 <h3 style="margin-top:18px">Daily detail</h3><div class="field"><label for="planWeek">Week beginning</label><select id="planWeek"></select></div><div id="planDays"></div>
 </div>
 <div class="card"><details><summary>Edit / import plan snapshot</summary>
 <p class="hint">One line per date: YYYY-MM-DD | running km | run, rest or other | session description. Non-running days use 0 km. Saving creates a new revision; older snapshots stay in storage. This is a snapshot, not a live spreadsheet link.</p>
 <div class="field"><label for="planSourceInput">Source / revision note</label><input id="planSourceInput" maxlength="300" value="Manual plan"></div>
 <div class="field"><label for="planText">Daily sessions</label><textarea id="planText" rows="10" placeholder="2026-10-01 | 8 | run | Easy"></textarea></div>
 <button class="secondary" id="editPlan">Load current snapshot for editing</button>
 <button class="secondary" id="savePlan">Save new snapshot</button><p id="planImportStatus" class="status"></p>
 </details></div>
 <div class="card"><h2>What the evidence supports</h2><p class="hint">Heat can impair endurance performance. Recovery trends and how you feel can help guide training. StrideAI's combined score, fixed distance cuts and forecast triggers have not been clinically or prospectively validated. A target pace is a goal, not a prediction.</p>
 <p class="hint"><a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC9811094/" target="_blank" rel="noopener">IOC heat consensus</a> · <a href="https://pubmed.ncbi.nlm.nih.gov/26909534/" target="_blank" rel="noopener">HRV-guided training study</a> · <a href="https://pubmed.ncbi.nlm.nih.gov/26423706/" target="_blank" rel="noopener">Subjective recovery review</a> · <a href="https://pubmed.ncbi.nlm.nih.gov/32502973/" target="_blank" rel="noopener">Workload ratio limitations</a></p></div>
</section>
'''

WEATHER_CARD = r'''
<div class="card"><h2>Weather for this run</h2><p class="hint">Select where and when you will run. City coordinates and start date go to Open-Meteo. Start time uses this device's time zone. Yesterday's weather is not tomorrow's forecast.</p>
<div class="checks"><label><input id="weatherIndoor" type="checkbox"> Indoor run</label></div>
<div class="grid"><div class="field"><label for="weatherCity">City</label><input id="weatherCity" placeholder="Search for your running location"></div><button id="searchPlaces" type="button" class="secondary">Find location</button>
<div class="field"><label for="weatherPlace">Selected location</label><select id="weatherPlace"><option value="">Choose a location</option></select></div>
<div class="field"><label for="weatherStart">Planned start (device local time)</label><input id="weatherStart" type="datetime-local"></div></div>
<button id="previewWeather" type="button" class="secondary">Preview forecast guidance</button><p id="weatherPreview" class="status">No forecast selected.</p>
</div>
'''

PLAN_SCRIPT = r'''
<script>
(()=>{
 const $=id=>document.getElementById(id);let progress=null,places=[];
 const call=async(url,options={})=>{const headers=new Headers(options.headers||{});headers.set('X-StrideAI-Key',localStorage.getItem('strideai_app_key')||'');const r=await fetch(url,{...options,headers});let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Check the form values and try again.');return d};
 const send=(url,method,data)=>call(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 const text=(parent,tag,value)=>{const e=document.createElement(tag);e.textContent=value;parent.append(e);return e};
 const km=v=>v==null?'Not recorded':`${v} km`;
 function showDays(){const host=$('planDays');host.replaceChildren();if(!progress)return;const start=$('planWeek').value;const end=new Date(start+'T12:00:00Z');end.setUTCDate(end.getUTCDate()+6);const finish=end.toISOString().slice(0,10);for(const d of progress.days.filter(d=>d.date>=start&&d.date<=finish)){const card=text(host,'div','');card.className='history-item';text(card,'strong',`${d.date} · ${d.activity} · ${km(d.distance_km)}`);text(card,'p',d.note||'');text(card,'p',`Recorded: ${km(d.recorded_km)} · Recovery recommendation: ${d.action?d.action.replaceAll('_',' '):'Not recorded'}`);if(d.weather_guidance)text(card,'p','Forecast guidance: '+d.weather_guidance);if(d.recommended_km!=null)text(card,'p',`Recommended ${km(d.recommended_km)} from that day's ${km(d.checkin_planned_km)} check-in. The original plan above is unchanged.`);}}
 function fillGoalDays(){if(!progress?.goal)return;const days=Math.round((Date.parse(progress.goal.race_date+'T12:00:00Z')-Date.parse($('checkin_date').value+'T12:00:00Z'))/86400000);$('days_until_event').value=days>=0&&days<=365?days:'';}
 async function loadPlan(){progress=await call('/app/api/plan');const g=progress.goal;if(g){$('raceName').value=g.name;$('raceDate').value=g.race_date;$('raceDistance').value=g.distance_km;$('raceTime').value=String(Math.floor(g.goal_minutes/60)).padStart(2,'0')+':'+String(Math.round(g.goal_minutes%60)).padStart(2,'0');$('planTimezone').value=g.timezone;const p=progress.goal_pace_seconds_km;$('goalSummary').textContent=`${g.name} · ${g.race_date} · ${$('raceTime').value} goal · ${Math.floor(p/60)}:${String(p%60).padStart(2,'0')}/km target pace · ${progress.days_to_race} days to race`;fillGoalDays();}
 $('planReview').textContent=`${progress.review} ${progress.decisions_14d==null?'':`${progress.reductions_14d} reduced recommendations from ${progress.decisions_14d} running decisions in the last 14 days. The review trigger is an app heuristic, not a race prediction.`}`;
 $('planSource').textContent=progress.revision?`Snapshot ${progress.revision} · ${progress.source} · imported ${progress.imported_at} UTC`:'No plan snapshot yet.';
 const host=$('weekTable');host.replaceChildren();const table=text(host,'table','');table.style.cssText='width:100%;border-collapse:collapse;font-size:13px;text-align:left';const head=text(table,'tr','');for(const h of ['Week','Plan','Plan to date','Recorded','Longest planned','Reductions'])text(head,'th',h).style.padding='8px';for(const w of progress.weeks){const row=text(table,'tr','');for(const v of [w.start,km(w.planned_km),km(w.planned_to_date_km),km(w.recorded_km),km(w.longest_planned_km),String(w.reductions)])text(row,'td',v).style.cssText='padding:8px;border-top:1px solid #e5e7eb';}
 $('planWeek').replaceChildren();for(const w of progress.weeks){const opt=text($('planWeek'),'option',w.start);opt.value=w.start;}
 const current=progress.weeks.filter(w=>w.start<=progress.as_of).at(-1);if(current)$('planWeek').value=current.start;if(progress.weeks.length)showDays();else $('planDays').textContent='Import a plan to see daily detail.';
 }
 $('goalForm').addEventListener('submit',async e=>{e.preventDefault();try{const parts=$('raceTime').value.split(':').map(Number);await send('/app/api/goal','PUT',{name:$('raceName').value.trim(),race_date:$('raceDate').value,distance_km:Number($('raceDistance').value),goal_minutes:parts[0]*60+parts[1],timezone:$('planTimezone').value.trim(),new_race:$('newRace').checked});$('newRace').checked=false;$('goalStatus').textContent='Race goal saved.';await loadPlan()}catch(err){$('goalStatus').textContent=err.message}});
 $('editPlan').onclick=()=>{if(!progress?.days.length)return;$('planText').value=progress.days.map(d=>`${d.date} | ${d.distance_km} | ${d.activity} | ${d.note}`).join('\n');$('planSourceInput').value=progress.source||'Edited plan';};
 $('savePlan').onclick=async()=>{try{if(!progress?.goal)throw new Error('Save a race goal first.');const days=$('planText').value.trim().split('\n').filter(s=>s.trim()).map(line=>{const [date,dist,activity,...note]=line.split('|').map(s=>s.trim());if(!dist)throw new Error('Every line needs a distance, including 0 for non-running days.');return {date,distance_km:Number(dist),activity,note:note.join(' | ')}});await send('/app/api/plan','POST',{race_id:progress.goal.id,source:$('planSourceInput').value,days});$('planImportStatus').textContent=`Saved ${days.length} sessions as a new snapshot.`;await loadPlan()}catch(err){$('planImportStatus').textContent=err.message}};
 $('planWeek').onchange=showDays;$('checkin_date').addEventListener('change',fillGoalDays);
 $('searchPlaces').onclick=async()=>{try{places=await call('/app/api/weather/places?name='+encodeURIComponent($('weatherCity').value.trim()));$('weatherPlace').replaceChildren();const empty=text($('weatherPlace'),'option','Choose a location');empty.value='';places.forEach((p,i)=>{const opt=text($('weatherPlace'),'option',p.name);opt.value=String(i)});$('weatherPreview').textContent=places.length?'Select the matching location below.':'No matching locations.'}catch(err){$('weatherPreview').textContent=err.message}};
 const localStart=value=>{const d=new Date(value),offset=-d.getTimezoneOffset(),sign=offset>=0?'+':'-';return value+':00'+sign+String(Math.floor(Math.abs(offset)/60)).padStart(2,'0')+':'+String(Math.abs(offset)%60).padStart(2,'0')};
 window.strideRunWeather=()=>{if($('weatherIndoor').checked)return {indoor:true,latitude:0,longitude:0,start:new Date().toISOString()};const val=$('weatherPlace').value;if(val===''&&!$('weatherStart').value)return null;if(val===''||!$('weatherStart').value)throw new Error('Complete both the forecast location and start time, or clear both.');const p=places[Number(val)];return {indoor:false,latitude:p.latitude,longitude:p.longitude,location:p.name,start:localStart($('weatherStart').value)}};
 window.strideWeatherText=w=>{if(!w)return '';const v=w.values;return `${v?`${w.location} · ${new Date(w.start).toLocaleString()} · ${v.temperature_c}°C, feels ${v.feels_like_c}°C · humidity ${v.humidity_pct}% · `:''}${w.guidance} ${w.limitation||''}`};
 $('previewWeather').onclick=async()=>{try{const request=window.strideRunWeather();if(!request)throw new Error('Select the location and start time first.');$('weatherPreview').textContent=window.strideWeatherText(await send('/app/api/weather/forecast','POST',request));}catch(err){$('weatherPreview').textContent=err.message}};
 document.querySelector('[data-tab="plan"]').addEventListener('click',()=>loadPlan().catch(err=>$('planReview').textContent=err.message));
 $('saveKey').addEventListener('click',()=>loadPlan().catch(()=>{}));loadPlan().catch(()=>{});
})();
</script>
'''


def enhance_plan_ui(html):
    html = html.replace('grid-template-columns:repeat(3,1fr);gap:8px;padding:8px', 'grid-template-columns:repeat(4,1fr);gap:8px;padding:8px', 1)
    html = html.replace('<button data-tab="data">Data</button>', '<button data-tab="data">Data</button><button data-tab="plan">Plan</button>', 1)
    html = html.replace('<section id="history"', PLAN_PANEL + '<section id="history"', 1)
    html = html.replace('      <div class="card">\n        <h2>Morning recovery</h2>', WEATHER_CARD + '      <div class="card">\n        <h2>Morning recovery</h2>', 1)
    html = html.replace("athlete_id:'viet',checkin_date:", "run_weather:window.strideRunWeather?.()||null,athlete_id:'viet',checkin_date:", 1)
    html = html.replace("$('explanation').textContent=d.explanation;", "$('explanation').textContent=d.explanation;document.getElementById('runWeatherResult').textContent=window.strideWeatherText(d.run_weather);", 1)
    html = html.replace('<ul id="factors"', '<div id="runWeatherResult" class="compare" role="status"></div><ul id="factors"', 1)
    html = html.replace('StrideAI recommendation</div>', 'Recovery recommendation</div>', 1)
    html = html.replace('Weather does not change recommendations.', 'Past weather does not alter the recovery score. Add the next run forecast in Today for separate session guidance.')
    return html.replace('</body>', PLAN_SCRIPT + '</body>', 1)
