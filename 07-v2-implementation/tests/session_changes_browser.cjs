const {chromium}=require('playwright');
(async()=>{
const base='http://127.0.0.1:8765';for(let i=0;i<60;i++){try{await fetch(base+'/health');break}catch{await new Promise(r=>setTimeout(r,100));}}
const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
const api=async(path,data,method='POST')=>{const r=await page.request.fetch(base+path,{method,data});if(!r.ok())throw Error(await r.text());return r.json()};
const profile=await api('/app/api/coach/profile',undefined,'GET'),today=profile.today;
const day=n=>{const d=new Date(today+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10)};
const goal=await api('/app/api/goal',{name:'Test',race_date:day(90),goal_minutes:230},'PUT');
await api('/app/api/plan',{race_id:goal.id,days:[26,8,5].map((km,i)=>({date:day(i),distance_km:km,activity:'run',note:'Run '+km}))});await api('/app/api/journey/activate-import',{});
await page.goto(base+'/app');await page.locator('#sessionChangeBox summary').click();
await page.locator('#sessionSwapDate').selectOption(day(1));await page.getByRole('button',{name:'Preview change',exact:true}).click();
await page.getByText(today+': 26 km → 8 km · Run 8',{exact:true}).waitFor();
await page.locator('#sessionChangeConfirm').click();await page.waitForFunction(()=>document.getElementById('coachToday').textContent.startsWith('8 km'));
let rows=await api('/app/api/coach/workouts',undefined,'GET');if(rows[0].original.distance_km!==26||rows[1].current.distance_km!==26)throw Error('Swap failed');
await page.locator('#sessionChangeBox summary').click();await page.locator('#sessionChangeAction').selectOption('distance');await page.locator('#sessionChangeReason').selectOption('feeling_good');await page.locator('#sessionNewDistance').fill('10');await page.getByRole('button',{name:'Preview change',exact:true}).click();await page.locator('#sessionChangeConfirm').click();
await page.waitForFunction(()=>document.getElementById('coachToday').textContent.startsWith('10 km'));
await page.locator('#sessionChangeBox summary').click();await page.locator('#sessionChangeAction').selectOption('skip');await page.locator('#sessionChangeReason').selectOption('fatigue');await page.getByRole('button',{name:'Preview change',exact:true}).click();await page.locator('#sessionChangeConfirm').click();
await page.waitForFunction(()=>document.getElementById('coachToday').textContent.includes('Recovery day'));
await page.reload();await page.waitForFunction(()=>document.getElementById('coachToday').textContent.includes('Recovery day'));
rows=await api('/app/api/coach/workouts',undefined,'GET');if(rows[0].current.distance_km!==0||rows[1].current.distance_km!==26)throw Error('Skip changed tomorrow');
if(await page.locator('#coachTodayOpen').isVisible())throw Error('Skipped run should not ask for running targets');
if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
if(errors.length)throw Error(errors.join('; '));console.log('Swap, increase, skip and reload passed');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
