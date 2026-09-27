(()=>{
const host=document.getElementById('today'),date=document.getElementById('checkin_date');if(!host||!date)return;
const make=(tag,text,parent)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(parent)parent.append(n);return n};
const card=make('div');card.className='card';card.id='morningHealthStatus';host.prepend(card);
make('h3','Health data for your check-in',card);const summary=make('p','Checking availability…',card);summary.setAttribute('role','status');
const rows=make('div',null,card);const detail=make('details',null,card);make('summary','Sources and dates',detail);const source=make('div',null,detail);
const button=make('button','Refresh health status',card);button.type='button';button.className='secondary';
let version=0;
async function refresh(){const request=++version;button.disabled=true;try{const r=await fetch('/app/api/coach/recovery-status'+(date.value?'?day='+encodeURIComponent(date.value):''),{headers:{'X-StrideAI-Key':localStorage.getItem('strideai_app_key')||''}});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Could not load health status.');if(request!==version)return;
summary.textContent=`${d.date}: ${d.status==='complete'?'All three measurements available':d.status==='partial'?'Some measurements are missing':'No measurements received for this date'}`;
rows.replaceChildren();source.replaceChildren();for(const m of d.metrics){const value=m.field==='sleep_hours'?`${Number(m.value).toFixed(1)} h`:m.field==='hrv_ms'?`${m.value} ms`:`${m.value} bpm`;make('p',`${m.label}: ${m.available?value+' · '+m.source:'Missing'}`,rows);if(m.record_updated_at)make('p',`${m.label} record updated: ${new Date(m.record_updated_at.includes('T')?m.record_updated_at:m.record_updated_at.replace(' ','T')+'Z').toLocaleString()}`,source);}
make('p',`Latest Garmin import date: ${d.garmin_latest_date||'None'}. Latest Apple Health date: ${d.apple_latest_date||'None'}.`,source);make('p',d.garmin_note,source);make('p',d.usage_note,source);
make('p','Refresh checks data already received by StrideAI. To send new data, sync the iPhone companion or import your Garmin recovery export.',source);
}catch(e){if(request===version){summary.textContent=e.message;rows.replaceChildren();source.replaceChildren();}}finally{if(request===version)button.disabled=false;}}
button.onclick=refresh;date.addEventListener('change',refresh);window.addEventListener('focus',refresh);refresh();
})();
