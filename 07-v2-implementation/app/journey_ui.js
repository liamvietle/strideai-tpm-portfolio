(()=>{
'use strict';
const $=id=>document.getElementById(id);
const make=(tag,text,parent,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;if(parent)parent.append(n);return n};
const button=(text,parent,fn,cls='secondary')=>{const b=make('button',text,parent,cls);b.type='button';b.onclick=fn;return b};
const shell=document.querySelector('.shell'), oldNav=document.querySelector('.nav');
const nav=make('nav',null,null,'journey-nav');nav.setAttribute('aria-label','Main navigation');oldNav.after(nav);nav.hidden=true;
const loading=make('p','Loading your training…',shell,'card');loading.setAttribute('role','status');
const pages={};let setupState=null, mode='generate', current='today', refreshing=false;
const names={today:'Today',training:'Training',progress:'Progress',you:'You'};
for(const [id,label] of Object.entries(names)){const page=make('div',null,shell,'journey-page');page.id='journey-'+id;page.hidden=true;pages[id]=page;button(label,nav,()=>show(id),'').dataset.page=id;}
function refreshLegacy(tab){refreshing=true;document.querySelector(`[data-tab="${tab}"]`).click();refreshing=false;}
function show(id){current=id;for(const [k,p] of Object.entries(pages))p.hidden=k!==id;setup.hidden=true;nav.hidden=false;for(const b of nav.children){if(b.dataset.page===id)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}if(id==='training'){refreshLegacy('plan');refreshLegacy('coach');}if(id==='progress'){refreshLegacy('review');refreshLegacy('history');refreshLegacy('coach');}if(id==='you'){refreshLegacy('athlete');refreshLegacy('data');}if(id==='today')home().catch(error);}
const map={today:'today',coach:'training',plan:'training',review:'progress',history:'progress',athlete:'you',data:'you'};
for(const b of oldNav.children)b.addEventListener('click',()=>{if(!refreshing)show(map[b.dataset.tab]);});
function fold(title,node,parent){const d=make('details',null,parent);make('summary',title,d);d.append(node);return d;}
pages.today.append($('today'));pages.training.append($('coach'));pages.progress.append($('review'));
fold('Past check-ins and outcomes',$('history'),pages.progress);
pages.you.append($('athlete'));
const historyImport=$('coachImport').closest('.card');$('data').append(historyImport);historyImport.querySelector('.hint').textContent='Connect Strava above, or upload Garmin CSV / TCX here. Previously imported activities remain available.';
if($('csvFile'))$('csvFile').closest('.card').hidden=true;
const activities=$('recentActivitiesCard');if(activities)fold('Synced activities',activities,pages.progress);
const dataFold=fold('Connections, imports and access',$('data'),pages.you);dataFold.open=true;
const planFold=fold('Race goal and imported calendar',$('plan'),pages.training);
// Keep generated sessions together and tuck setup controls away once training begins.
const coachCard=$('coachGenerate').closest('.card');
const config=make('div');
while(coachCard.firstChild && coachCard.firstChild!==$('coachWeek').parentElement)config.append(coachCard.firstChild);
const calendarTitle=make('h2','This week’s sessions');coachCard.prepend(calendarTitle);
const configFold=fold('Create or replace your plan',config,pages.training);pages.training.prepend(configFold);
config.querySelector('h2').textContent='Build your training plan';
for(const p of config.querySelectorAll(':scope > p'))if(p.textContent.includes('Save your race in Plan'))p.textContent='Choose a start date, then generate a plan from your profile and recent training.';
config.append($('coachGenerate'));config.append($('coachStatus'));
const forecastCard=$('raceForecast').parentElement;forecastCard.classList.add('card');pages.progress.prepend(forecastCard);
const goalCard=$('goalForm').closest('.card');const importCard=$('planText').closest('.card');
importCard.querySelector('summary').textContent='Bring your own plan';
$('savePlan').textContent='Save imported plan';$('editPlan').textContent='Load saved plan';
const fileLabel=make('label','Upload a plan text file',importCard.querySelector('details'),'field');
const file=make('input',null,fileLabel);file.type='file';file.accept='.txt';file.id='journeyPlanFile';
file.onchange=async()=>{if(file.files[0]){if(file.files[0].size>250000){error(new Error('Choose a plan file smaller than 250 KB.'));return;}$('planText').value=await file.files[0].text();}};
make('p','Use the dated session format shown above. You can paste your plan or upload a .txt file; spreadsheets and PDFs need conversion first.',fileLabel,'hint');
// Basic profile first; optional measurements are still editable in one place.
const advanced=make('details');make('summary','Optional body and fitness measurements',advanced);const advancedGrid=make('div',null,advanced,'grid');
for(const key of ['sex','gender','height_cm','weight_kg','resting_hr','hrv_ms','vo2max','threshold_pace','threshold_hr','max_hr'])advancedGrid.append($('ap_'+key).closest('.field'));
$('athleteFields').after(advanced);
fold('Past race results (optional)',$('athletePB').closest('.field'),$('athleteForm'));
for(const o of $('ap_race_priority').options)o.textContent={A:'A · Main goal race',B:'B · Secondary race',C:'C · Training event'}[o.value];
const strengthVisibility=()=>{$('strengthDays').hidden=!$('addStrength').checked;};
$('addStrength').addEventListener('change',strengthVisibility);window.addEventListener('strideai:profile-loaded',strengthVisibility);strengthVisibility();
const injury=$('athleteActiveInjury').closest('.checks');$('athleteForm').insertBefore(injury,advanced);
$('recommendBtn').textContent='Get today’s guidance';
$('planned_activity_type').addEventListener('change',()=>{$('planned_intensity').required=false;});
$('coachTodayOpen').textContent='View workout and results';
$('coachTodayOpen').parentElement.querySelector('.hint').hidden=true;
$('coachToday').previousElementSibling.textContent='Your next step';
$('checkinForm').querySelector('h2').textContent='Daily check-in';
$('checkinForm').querySelector('.hint').textContent='Confirm today’s session and tell us how you feel. Optional health numbers can stay blank.';
const checkFold=fold('Check in before training',$('checkinForm'),$('today'));checkFold.id='journeyCheckin';
$('today').insertBefore(checkFold,$('result'));
const homeIntro=make('p','Before training, check in and review your targets. Afterward, sync your activity and record how it felt.',null,'hint');$('today').prepend(homeIntro);
const homeAction=button('Start daily check-in',$('coachToday').parentElement,()=>{checkFold.open=true;$('sleep_hours').focus();});homeAction.id='journeyCheckinButton';homeAction.disabled=true;
const editSetup=button('Review guided setup',pages.you,()=>begin(0));
// Hide operational diagnostics behind an explicit maintenance disclosure.
const metricsCard=$('metrics').closest('.card');fold('App diagnostics',metricsCard,$('data'));
const setup=make('section',null,shell);setup.id='journeySetup';setup.hidden=true;
const welcome=make('div',null,setup,'card');welcome.id='journeyWelcome';
const heading=make('h1','Let’s build your running routine',welcome);heading.tabIndex=-1;
const description=make('p','Start with a few details. You can connect your history and choose a plan next. Missing information can be added later.',welcome);
const steps=make('div',null,welcome);steps.id='setupSteps';
const accessHost=make('div',null,setup);accessHost.hidden=true;
const accessCard=$('appKey').closest('.card');const accessHome=make('span',null,accessCard.parentElement);accessCard.before(accessHome);
const content=make('div',null,setup);content.id='setupContent';
const choices=make('div',null,null,'journey-choice');
const generateChoice=button('Build a plan for me\nUse my profile, availability and training history.',choices,()=>choose('generate'),'');
const importChoice=button('I already have a plan\nKeep my own sessions and use daily guidance.',choices,()=>choose('import'),'');
const planHost=make('div');planHost.id='journeyPlanChoice';planHost.append(choices);
const activate=button('Use this imported plan',planHost,async()=>{try{activate.disabled=true;await api('/app/api/journey/activate-import','POST',{});await finish();}catch(e){error(e)}finally{activate.disabled=false}});activate.hidden=true;
const message=make('p',null,setup);message.id='journeyMessage';message.setAttribute('role','status');
const actions=make('div',null,setup);actions.id='setupActions';
const back=button('Back',actions,()=>begin(Math.max(0,setupState.step-1)));
const next=button('Continue',actions,advance,'primary');
button('Finish setup later',actions,finish);
const homes=new Map();for(const node of [$('athlete'),$('data'),goalCard,config,importCard,forecastCard]){const marker=document.createComment('home');node.before(marker);homes.set(node,marker);}
function restore(){$('athleteForm').querySelector('button').hidden=false;for(const [n,m] of homes)m.after(n);accessHome.after(accessCard);accessHost.hidden=true;}
async function api(url,method='GET',body){const r=await fetch(url,{method,headers:{'X-StrideAI-Key':localStorage.getItem('strideai_app_key')||'',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});const d=await r.json();if(!r.ok){const e=new Error(typeof d.detail==='string'?d.detail:'Check your entries and try again.');e.status=r.status;throw e;}return d;}
function error(e){message.textContent=e.message;if(e.status===401||e.status===403){for(const p of Object.values(pages))p.hidden=true;setup.hidden=false;nav.hidden=true;accessHost.hidden=false;accessHost.append(accessCard);message.textContent='Enter your private access key to load your profile and continue.';}}
function choose(value){mode=value;generateChoice.setAttribute('aria-pressed',value==='generate');importChoice.setAttribute('aria-pressed',value==='import');config.hidden=value!=='generate';importCard.hidden=value!=='import';activate.hidden=value!=='import';next.textContent=value==='generate'?'Finish setup':'Continue with saved plan';}
async function begin(step){try{setupState=await api('/app/api/journey','PUT',{step,finished:false});renderSetup();}catch(e){error(e)}}
function renderSetup(){restore();content.replaceChildren();message.textContent='';for(const p of Object.values(pages))p.hidden=true;setup.hidden=false;nav.hidden=true;steps.replaceChildren();['About you','Your history','Your plan'].forEach((name,i)=>{const s=make('span',`${i+1}. ${name}`,steps);if(i===setupState.step)s.setAttribute('aria-current','step');});back.hidden=setupState.step===0;
if(setupState.step===0){heading.textContent='Make the plan fit your life';description.textContent='Choose your training days and long-run day. Add what you know about your running; everything else can wait.';content.append($('athlete'));$('athleteForm').querySelector('button').hidden=true;refreshLegacy('athlete');next.textContent='Save and continue';}
if(setupState.step===1){heading.textContent='Bring your training history';description.textContent='Connect Strava for automatic updates, or import a Garmin file. You can skip this and start with the mileage you reported.';content.append($('data'));refreshLegacy('data');next.textContent='Continue to plan';}
if(setupState.step===2){heading.textContent='Choose how you want to train';description.textContent='Save your race goal, then let StrideAI build your plan or bring your own. You can also start with daily check-ins and add a plan later.';content.append(goalCard,planHost);planHost.append(config,importCard,activate,forecastCard);importCard.querySelector('details').open=true;refreshLegacy('plan');refreshLegacy('coach');choose(mode);}
heading.focus();}
async function advance(){try{next.disabled=true;if(setupState.step===0){const form=$('athleteForm');if(!form.reportValidity())return;await form.onsubmit({preventDefault(){}});if(!$('athleteStatus').textContent.startsWith('Profile saved'))throw new Error($('athleteStatus').textContent);await begin(1);}else if(setupState.step===1){await begin(2);}else{const s=await api('/app/api/journey');if(!s.has_plan)throw new Error('Generate or save your plan first, or choose “Finish setup later”.');if(mode==='import'){await api('/app/api/journey/activate-import','POST',{});}await finish();}}catch(e){error(e)}finally{next.disabled=false}}
async function finish(){try{setupState=await api('/app/api/journey','PUT',{step:setupState?.step||0,finished:true});restore();config.hidden=false;importCard.hidden=false;show('today');}catch(e){error(e)}}
async function home(){
homeAction.disabled=true;
const [profile,workouts,plan,history]=await Promise.all([api('/app/api/coach/profile'),api('/app/api/coach/workouts'),api('/app/api/plan'),api('/app/api/history?limit=7')]);
const checked=history.some(h=>h.checkin_date===profile.today);
homeAction.className=checked?'secondary':'primary';$('coachTodayOpen').className=checked?'primary':'secondary';
const w=workouts.find(w=>w.date===profile.today), own=plan.days?.find(d=>d.date===profile.today);
$('coachTodayOpen').hidden=!w||w.current.distance_km===0;homeAction.textContent=checked?'Update daily check-in':'Start daily check-in';
if(w?.current.distance_km===0){$('coachToday').textContent=checked?'Recovery check-in saved. Give yourself time to recover.':'Recovery day. Check in with how you feel; no workout targets are needed.';homeAction.textContent='Recovery check-in';}
else if(w){$('coachToday').textContent=`${w.current.distance_km} km · ${w.current.purpose}. ${w.evaluation?'Session reviewed. See what you learned.':w.execution?'Your run is saved. Review the result.':w.prediction?'Your targets are ready. Review them before training.':checked?'Check-in saved. View your workout to set execution targets.':'Start with a recovery check-in, then review your workout targets.'}`;}
else{$('coachToday').textContent=own?`${own.activity==='rest'?'Recovery day':own.activity==='other'?'Non-running session':own.distance_km+' km run'} · ${own.note||'Your plan'}`:plan.days?.length?'No session scheduled today. Rest or check in with what you choose to do.':'You can check in today, or use guided setup to choose your training plan.';}
homeAction.onclick=()=>{checkFold.open=true;const session=w?.current;if(session||own){$('checkin_date').value=profile.today;$('planned_activity_type').value=session?(session.distance_km>0?'run':'rest'):own.activity;$('planned_activity_type').dispatchEvent(new Event('change'));$('planned_intensity').required=false;$('planned_distance_km').value=session?.distance_km??own.distance_km;$('planned_activity_note').value=(session?.purpose||own.note||'').slice(0,200);if(session?.kind==='custom'){const option=make('option','Choose intensity from your plan');option.value='';$('planned_intensity').prepend(option);$('planned_intensity').value='';$('planned_intensity').required=true;}else $('planned_intensity').value=session?.kind==='threshold'?'threshold':session?.kind==='race'?'race':'easy';}$('sleep_hours').focus();};
homeAction.disabled=false;
}
window.addEventListener('strideai:workouts-loaded',()=>{if(current==='today'&&setup.hidden)home().catch(error)});
window.addEventListener('strideai:checkin-saved',()=>{checkFold.open=false;home().catch(error)});
window.addEventListener('strideai:strava-synced',()=>{if(current==='today'&&setup.hidden)home().catch(error)});
$('saveKey').addEventListener('click',()=>setTimeout(load,100));
async function load(){try{setupState=await api('/app/api/journey');if(setupState.finished){restore();show('today');}else renderSetup();}catch(e){setup.hidden=false;nav.hidden=true;error(e)}finally{loading.remove()}}
load();
})();
