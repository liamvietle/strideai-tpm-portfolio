const {chromium}=require('playwright');
(async()=>{
for(let i=0;i<60;i++){try{await fetch('http://127.0.0.1:8765/health');break}catch{await new Promise(r=>setTimeout(r,100));}}
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE,args:['--no-sandbox','--disable-dev-shm-usage']});
const page=await browser.newPage({viewport:{width:390,height:844}}), errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8765/app');
await page.getByRole('button',{name:'Finish setup later',exact:true}).click();
await page.locator('#askCoachPanel > summary').click();
await page.getByRole('button',{name:'Am I improving over the last six weeks?',exact:true}).click();
await page.getByRole('button',{name:'Ask coach',exact:true}).click();
await page.locator('#coachQuestionAnswer').getByText('Data summary (AI unavailable)',{exact:false}).waitFor();
if(!await page.locator('#coachQuestionAnswer').textContent().then(s=>s.includes('AI coaching is unavailable')))throw Error('Missing honest fallback');
await page.locator('#coachQuestionAnswer').getByText('Evidence and sources',{exact:true}).click();
await page.screenshot({path:'/tmp/strideai-ask-coach-mobile.png',fullPage:true});
if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1))throw Error('Horizontal overflow');
if(errors.length)throw Error(errors.join('\n'));
await browser.close();console.log('Coach question mobile flow passed');
})();
