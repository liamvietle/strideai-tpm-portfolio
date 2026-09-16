from __future__ import annotations

ACTIVITIES_CARD = r'''
<div class="card" id="recentActivitiesCard">
  <h2>Recent Activities</h2>
  <p class="hint">Your latest 30 synced Strava activities. Times are shown in your device's time zone.</p>
  <button id="refreshActivities" class="secondary" type="button">Refresh activities</button>
  <div id="activitiesStatus" class="status" role="status" aria-live="polite"></div>
  <div id="recentActivities"></div>
  <p class="hint">Weather estimates from <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a>
  use the start location and hour, not the whole route. Recent weather uses model data. Older weather uses historical reanalysis.
  Activity coordinates and date are sent to Open-Meteo for this lookup. Weather does not change recommendations.</p>
</div>
'''

ACTIVITIES_SCRIPT = r'''
<script>
(()=>{
  const el=id=>document.getElementById(id);
  let loading=false, retryTimer;
  const finite=n=>typeof n==='number'&&Number.isFinite(n);
  const metric=(n,unit,digits=0)=>finite(n)?`${n.toFixed(digits)} ${unit}`:null;
  const duration=n=>{
    if(!finite(n)||n<0)return null;
    n=Math.round(n);
    return n>=3600?`${Math.floor(n/3600)}:${String(Math.floor(n%3600/60)).padStart(2,'0')}:${String(n%60).padStart(2,'0')}`:
      `${Math.floor(n/60)}:${String(n%60).padStart(2,'0')}`;
  };
  function line(parent,text,tag='p'){
    const node=document.createElement(tag);node.textContent=text;parent.appendChild(node);return node;
  }
  function render(items){
    el('recentActivities').replaceChildren();
    for(const a of items){
      const card=document.createElement('article');card.className='card';
      line(card,a.name||a.activity_type||'Strava activity','h3');
      const date=new Date(a.start_time);
      line(card,`${Number.isNaN(date.getTime())?'Date unavailable':date.toLocaleString()} · ${a.activity_type} · Strava`);
      const stats=[metric(a.distance_km,'km',2),duration(a.duration_seconds)];
      if(a.distance_km>0&&a.duration_seconds>0&&/run|walk|hike/i.test(a.activity_type))
        stats.push(`${duration(a.duration_seconds/a.distance_km)}/km`);
      line(card,stats.filter(Boolean).join(' · ')||'Distance and time unavailable');
      const detail=[metric(a.average_hr,'bpm avg'),metric(a.max_hr,'bpm max'),metric(a.elevation_m,'m ascent')];
      if(finite(a.cadence_rpm))detail.push(/run/i.test(a.activity_type)?
        metric(a.cadence_rpm*2,'steps/min'):metric(a.cadence_rpm,'rpm cadence'));
      if(detail.some(Boolean))line(card,detail.filter(Boolean).join(' · '));
      if(a.weather_status==='available'&&a.weather){
        const w=a.weather;
        line(card,'Weather estimate · '+[metric(w.temperature_c,'°C',1),finite(w.feels_like_c)?'feels '+metric(w.feels_like_c,'°C',1):null,
          metric(w.humidity_pct,'% humidity'),metric(w.wind_kmh,'km/h wind',1),metric(w.precipitation_mm,'mm precipitation',1)]
          .filter(Boolean).join(' · '));
        line(card,`Start-hour estimate · ${w.dataset==='recent_model'?'recent model':'historical reanalysis'} · Open-Meteo`).className='hint';
      }else{
        const labels={pending:'Weather pending. Older activities are enriched over subsequent syncs.',
          unavailable:'Weather unavailable. Will retry on a later sync.',indoor:'Weather not applicable to indoor / virtual activity.',
          missing_location:'Weather unavailable: no usable start location from Strava.',missing_time:'Weather unavailable: no usable start time from Strava.'};
        line(card,labels[a.weather_status]||'Weather unavailable').className='hint';
      }
      if(finite(a.strava_temperature_c))line(card,`Strava recorded temperature: ${a.strava_temperature_c} °C`).className='hint';
      if(/^\d+$/.test(a.source_activity_id)){
        const link=document.createElement('a');link.href='https://www.strava.com/activities/'+a.source_activity_id;
        link.textContent='View on Strava';link.target='_blank';link.rel='noopener noreferrer';card.appendChild(link);
      }
      el('recentActivities').appendChild(card);
    }
  }
  async function load(){
    if(loading)return;
    loading=true;el('refreshActivities').disabled=true;el('activitiesStatus').textContent='Loading activities…';
    try{
      const headers={};const key=localStorage.getItem('strideai_app_key');if(key)headers['X-StrideAI-Key']=key;
      const response=await fetch('/app/api/activities',{headers});
      if(!response.ok)throw new Error(response.status===401?'Save your Private access key, then refresh activities.':'Could not load activities. Please try again.');
      const items=await response.json();render(items);
      el('activitiesStatus').textContent=items.length?`Showing ${items.length} recent activities.`:'No synced Strava activities yet. Connect Strava and sync above.';
    }catch(err){el('recentActivities').replaceChildren();el('activitiesStatus').textContent=err.message;}
    finally{loading=false;el('refreshActivities').disabled=false;}
  }
  el('refreshActivities').addEventListener('click',load);
  document.querySelectorAll('.nav button').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.tab==='data')load();}));
  window.addEventListener('strideai:strava-synced',()=>{
    load();clearTimeout(retryTimer);retryTimer=setTimeout(load,25000);
  });
  load();
})();
</script>
'''
