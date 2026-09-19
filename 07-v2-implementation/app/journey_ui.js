(()=>{
'use strict';
const $=id=>document.getElementById(id);
const make=(tag,text,parent,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;if(parent)parent.append(n);return n};
const button=(text,parent,fn,cls='secondary')=>{const b=make('button',text,parent,cls);b.type='button';b.onclick=fn;return b};
const shell=document.querySelector('.shell'), oldNav=document.querySelector('.nav');
const nav=make('nav',null,null,'journey-nav');nav.setAttribute('aria-label','Main navigation');oldNav.after(nav);nav.hidden=true;const menu=make('details',null,nav);make('summary','Plan, progress and settings',menu);const menuLinks=make('div',null,menu,'journey-links');
const loading=make('p','Loading your training…',shell,'card');loading.setAttribute('role','status');
const pages={};let setupState=null, mode='generate', current='today', refreshing=false;
const names={today:'Today',training:'Training',progress:'Progress',you:'You'};
for(const [id,label] of Object.entries(names)){const page=make('div',null,shell,'journey-page');page.id='journey-'+id;page.hidden=true;pages[id]=page;button(label,menuLinks,()=>{menu.open=false;show(id)},'').dataset.page=id;}
function refreshLegacy(tab){refreshing=true;document.querySelector(`[data-tab="${tab}"]`).click();refreshing=false;}
function show(id){current=id;dailyHost.hidden=id!=='today';if(id!=='today'){$('coach').append($('coachDetail'));$('coachDetail').hidden=true;}else dailyHost.append($('coachDetail'));for(const [k,p] of Object.entries(pages))p.hidden=k!==id;setup.hidden=true;nav.hidden=false;for(const b of menuLinks.children){if(b.dataset.page===id)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');}if(id==='training'){refreshLegacy('plan');refreshLegacy('coach');}if(id==='progress'){pages.progress.prepend($('review'));refreshLegacy('review');refreshLegacy('history');refreshLegacy('coach');}if(id==='you'){refreshLegacy('athlete');refreshLegacy('data');}if(id==='today'){weekReview.append($('review'));home().catch(error)};}
const dailyHost=make('div',null,$('today'));dailyHost.id='dailyStepContent';let dailyOpen=false,homeVersion=0,lastStage=null;
for(const id of ['training','progress','you']){const backToday=button('Back to today',pages[id],()=>show('today'));pages[id].prepend(backToday);}
const map={today:'today',coach:'training',plan:'training',review:'progress',history:'progress',athlete:'you',data:'you'};
for(const b of oldNav.children)b.addEventListener('click',()=>{if(!refreshing)show(map[b.dataset.tab]);});
function fold(title,node,parent){const d=make('details',null,parent);make('summary',title,d);d.append(node);return d;}
pages.today.append($('today'));pages.training.append($('coach'));pages.progress.append($('review'));
fold('Past check-ins and outcomes',$('history'),pages.progress);
pages.you.append($('athlete'));
const historyImport=$('coachImport').closest('.card');$('data').append(historyImport);historyImport.querySelector('.hint').textContent='Connect Strava above, or upload Garmin CSV / TCX here. Previously imported activities remain available.';
if($('csvFile'))$('csvFile').closest('.card').hidden=true;
const activities=$('recentActivitiesCard');if(activities)fold('Synced activities',activities,pages.progress);
const dataFold=fold('Connections, imports and access',$('data'),pages.you);dataFold.open=false;
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
// Keep routine decisions visible; measurements and implementation details are optional.
const recoveryGrid=$('sleep_hours').closest('.grid');
const healthFields=make('div',null,null,'grid');
for(const id of ['hrv_ms','hrv_baseline_low','hrv_baseline_high','resting_hr_bpm','recent_load_ratio'])healthFields.append($(id).closest('.field'));
fold('Health measurements (optional)',healthFields,recoveryGrid.parentElement);
recoveryGrid.parentElement.querySelector('.hint').textContent='Tell us how you feel, including muscle soreness. Flag pain separately. Synced health data is used when available.';
fold('Weather for this run (optional)',$('weatherCity').closest('.card'),$('checkinForm'));
const traitCard=$('coachTraits').closest('.card');
traitCard.querySelector('h2').textContent='What StrideAI has learned';
traitCard.querySelector('.hint').textContent='These patterns personalize future guidance. They update as you log sessions; you do not need to manage them.';
fold('What StrideAI has learned',traitCard,pages.progress);
fold('Past health measurements',$('athleteHealth').closest('.field'),$('athleteForm'));
const resultDetails=make('div');
resultDetails.append($('comparison'),$('sleepAvg').closest('.metricrow'),$('factors'));
fold('Why this recommendation?',resultDetails,$('explanation').parentElement);
fold('Record a basic outcome',$('currentOutcome').closest('.card'),$('result'));
recoveryGrid.append($('human_decision').closest('.field'));
const sessionFields=$('planned_activity_type').closest('.grid');
const sessionDetails=fold('Change session details',sessionFields,$('checkinForm').querySelector('.card'));
const checkFold=fold('Check in before training',$('checkinForm'),$('today'));checkFold.id='journeyCheckin';
$('today').insertBefore(checkFold,$('result'));
const stepLabel=make('p','',null,'hint');stepLabel.id='dailyStepLabel';$('coachToday').before(stepLabel);
const dailyError=make('p','',dailyHost);dailyError.id='dailyStepError';dailyError.setAttribute('role','alert');
fold('Check-in recommendation',$('result'),$('today'));
const weekReview=fold('Your weekly review',$('review'),pages.today);weekReview.id='dailyWeeklyReview';weekReview.addEventListener('toggle',()=>{if(weekReview.open)refreshLegacy('review')});
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
const replaceLabel=make('label',null,planHost);replaceLabel.id='replaceImportedPlanLabel';
const replaceImport=make('input',null,replaceLabel);replaceImport.type='checkbox';replaceImport.id='replaceImportedPlan';
replaceLabel.append(document.createTextNode(' Replace my upcoming coaching plan with this saved plan. Completed sessions and locked expectations stay unchanged.'));
const activate=button('Use this imported plan',planHost,async()=>{try{activate.disabled=true;await api('/app/api/journey/activate-import','POST',{replace_existing:replaceImport.checked});await finish();}catch(e){error(e)}finally{activate.disabled=false}});activate.hidden=true;
const message=make('p',null,setup);message.id='journeyMessage';message.setAttribute('role','status');
const actions=make('div',null,setup);actions.id='setupActions';
const back=button('Back',actions,()=>begin(Math.max(0,setupState.step-1)));
const next=button('Continue',actions,advance,'primary');
button('Finish setup later',actions,finish);
const homes=new Map();for(const node of [$('athlete'),$('data'),goalCard,config,importCard,forecastCard]){const marker=document.createComment('home');node.before(marker);homes.set(node,marker);}
function restore(){$('athleteForm').querySelector('button').hidden=false;for(const [n,m] of homes)m.after(n);accessHome.after(accessCard);accessHost.hidden=true;}
async function api(url,method='GET',body){const r=await fetch(url,{method,headers:{'X-StrideAI-Key':localStorage.getItem('strideai_app_key')||'',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});const d=await r.json();if(!r.ok){const e=new Error(typeof d.detail==='string'?d.detail:'Check your entries and try again.');e.status=r.status;throw e;}return d;}
function error(e){message.textContent=e.message;if(e.status===401||e.status===403){for(const p of Object.values(pages))p.hidden=true;setup.hidden=false;nav.hidden=true;accessHost.hidden=false;accessHost.append(accessCard);message.textContent='Enter your private access key to load your profile and continue.';}}
function choose(value){mode=value;generateChoice.setAttribute('aria-pressed',value==='generate');importChoice.setAttribute('aria-pressed',value==='import');config.hidden=value!=='generate';importCard.hidden=value!=='import';activate.hidden=value!=='import';replaceLabel.hidden=value!=='import';next.textContent=value==='generate'?'Finish setup':'Continue with saved plan';}
async function begin(step){try{setupState=await api('/app/api/journey','PUT',{step,finished:false});renderSetup();}catch(e){error(e)}}
function renderSetup(){restore();content.replaceChildren();message.textContent='';for(const p of Object.values(pages))p.hidden=true;setup.hidden=false;nav.hidden=true;steps.replaceChildren();['About you','Your history','Your plan'].forEach((name,i)=>{const s=make('span',`${i+1}. ${name}`,steps);if(i===setupState.step)s.setAttribute('aria-current','step');});back.hidden=setupState.step===0;
if(setupState.step===0){heading.textContent='Make the plan fit your life';description.textContent='Choose your training days and long-run day. Add what you know about your running; everything else can wait.';content.append($('athlete'));$('athleteForm').querySelector('button').hidden=true;refreshLegacy('athlete');next.textContent='Save and continue';}
if(setupState.step===1){heading.textContent='Bring your training history';description.textContent='Connect Strava for automatic updates, or import a Garmin file. You can skip this and start with the mileage you reported.';content.append($('data'));refreshLegacy('data');next.textContent='Continue to plan';}
if(setupState.step===2){heading.textContent='Choose how you want to train';description.textContent='Save your race goal, then let StrideAI build your plan or bring your own. You can also start with daily check-ins and add a plan later.';content.append(goalCard,planHost);planHost.append(config,importCard,replaceLabel,activate,forecastCard);importCard.querySelector('details').open=true;refreshLegacy('plan');refreshLegacy('coach');choose(mode);}
heading.focus();}
async function advance(){try{next.disabled=true;if(setupState.step===0){const form=$('athleteForm');if(!form.reportValidity())return;await form.onsubmit({preventDefault(){}});if(!$('athleteStatus').textContent.startsWith('Profile saved'))throw new Error($('athleteStatus').textContent);await begin(1);}else if(setupState.step===1){await begin(2);}else{const s=await api('/app/api/journey');if(!s.has_plan)throw new Error('Generate or save your plan first, or choose “Finish setup later”.');if(mode==='import'){await api('/app/api/journey/activate-import','POST',{replace_existing:replaceImport.checked});}await finish();}}catch(e){error(e)}finally{next.disabled=false}}
async function finish(){try{setupState=await api('/app/api/journey','PUT',{step:setupState?.step||0,finished:true});restore();config.hidden=false;importCard.hidden=false;show('today');}catch(e){error(e)}}
async function home(){
const version=++homeVersion;homeAction.disabled=true;
const [profile,workouts,plan,history]=await Promise.all([api('/app/api/coach/profile'),api('/app/api/coach/workouts'),api('/app/api/plan'),api('/app/api/history?limit=7')]);
if(version!==homeVersion||current!=='today')return;
const checked=history.some(h=>h.checkin_date===profile.today);
homeAction.className=checked?'secondary':'primary';$('coachTodayOpen').className=checked?'primary':'secondary';
const w=workouts.find(w=>w.date===profile.today), own=plan.days?.find(d=>d.date===profile.today);
$('coachTodayOpen').hidden=!w||(w.current.distance_km===0&&!w.current.strength_session);homeAction.textContent=checked?'Update daily check-in':'Start daily check-in';
if(w?.current.distance_km===0&&w.current.strength_session){$('coachToday').textContent=`Strength · ${w.current.strength_minutes} minutes. No run scheduled. Check in before training; if also playing tennis, choose Tennis and mention strength in the activity note.`;}
else if(w?.current.distance_km===0){$('coachToday').textContent=checked?'Recovery check-in saved. Give yourself time to recover.':'Recovery day. Check in with how you feel; no workout targets are needed.';homeAction.textContent='Recovery check-in';}
else if(w){$('coachToday').textContent=`${w.current.distance_km} km · ${w.current.purpose}. ${w.evaluation?'Session reviewed. See what you learned.':w.execution?'Your run is saved. Review the result.':w.prediction?'Your targets are ready. Review them before training.':checked?'Check-in saved. View your workout to set execution targets.':'Start with a recovery check-in, then review your workout targets.'}`;}
else{$('coachToday').textContent=own?`${own.activity==='rest'?'Recovery day':own.activity==='other'?'Non-running session':own.distance_km+' km run'} · ${own.note||'Your plan'}`:plan.days?.length?'No session scheduled today. Rest or check in with what you choose to do.':'You can check in today, or use guided setup to choose your training plan.';}
homeAction.onclick=()=>{checkFold.open=true;const session=w?.current;if(session||own){$('checkin_date').value=profile.today;$('planned_activity_type').value=session?(session.distance_km>0?'run':session.strength_session?'strength':'rest'):own.activity;$('planned_activity_type').dispatchEvent(new Event('change'));$('planned_intensity').required=false;$('planned_distance_km').value=session?.distance_km??own.distance_km;$('planned_activity_note').value=(session?.purpose||own.note||'').slice(0,200);if(session?.kind==='custom'){const option=make('option','Choose intensity from your plan');option.value='';$('planned_intensity').prepend(option);$('planned_intensity').value='';$('planned_intensity').required=true;}else $('planned_intensity').value=session?.kind==='threshold'?'threshold':session?.kind==='race'?'race':'easy';}$('sleep_hours').focus();};
const running=!!w&&(w.current.distance_km>0||!!w.execution||!!w.prediction);
renderSessionChange(w,workouts,profile.today);
const stage=w?.evaluation?'review':w?.execution?'review':!checked?'checkin':!w?.prediction||!w?.choice?'prepare':'execute';
if(stage==='execute'&&lastStage!==stage){dailyOpen=false;$('coachDetail').hidden=true;}lastStage=stage;
stepLabel.textContent=running?({checkin:'Step 1 of 4 · Check in',prepare:'Step 2 of 4 · Review your run',execute:'Step 3 of 4 · Run and record',review:'Step 4 of 4 · Review and learn'}[stage]):checked?'Check-in saved · You’re set for today':'Today · Check in';
const fillCheckin=homeAction.onclick;
const openCheckin=()=>{fillCheckin();sessionDetails.open=!w&&!own||w?.current.kind==='custom'||!running;};
homeAction.onclick=openCheckin;
homeAction.hidden=running&&stage!=='checkin';
$('coachTodayOpen').hidden=!w||(!running&&!w.current.strength_session)||running&&stage==='checkin';
if(running){$('coachTodayOpen').textContent=stage==='prepare'?'Review today’s run':stage==='execute'?'I’ve finished my run':'Review my result';}
else $('coachTodayOpen').textContent='View strength session';
checkFold.hidden=running&&stage!=='checkin';
if(running&&stage==='checkin')homeAction.onclick=()=>{openCheckin();homeAction.hidden=true;};
$('coachTodayOpen').onclick=async()=>{dailyOpen=true;await openDaily(w,stage);};
const oldShortcut=$('recordWithoutPrediction');if(oldShortcut)oldShortcut.remove();
if(running&&!w.execution&&!w.prediction){const already=button('Already ran? Record the result',$('coachToday').parentElement,async()=>{dailyOpen=true;await openDaily(w,'execute')});already.id='recordWithoutPrediction';}
if(dailyOpen&&w&&stage!=='checkin')await openDaily(w,stage);
if(!running&&checked){homeAction.textContent='Edit today’s check-in';checkFold.open=false;}
homeAction.disabled=false;
}
function renderSessionChange(w,workouts,today){
$('sessionChangeBox')?.remove();
if(!w||w.state!=='planned'||w.execution||w.prediction)return;
const box=make('details',null,$('coachToday').parentElement);box.id='sessionChangeBox';make('summary','Change today’s session',box);
make('p','Preview the effect on your week before saving. Your original plan remains in history.',box,'hint');
const form=make('form',null,box),grid=make('div',null,form,'grid');
const field=(id,label,type)=>{const f=make('div',null,grid,'field');const l=make('label',label,f);l.htmlFor=id;const input=make(type==='select'?'select':'input',null,f);input.id=id;if(type!=='select')input.type=type;return input};
const action=field('sessionChangeAction','Change','select');for(const [v,label] of [['swap','Swap with another day'],['distance','Change distance'],['skip','Skip this session']]){const o=make('option',label,action);o.value=v;}
const reason=field('sessionChangeReason','Why?','select');for(const [v,label] of [['availability','Time / availability'],['fatigue','Tired / need recovery'],['feeling_good','Feeling good'],['other','Other']]){const o=make('option',label,reason);o.value=v;}
const swap=field('sessionSwapDate','Swap with','select');make('option','Choose a day',swap).value='';for(const other of workouts.filter(r=>r.date>today&&r.state==='planned'&&!r.prediction&&!r.execution&&r.current.kind!=='race')){const o=make('option',`${other.date} · ${other.current.distance_km} km · ${other.current.purpose}`,swap);o.value=other.date;}
const distance=field('sessionNewDistance','New distance (km)','number');distance.min='0.1';distance.max='100';distance.step='0.1';distance.value=w.current.distance_km||'';
const note=field('sessionChangeNote','Note (optional)','text');note.maxLength=300;
const preview=make('button','Preview change',form,'secondary');preview.type='submit';
const result=make('div',null,form);result.id='sessionChangePreview';result.setAttribute('role','status');
let proposal=null;
const confirm=button('Save this change',form,async()=>{if(!proposal)return;confirm.disabled=true;try{await api(`/app/api/coach/workouts/${w.id}/change`,'POST',proposal);dailyOpen=false;$('coachDetail').hidden=true;checkFold.open=false;await home();}catch(e){result.textContent=e.message;proposal=null;confirm.hidden=true;}finally{confirm.disabled=false;}},'primary');confirm.id='sessionChangeConfirm';confirm.hidden=true;
const invalidate=()=>{proposal=null;confirm.hidden=true;result.replaceChildren();swap.closest('.field').hidden=action.value!=='swap';swap.required=action.value==='swap';distance.closest('.field').hidden=action.value!=='distance';distance.required=action.value==='distance';distance.disabled=action.value!=='distance';};form.addEventListener('input',invalidate);invalidate();
form.onsubmit=async e=>{e.preventDefault();preview.disabled=true;try{const request={action:action.value,reason:reason.value,note:note.value,swap_date:action.value==='swap'?swap.value:null,distance_km:action.value==='distance'?Number(distance.value):null};const data=await api(`/app/api/coach/workouts/${w.id}/change`,'POST',request);result.replaceChildren();for(const c of data.changes)make('p',`${c.date}: ${c.before_km} km → ${c.after_km} km · ${c.purpose}`,result);for(const week of data.weeks)make('p',`Week of ${week.week}: ${week.before_km} km → ${week.after_km} km`,result);for(const warning of data.warnings)make('p',warning,result);proposal={...request,confirm_token:data.confirm_token};confirm.hidden=false;}catch(e){result.textContent=e.message;}finally{preview.disabled=false;}};
}
async function openDaily(w,stage){
try{dailyError.textContent='';dailyHost.append($('coachDetail'));dailyHost.hidden=false;await window.strideOpenWorkout(w,stage==='checkin'?'prepare':stage);$('coachTodayOpen').hidden=true;
if(stage==='execute'&&!w.execution){const title=make('p','After your run, sync Strava or enter the totals below.',null,'hint');$('coachDetail').prepend(title);const sync=button('Sync Strava',title,async()=>{sync.disabled=true;try{await api('/app/api/strava/sync','POST');await home();}catch(e){dailyError.textContent=e.message;}finally{sync.disabled=false;}});}
}catch(e){dailyError.textContent=e.message;}
}
window.addEventListener('strideai:workouts-loaded',()=>{if(current==='today'&&setup.hidden)home().catch(error)});
window.addEventListener('strideai:checkin-saved',()=>{checkFold.open=false;dailyOpen=true;home().catch(error)});
window.addEventListener('strideai:strava-synced',()=>{if(current==='today'&&setup.hidden)home().catch(error)});
$('saveKey').addEventListener('click',()=>setTimeout(load,100));
async function load(){try{setupState=await api('/app/api/journey');if(setupState.finished){restore();show('today');}else renderSetup();}catch(e){setup.hidden=false;nav.hidden=true;error(e)}finally{loading.remove()}}
load();
})();
