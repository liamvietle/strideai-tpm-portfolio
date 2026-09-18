// Fresh isolated local server with account mode on and secure cookies off for localhost only.
const {chromium}=require('playwright');
(async()=>{
for(let i=0;i<60;i++){try{await fetch('http://127.0.0.1:8765/health');break}catch{await new Promise(r=>setTimeout(r,100));}}
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.stack)});
await page.goto('http://127.0.0.1:8765/app');await page.getByRole('heading',{name:'Set up your account',exact:true}).waitFor();
await page.screenshot({path:'/tmp/strideai-login.png',fullPage:true});
await page.locator('#username').fill('owner');await page.locator('#password').fill('test-owner-password');await page.locator('#setupKey').fill('test-bootstrap-secret');await page.locator('#submit').click();
await page.getByRole('heading',{name:'Make the plan fit your life'}).waitFor();await page.locator('#ap_age').fill('33');await page.getByRole('button',{name:'Save and continue',exact:true}).click();await page.getByRole('heading',{name:'Bring your training history'}).waitFor();await page.getByRole('button',{name:'Finish setup later',exact:true}).click();
await page.getByRole('button',{name:'You',exact:true}).click();await page.getByRole('button',{name:'Create invitation',exact:true}).click();
await page.waitForFunction(()=>document.querySelector('#journey-you [role=status]').textContent.includes('One-use invitation'));
const invite=(await page.locator('#journey-you [role=status]').first().innerText()).split(': ').at(-1);
await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.locator('#toggle').click();await page.getByRole('heading',{name:'Create your account',exact:true}).waitFor();await page.locator('#username').fill('runner');await page.locator('#password').fill('test-runner-password');await page.locator('#invitation').fill(invite);await page.locator('#submit').click();
await page.getByRole('heading',{name:'Make the plan fit your life'}).waitFor();if(await page.locator('#ap_age').inputValue()!=='')throw Error('Leaked owner profile');await page.locator('#ap_age').fill('25');await page.getByRole('button',{name:'Save and continue',exact:true}).click();await page.getByRole('heading',{name:'Bring your training history'}).waitFor();await page.getByRole('button',{name:'Finish setup later',exact:true}).click();
const age=await page.evaluate(async()=>{const r=await fetch('/app/api/coach/profile?athlete_id=viet');return (await r.json()).profile.age;});if(age!==25)throw Error('Identity isolation failed');
await page.getByRole('button',{name:'You',exact:true}).click();await page.getByRole('button',{name:'Sign out',exact:true}).click();
await page.getByRole('heading',{name:'Sign in',exact:true}).waitFor();await page.locator('#username').fill('owner');await page.locator('#password').fill('test-owner-password');await page.locator('#submit').click();await page.locator('.journey-nav').waitFor();await page.getByRole('button',{name:'You',exact:true}).click();await page.waitForFunction(()=>document.getElementById('ap_age').value==='33');
console.log(JSON.stringify({accountFlows:'passed',errors}));await browser.close();if(errors.length)process.exit(1);
})().catch(e=>{console.error(e);process.exit(1)});
