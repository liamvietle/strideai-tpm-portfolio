(()=>{
'use strict';
const make=(tag,text,parent)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(parent)parent.append(n);return n};
const host=document.getElementById('journey-today');if(!host)return;
const panel=make('details',null,host);panel.className='card';panel.id='askCoachPanel';make('summary','Ask your coach',panel);
make('p','Ask about progress, a difficult session or your race goal. Your coach uses your saved training history. Advice here does not change your plan. Questions and selected training context are sent to the configured AI provider.',panel);
const choices=make('div',null,panel);choices.className='checks';
const form=make('form',null,panel);
const label=make('label','Your question',form);label.htmlFor='coachQuestion';label.className='field';
const input=make('textarea',null,label);input.id='coachQuestion';input.rows=3;input.maxLength=1200;input.minLength=5;input.required=true;input.style.cssText='width:100%;box-sizing:border-box';
const sessionLabel=make('label','Related session (optional)',form);sessionLabel.htmlFor='coachQuestionWorkout';sessionLabel.className='field';
const select=make('select',null,sessionLabel);select.id='coachQuestionWorkout';make('option','General question',select).value='';
const follow=make('p','New question',form);follow.className='hint';
const submit=make('button','Ask coach',form);submit.type='submit';submit.className='primary';
const fresh=make('button','New question',form);fresh.type='button';fresh.className='secondary';
const status=make('p',null,panel);status.setAttribute('role','status');
const output=make('div',null,panel);output.id='coachQuestionAnswer';output.setAttribute('aria-live','polite');
const past=make('details',null,panel);make('summary','Previous questions',past);const list=make('div',null,past);
let parent=null,loaded=false,busy=false;
async function api(url,method='GET',body){const r=await fetch(url,{method,headers:{'X-StrideAI-Key':localStorage.getItem('strideai_app_key')||'',...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Please check your question and try again.');return d;}
function reset(){parent=null;choices.hidden=false;follow.textContent='New question';output.replaceChildren();input.value='';status.textContent='';}
fresh.onclick=reset;
function evidenceCard(id,data,container){const box=make('details',null,container);make('summary',data?.title||id.replaceAll('_',' '),box);if(data?.url){const a=make('a',data.title,box);a.href=data.url;a.target='_blank';a.rel='noopener';make('p',data.summary,box);make('p',data.limits,box);}else{const omit=new Set(['id','workout_id','activity_id','activity_ids','allowed_next_steps','rule','method','provider','prediction_valid']);const show=(value,parent,depth=0)=>{if(value===null||value===undefined)return;if(typeof value!=='object'){make('p',String(value),parent);return;}for(const [key,v] of Object.entries(value)){if(omit.has(key)||v===null||v===undefined)continue;const label=key.replaceAll('_',' ');if(typeof v!=='object')make('p',`${label}: ${v}`,parent);else if(depth<3){const sub=make('details',null,parent);make('summary',label,sub);show(v,sub,depth+1);}}};show(data,box);}}
function render(result){output.replaceChildren();choices.hidden=true;parent=result.id;follow.textContent='Your next question will follow up on this answer.';
make('p',result.question,output);make('p',`${result.ai_trace.fallback?'Data summary (AI unavailable)':'AI coach · '+result.ai_trace.model} · ${result.created_at}`,output).className='hint';
if(result.safety_notice)make('p',result.safety_notice,output);
for(const key of ['message','historical_context','learning'])make('p',result.briefing[key].text,output);
make('h3','What to do next',output);make('p',result.next_step,output);
if(result.briefing.uncertainty)make('p',result.briefing.uncertainty,output).className='hint';
const detail=make('details',null,output);make('summary','Evidence and sources',detail);
const ids=new Set(['training_trend','retrieval_limits',...['message','historical_context','learning'].flatMap(k=>result.briefing[k].evidence_ids)]);
for(const id of ids)if(result.evidence[id])evidenceCard(id,result.evidence[id],detail);
}
async function history(){const d=await api('/app/api/coach/questions');list.replaceChildren();for(const item of d.history){const b=make('button',item.question,list);b.type='button';b.className='secondary';b.onclick=async()=>{try{render(await api('/app/api/coach/questions/'+item.id));}catch(e){status.textContent=e.message;}};}return d;}
panel.addEventListener('toggle',async()=>{if(!panel.open||loaded)return;try{const [d,workouts]=await Promise.all([history(),api('/app/api/coach/workouts')]);for(const q of d.suggestions){const b=make('button',q,choices);b.type='button';b.className='secondary';b.onclick=()=>{reset();input.value=q;input.focus();};}for(const w of workouts.filter(w=>w.execution).slice(-30).reverse()){const o=make('option',`${w.date} · ${w.current.kind}`,select);o.value=w.id;}loaded=true;}catch(e){status.textContent=e.message;}});
form.onsubmit=async event=>{event.preventDefault();if(busy||!form.reportValidity())return;busy=true;submit.disabled=fresh.disabled=true;status.textContent='Reviewing your training…';try{let result=await api('/app/api/coach/questions','POST',{question:input.value,workout_id:select.value?Number(select.value):null,parent_id:parent});for(let i=0;result.status==='pending'&&i<30;i++){await new Promise(r=>setTimeout(r,1500));result=await api('/app/api/coach/questions/'+result.id);}if(result.status!=='ready')throw Error('Your answer is still processing. Try opening it again shortly.');render(result);input.value='';status.textContent='';await history();}catch(e){status.textContent=e.message;}finally{busy=false;submit.disabled=fresh.disabled=false;}};
})();
