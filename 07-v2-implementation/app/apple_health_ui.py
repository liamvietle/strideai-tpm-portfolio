from __future__ import annotations


APPLE_HEALTH_CARD = r'''
    <div class="card" id="appleHealthCard">
      <h2>Apple Health recovery sync</h2>
      <p class="hint">The StrideAI iPhone companion reads Sleep, Resting Heart Rate and HRV SDNN with your permission. It sends daily summaries only, not raw HealthKit samples.</p>
      <div id="appleHealthStatus" class="status">Checking Apple Health data…</div>
      <div class="history-actions">
        <button id="loadAppleHealthBtn" class="secondary" type="button">Load into today's check-in</button>
      </div>
      <div id="appleHealthLoadStatus" class="status"></div>
    </div>
'''


APPLE_HEALTH_SCRIPT = r'''
<script>
(()=>{
  const byId=id=>document.getElementById(id);
  const storedKey=()=>localStorage.getItem('strideai_app_key')||'';
  async function healthApi(url){
    const headers=new Headers();if(storedKey())headers.set('X-StrideAI-Key',storedKey());
    const response=await fetch(url,{headers});let payload={};try{payload=await response.json()}catch{}
    if(!response.ok)throw new Error(payload.detail||`Request failed (${response.status})`);return payload;
  }
  const sleepText=value=>{
    const minutes=Math.round(Number(value)*60);
    return `${String(Math.floor(minutes/60)).padStart(2,'0')}:${String(minutes%60).padStart(2,'0')}`;
  };
  async function loadForDate({overwrite=false}={}){
    const date=byId('checkin_date')?.value;if(!date)return;
    const status=byId('appleHealthLoadStatus');
    try{
      const data=await healthApi(`/app/api/apple-health/daily-state?athlete_id=viet&date=${encodeURIComponent(date)}`);
      if(!data.available){if(status)status.textContent=`No Apple Health recovery summary for ${date}.`;return}
      const state=data.state;const fields={
        sleep_hours:state.sleep_hours==null?null:sleepText(state.sleep_hours),
        hrv_ms:state.hrv_ms,resting_hr_bpm:state.resting_hr_bpm,
        hrv_baseline_low:state.hrv_baseline_low,hrv_baseline_high:state.hrv_baseline_high
      };
      let loaded=0;
      Object.entries(fields).forEach(([id,value])=>{const input=byId(id);if(input&&value!=null&&(overwrite||!input.value)){input.value=value;loaded++}});
      if(status){
        const baseline=state.hrv_baseline_days>=7?` HRV baseline uses ${state.hrv_baseline_days} prior days.`:' HRV baseline needs at least 7 prior days.';
        status.textContent=`Apple Health loaded ${loaded} field${loaded===1?'':'s'} for ${date}.${baseline}`;
      }
    }catch(err){if(status)status.textContent=err.message}
  }
  async function loadStatus(){
    const status=byId('appleHealthStatus');if(!status)return;
    try{
      const data=await healthApi('/app/api/apple-health/status?athlete_id=viet');
      status.textContent=data.connected
        ?`Receiving Apple Health summaries. ${data.days} days saved; latest ${data.latest_date}. Last sync: ${data.last_sync_at}.`
        :'No Apple Health data yet. Open the StrideAI companion on your iPhone to authorize and sync.';
      await loadForDate();
    }catch(err){status.textContent=err.message.includes('access key')?'Save your Private access key below first.':err.message}
  }
  byId('loadAppleHealthBtn')?.addEventListener('click',()=>loadForDate({overwrite:true}));
  byId('checkin_date')?.addEventListener('change',()=>loadForDate());
  document.querySelectorAll('.nav button').forEach(button=>button.addEventListener('click',()=>{
    if(button.dataset.tab==='data'||button.dataset.tab==='today')loadStatus();
  }));
  loadStatus();
})();
</script>
'''


def enhance_apple_health_ui(html: str) -> str:
    marker = '<section id="data" class="panel">'
    enhanced = html.replace(marker, marker + APPLE_HEALTH_CARD, 1)
    if enhanced == html:
        return html
    return enhanced.replace("</body>", APPLE_HEALTH_SCRIPT + "</body>", 1)

