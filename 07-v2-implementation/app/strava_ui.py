from __future__ import annotations

from app.daily_ui_v2 import enhance_daily_ui


STRAVA_CARD = r'''
    <div class="card" id="stravaCard">
      <h2>Strava activity sync</h2>
      <p class="hint">StrideAI refreshes Strava automatically when you open the app and before a running recommendation. All activity types are stored; the current load ratio still uses running distance only.</p>
      <div id="stravaStatus" class="status">Checking Strava connection…</div>
      <div class="history-actions">
        <button id="connectStravaBtn" class="secondary" type="button">Connect Strava</button>
        <button id="syncStravaBtn" class="secondary" type="button" disabled>Sync now</button>
      </div>
      <div id="stravaSyncStatus" class="status"></div>
    </div>
'''


STRAVA_SCRIPT = r'''
<script>
(()=>{
  const byId=id=>document.getElementById(id);
  const storedKey=()=>localStorage.getItem('strideai_app_key')||'';
  let lastAutoSync=0;
  let syncing=false;
  async function stravaApi(url, options={}){
    const headers=new Headers(options.headers||{});
    if(storedKey())headers.set('X-StrideAI-Key',storedKey());
    const response=await fetch(url,{...options,headers});
    let payload={};
    try{payload=await response.json()}catch{}
    if(!response.ok)throw new Error(payload.detail||`Request failed (${response.status})`);
    return payload;
  }
  function fmtWhen(value){
    if(!value)return 'Never synced';
    const d=new Date(value);
    return Number.isNaN(d.getTime())?value:d.toLocaleString();
  }
  async function syncNow({silent=false}={}){
    if(syncing)return null;
    syncing=true;
    const button=byId('syncStravaBtn');
    const status=byId('stravaSyncStatus');
    if(button)button.disabled=true;
    if(status&&!silent)status.textContent='Syncing Strava…';
    try{
      const data=await stravaApi('/app/api/strava/sync',{method:'POST'});
      lastAutoSync=Date.now();
      if(status)status.textContent=`Synced ${data.activities??data.fetched} recent activities (${data.running_activities} runs): ${data.inserted} new, ${data.updated} updated.`;
      return data;
    }catch(err){
      if(status&&!silent)status.textContent=err.message;
      throw err;
    }finally{
      syncing=false;
      if(button)button.disabled=false;
    }
  }
  async function loadStravaStatus({auto=true}={}){
    const status=byId('stravaStatus');
    const connect=byId('connectStravaBtn');
    const sync=byId('syncStravaBtn');
    if(!status||!connect||!sync)return;
    try{
      const data=await stravaApi('/app/api/strava/status');
      if(!data.configured){
        status.textContent='Server credentials are not configured yet.';
        connect.disabled=true;sync.disabled=true;return;
      }
      connect.disabled=false;
      if(data.connected){
        status.textContent=`Connected${data.athlete_name?' as '+data.athlete_name:''}. Automatic sync on. Last sync: ${fmtWhen(data.last_sync_at)}.`;
        connect.textContent='Reconnect Strava';
        sync.disabled=false;
        if(auto&&Date.now()-lastAutoSync>5*60*1000){
          try{await syncNow({silent:true})}catch{}
        }
      }else{
        status.textContent='Not connected yet.';
        connect.textContent='Connect Strava';
        sync.disabled=true;
      }
    }catch(err){
      status.textContent=err.message.includes('access key')?'Save your Private access key below first.':err.message;
      sync.disabled=true;
    }
  }
  byId('connectStravaBtn')?.addEventListener('click',async()=>{
    const status=byId('stravaSyncStatus');
    try{
      status.textContent='Opening Strava authorization…';
      const data=await stravaApi('/app/api/strava/auth-url');
      window.location.assign(data.url);
    }catch(err){status.textContent=err.message}
  });
  byId('syncStravaBtn')?.addEventListener('click',async()=>{
    try{await syncNow()}catch{}
  });
  document.querySelectorAll('.nav button').forEach(button=>{
    button.addEventListener('click',()=>{
      if(button.dataset.tab==='data')loadStravaStatus({auto:true});
      if(button.dataset.tab==='today'&&Date.now()-lastAutoSync>5*60*1000)loadStravaStatus({auto:true});
    });
  });
  document.addEventListener('submit',async event=>{
    if(event.target.id==='checkinForm'&&Date.now()-lastAutoSync>5*60*1000){
      try{await loadStravaStatus({auto:true})}catch{}
    }
  },true);
  const params=new URLSearchParams(window.location.search);
  if(params.get('strava')==='connected'){
    const dataButton=document.querySelector('.nav button[data-tab="data"]');
    if(dataButton)dataButton.click();
    const status=byId('stravaSyncStatus');if(status)status.textContent='Strava connected. Initial activity sync is running automatically.';
    history.replaceState({},'',window.location.pathname);
  }
  loadStravaStatus({auto:true});
})();
</script>
'''


def enhance_personal_app(html: str) -> str:
    html = enhance_daily_ui(html).replace('/app/api/daily-checkin', '/app/api/recommendations')
    marker = '<section id="data" class="panel">'
    enhanced = html.replace(marker, marker + STRAVA_CARD, 1)
    if enhanced == html:
        return html
    return enhanced.replace('</body>', STRAVA_SCRIPT + '</body>', 1)
