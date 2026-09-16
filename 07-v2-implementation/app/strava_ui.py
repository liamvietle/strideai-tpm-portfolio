from __future__ import annotations


STRAVA_CARD = r'''
    <div class="card" id="stravaCard">
      <h2>Strava activity sync</h2>
      <p class="hint">Connect Strava once, then sync recent runs directly into StrideAI. Morning recovery data still comes from Garmin/manual entry.</p>
      <div id="stravaStatus" class="status">Checking Strava connection…</div>
      <div class="history-actions">
        <button id="connectStravaBtn" class="secondary" type="button">Connect Strava</button>
        <button id="syncStravaBtn" class="secondary" type="button" disabled>Sync Strava</button>
      </div>
      <div id="stravaSyncStatus" class="status"></div>
    </div>
'''


STRAVA_SCRIPT = r'''
<script>
(()=>{
  const byId=id=>document.getElementById(id);
  const storedKey=()=>localStorage.getItem('strideai_app_key')||'';
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
  async function loadStravaStatus(){
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
        status.textContent=`Connected${data.athlete_name?' as '+data.athlete_name:''}. ${fmtWhen(data.last_sync_at)}.`;
        connect.textContent='Reconnect Strava';
        sync.disabled=false;
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
    const button=byId('syncStravaBtn');
    const status=byId('stravaSyncStatus');
    button.disabled=true;status.textContent='Syncing recent runs…';
    try{
      const data=await stravaApi('/app/api/strava/sync',{method:'POST'});
      status.textContent=`Synced ${data.running_activities} recent runs: ${data.inserted} new, ${data.updated} updated.`;
      await loadStravaStatus();
    }catch(err){status.textContent=err.message;button.disabled=false}
  });
  document.querySelectorAll('.nav button').forEach(button=>{
    button.addEventListener('click',()=>{if(button.dataset.tab==='data')loadStravaStatus()});
  });
  const params=new URLSearchParams(window.location.search);
  if(params.get('strava')==='connected'){
    const dataButton=document.querySelector('.nav button[data-tab="data"]');
    if(dataButton)dataButton.click();
    const status=byId('stravaSyncStatus');if(status)status.textContent='Strava connected. Sync your recent runs now.';
    history.replaceState({},'',window.location.pathname);
  }
  loadStravaStatus();
})();
</script>
'''


def enhance_personal_app(html: str) -> str:
    marker = '<section id="data" class="panel">'
    enhanced = html.replace(marker, marker + STRAVA_CARD, 1)
    if enhanced == html:
        return html
    return enhanced.replace('</body>', STRAVA_SCRIPT + '</body>', 1)
