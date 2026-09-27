const {chromium}=require('playwright');
(async()=>{
const base='http://127.0.0.1:8765';for(let i=0;i<60;i++){try{await fetch(base+'/health');break}catch{await new Promise(r=>setTimeout(r,100));}}
async function api(path,method='GET',data){const r=await fetch(base+path,{method,headers:{'Content-Type':'application/json'},...(data?{body:JSON.stringify(data)}:{})});const d=await r.json();if(!r.ok)throw Error(JSON.stringify(d));return d;}
const profile=await api('/app/api/coach/profile');const day=profile.today;const end=new Date(day+'T12:00:00Z');end.setUTCDate(end.getUTCDate()+90);
await api('/app/api/coach/profile','PATCH',{available_days:[0,1,2,3,4,5,6]});
await api('/app/api/goal','PUT',{name:'Test race',race_date:end.toISOString().slice(0,10),goal_minutes:240});
await api('/app/api/coach/plan','POST',{start_date:day});
const w=(await api('/app/api/coach/workouts')).find(w=>w.date===day);
await api(`/app/api/coach/workouts/${w.id}/execution`,'POST',{distance_km:w.current.distance_km+2,duration_seconds:3600,average_hr:135,completed:true});
await api(`/app/api/coach/workouts/${w.id}/evaluate`,'POST');
await api('/app/api/garmin-recovery/import','POST',{format:'strideai-garmin-recovery-v1',days:[{date:day,sleep_hours:7}]});
await api('/app/api/journey','PUT',{step:2,finished:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage']});const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(base+'/app');await page.locator('#morningHealthStatus').getByText('Sleep: 7.0 h · Garmin import',{exact:true}).waitFor();
await page.locator('#coachTodayOpen').click();await page.getByText('Why did you run farther? (optional)',{exact:true}).click();
await page.getByLabel('Reason for extra distance',{exact:true}).selectOption('felt_fresh');
await page.getByRole('button',{name:'Save run context',exact:true}).click();
await page.waitForResponse(r=>r.url().endsWith('/app/api/coach/workouts')&&r.status()===200);
await page.reload();await page.locator('#coachTodayOpen').click();await page.getByText('Why did you run farther? (optional)',{exact:true}).click();
if(await page.getByLabel('Reason for extra distance',{exact:true}).inputValue()!=='felt_fresh')throw Error('Reason did not persist');
if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Horizontal overflow');
await page.screenshot({path:'/tmp/strideai-health-run-context.png',fullPage:true});if(errors.length)throw Error(errors.join('\n'));
await browser.close();console.log('Health status and post-review run context mobile flow passed');
})();
