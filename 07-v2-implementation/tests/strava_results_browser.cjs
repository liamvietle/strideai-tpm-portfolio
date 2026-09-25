const {chromium}=require('playwright');
const {execFileSync}=require('child_process');
(async()=>{
const base='http://127.0.0.1:8765';for(let i=0;i<60;i++){try{await fetch(base+'/health');break}catch{await new Promise(r=>setTimeout(r,100));}}
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
const api=async(path,data,method='POST')=>{const r=await page.request.fetch(base+path,{method,data});if(!r.ok())throw Error(await r.text());return r.json()};
const {today}=await api('/app/api/coach/profile',undefined,'GET');
const race=new Date(today+'T12:00:00Z');race.setUTCDate(race.getUTCDate()+90);
const goal=await api('/app/api/goal',{name:'Test',race_date:race.toISOString().slice(0,10),goal_minutes:230},'PUT');
await api('/app/api/plan',{race_id:goal.id,days:[{date:today,distance_km:5,activity:'run',note:'Easy run'}]});await api('/app/api/journey/activate-import',{});
execFileSync('python',['-c',`from app.storage import upsert_activities\nfrom app.models import ActivityRecord\nupsert_activities([ActivityRecord(source='strava',source_activity_id='browser',athlete_id='viet',start_time='${today}T00:00:00Z',activity_type='Run',raw_format='strava-api-summary',distance_km=5,duration_seconds=1800,average_hr=140)])`]);
if(process.env.COACH_PREVIEW){
 await page.route('**/app/api/coach/workouts/*/briefing',async route=>{
  const response=await route.fetch(), d=await response.json();
  if(d.status==='ready'){
   d.ai_trace={fallback:false,model:'test-model'};
   d.briefing.message.text='You completed the intended distance. Your heart rate is recorded, but effort is still unknown.';
   d.briefing.historical_context.text='There is not enough comparable history here to say this run was easier than usual.';
  }
  await route.fulfill({json:d});
 });
}
await page.goto(base+'/app');
await page.getByRole('button',{name:'Review my result',exact:true}).click();
await page.getByText('Run synced · ready to review',{exact:true}).waitFor();
if(await page.locator('#ex_distance').count())throw Error('Should not show metric entry for synced run');
await page.locator('#coachDetail').getByRole('button',{name:'Review my result',exact:true}).click();
await page.getByText('Run details and comparison evidence',{exact:true}).click();
await page.getByRole('heading',{name:'Expected vs actual',exact:true}).waitFor();
await page.getByText(process.env.COACH_PREVIEW?'AI coach · test-model':'Saved guidance · AI commentary unavailable',{exact:true}).waitFor();
if(!await page.getByRole('region',{name:'Your coach'}).isVisible())throw Error('Coach message missing');
const rows=await api('/app/api/coach/workouts',undefined,'GET');
if(rows[0].execution.distance_km!==5||rows[0].execution.rpe!==null||!rows[0].evaluation)throw Error('Review failed');
if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
await page.getByText('Run details and comparison evidence',{exact:true}).click();
await page.screenshot({path:'/tmp/strideai-coach-mobile.png',fullPage:true});
if(errors.length)throw Error(errors.join('; '));console.log('Automatic link, metrics and review without RPE passed');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
