// Isolated fresh database at localhost:8765; MODE=import covers the alternative path.
const {chromium}=require('playwright');
(async()=>{
for(let i=0;i<60;i++){try{await fetch('http://127.0.0.1:8765/health');break}catch{await new Promise(r=>setTimeout(r,100));}}
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:390,height:844}}), errors=[];
page.on('pageerror',e=>{errors.push(e.message);console.error(e.stack);});
await page.goto('http://127.0.0.1:8765/app');
await page.getByRole('heading',{name:'Make the plan fit your life'}).waitFor();
for(const c of await page.locator('[name=availableDay]').all())await c.check();
await page.screenshot({path:'/tmp/strideai-setup-mobile.png',fullPage:true});
await page.locator('#ap_age').fill('33');await page.locator('#ap_recent_weekly_km').fill('30');
if(process.env.MODE==='strength'){
const profile=await (await page.request.get('http://127.0.0.1:8765/app/api/coach/profile')).json();
const weekday=(new Date(profile.today+'T12:00:00Z').getUTCDay()+6)%7;
await page.locator(`[name=availableDay][value="${weekday}"]`).uncheck();
await page.locator('#addStrength').check();await page.locator(`[name=strengthDay][value="${weekday}"]`).check();
}
await page.getByRole('button',{name:'Save and continue',exact:true}).click();
await page.getByRole('heading',{name:'Bring your training history'}).waitFor();
await page.reload();await page.getByRole('heading',{name:'Bring your training history'}).waitFor();
await page.getByRole('button',{name:'Continue to plan',exact:true}).click();
await page.getByRole('heading',{name:'Choose how you want to train'}).waitFor();
const today=await page.locator('#coachStart').inputValue();const end=new Date(today+'T12:00:00Z');end.setUTCDate(end.getUTCDate()+90);
await page.locator('#raceName').fill('My first plan');await page.locator('#raceDate').fill(end.toISOString().slice(0,10));await page.locator('#raceTime').fill('04:00');await page.locator('#goalForm button').click();await page.waitForFunction(()=>document.getElementById('goalStatus').textContent.includes('saved'));
if(process.env.MODE==='import'){
await page.getByRole('button',{name:/I already have a plan/}).click();
await page.locator('#planText').fill(`${today} | 5 | run | My easy run\n${end.toISOString().slice(0,10)} | 0 | other | Strength`);
await page.locator('#savePlan').click();await page.waitForFunction(()=>document.getElementById('planImportStatus').textContent.includes('Saved'));
await page.getByRole('button',{name:'Use this imported plan',exact:true}).click();
}else{
await page.locator('#coachGenerate').click();await page.waitForFunction(()=>document.getElementById('coachStatus').textContent.includes('sessions generated'));
await page.getByRole('button',{name:'Finish setup',exact:true}).click();
}
await page.locator('.journey-nav').waitFor();
if(await page.locator('.journey-nav button:visible').count()!==4)throw Error('Expected four navigation choices');
if(process.env.MODE==='strength'){
await page.waitForFunction(()=>document.getElementById('coachToday').textContent.includes('No run scheduled'));
await page.locator('#coachTodayOpen').click();
await page.getByText('30 minutes strength · no run scheduled',{exact:true}).waitFor();
if(await page.getByRole('button',{name:'Lock pre-run expectation',exact:true}).count())throw Error('Strength must not offer a running prediction');
await page.getByRole('button',{name:'Today',exact:true}).click();await page.locator('#journeyCheckinButton').click();
if(await page.locator('#planned_activity_type').inputValue()!=='strength')throw Error('Expected strength check-in');
await page.locator('#planned_activity_type').selectOption('tennis');await page.locator('#planned_intensity').selectOption('easy');await page.locator('#planned_activity_note').fill('Tennis and 30 minutes strength');
await page.locator('#sleep_hours').fill('08:00');await page.locator('#recommendBtn').click();
await page.waitForFunction(()=>/saved|locked/i.test(document.getElementById('submitStatus').textContent));
if(errors.length)throw Error(errors.join('; '));console.log('Strength-only setup, plan display and tennis check-in passed');await browser.close();return;
}
await page.locator('#journeyCheckinButton').click();if(process.env.MODE==='import')await page.locator('#planned_intensity').selectOption('easy');await page.locator('#sleep_hours').fill('08:00');await page.locator('#recommendBtn').click();await page.waitForFunction(()=>document.getElementById('submitStatus').textContent.includes('Decision locked'));
await page.getByRole('button',{name:'Training',exact:true}).click();await page.locator('#coachDays button').first().click();await page.locator('#coachDetail').waitFor();
await page.getByRole('button',{name:'Lock pre-run expectation',exact:true}).click();
await page.getByRole('button',{name:'Accept adjustment',exact:true}).click();
await page.getByText('Pre-run choice: accept',{exact:true}).waitFor();
await page.locator('#ex_distance').fill('5');await page.locator('#ex_duration').fill('35');await page.locator('#ex_hr').fill('138');await page.locator('#ex_rpe').fill('3');
await page.getByRole('button',{name:'Save execution and evaluate',exact:true}).click();
await page.getByRole('heading',{name:'Expected vs actual',exact:true}).waitFor();
await page.getByRole('button',{name:'Progress',exact:true}).click();await page.locator('#coachReview').waitFor();
await page.getByRole('button',{name:'You',exact:true}).click();await page.locator('#ap_age').waitFor();
await page.getByRole('button',{name:'Today',exact:true}).click();await page.reload();await page.locator('.journey-nav').waitFor();
await page.locator('#coachToday').waitFor();await page.waitForFunction(()=>!document.getElementById('journeyCheckinButton').disabled);
await page.screenshot({path:'/tmp/strideai-journey-'+(process.env.MODE||'generate')+'.png',fullPage:true});
if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))errors.push('Mobile overflow');
console.log(JSON.stringify({mode:process.env.MODE||'generate',errors}));await browser.close();if(errors.length)process.exit(1);
})().catch(e=>{console.error(e);process.exit(1)});
