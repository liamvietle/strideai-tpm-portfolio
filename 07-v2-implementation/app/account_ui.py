"""Login and account controls. Credentials never enter browser local storage."""
import json

LOGIN_HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in · StrideAI</title>
<style>body{font:16px system-ui;background:#f5f7fb;color:#111827;margin:0;padding:24px}main{max-width:400px;margin:8vh auto;background:white;padding:28px;border-radius:18px}label{display:block;margin:16px 0 6px}input,button{box-sizing:border-box;width:100%;font:inherit;padding:12px;border:1px solid #ccc;border-radius:8px}button{margin-top:20px;background:#2563eb;color:white;cursor:pointer}p{line-height:1.5}#message{color:#b91c1c}a{color:#2563eb}[hidden]{display:none!important}</style></head>
<body><main><h1>StrideAI</h1><h2 id="title">Sign in</h2><p id="intro">Your training, in one place.</p>
<form id="loginForm"><label for="username">Username</label><input id="username" autocomplete="username" pattern="[A-Za-z0-9_.-]{3,40}" required maxlength="40">
<label for="password">Password</label><input id="password" type="password" autocomplete="current-password" minlength="12" maxlength="128" required>
<div id="setupField" hidden><label for="setupKey">Existing StrideAI access key</label><input id="setupKey" type="password" autocomplete="off"><p>This one-time step links your existing training history to your account.</p></div>
<div id="inviteField" hidden><label for="invitation">Invitation code</label><input id="invitation" autocomplete="off" maxlength="256"></div>
<button id="submit">Sign in</button><p id="message" role="status"></p></form>
<button id="toggle" type="button">I have an invitation</button><p>Use at least 12 characters for your password. Password recovery currently requires help from the app owner.</p><a href="/privacy">Privacy</a></main>
<script>
let mode='login';const $=id=>document.getElementById(id);
function render(){const setup=mode==='bootstrap',register=mode==='register';$('setupField').hidden=!setup;$('inviteField').hidden=!register;$('toggle').hidden=setup;$('title').textContent=setup?'Set up your account':register?'Create your account':'Sign in';$('submit').textContent=$('title').textContent;$('toggle').textContent=register?'Back to sign in':'I have an invitation';$('password').autocomplete=mode==='login'?'current-password':'new-password';}
$('toggle').onclick=()=>{mode=mode==='login'?'register':'login';render()};
fetch('/auth/status').then(r=>r.json()).then(s=>{if(!s.initialized)mode='bootstrap';render()}).catch(()=>$('message').textContent='Unable to load sign-in. Refresh to try again.');
$('loginForm').onsubmit=async e=>{e.preventDefault();$('submit').disabled=true;$('message').textContent='';try{const r=await fetch('/auth/'+mode,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:$('username').value,password:$('password').value,setup_key:$('setupKey').value,invite:$('invitation').value})});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Check your username and password requirements.');localStorage.removeItem('strideai_app_key');location.replace('/app');}catch(e){$('message').textContent=e.message}finally{$('submit').disabled=false}};
</script></body></html>'''


def with_account_ui(html, account):
    # Escape '<' so data cannot close the script element.
    csrf=json.dumps(account['csrf']).replace('<','\\u003c')
    prefix='''<script>(()=>{const original=window.fetch.bind(window);window.fetch=(input,options={})=>{const url=new URL(typeof input==='string'?input:input.url,location.href);if(url.origin===location.origin){const headers=new Headers(options.headers||(input instanceof Request?input.headers:undefined));headers.set('X-CSRF-Token',__CSRF_VALUE__);options={...options,headers};}return original(input,options).then(r=>{if(r.status===401&&url.origin===location.origin)location.replace('/login');return r;});};})();</script>'''.replace('__CSRF_VALUE__',csrf)
    suffix=r'''<script>(()=>{
const host=document.getElementById('journey-you'),card=document.createElement('div');card.className='card';host.prepend(card);
const add=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;card.append(e);return e;};
const status=add('p','');status.setAttribute('role','status');
const call=async(path,body={})=>{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Check the values and try again.');return d;};
const action=(text,fn)=>{const b=add('button',text);b.type='button';b.className='secondary';b.style.margin='6px';b.onclick=async()=>{try{b.disabled=true;await fn()}catch(e){status.textContent=e.message}finally{b.disabled=false}};return b;};
fetch('/auth/me').then(r=>r.json()).then(a=>{add('h2','Account: '+a.username);if(a.owner)action('Create invitation',async()=>{const d=await call('/auth/invitations');status.textContent='One-use invitation (valid 24 hours): '+d.invitation;status.style.overflowWrap='anywhere';});});
action('Sign out',async()=>{await call('/auth/logout');location.replace('/login')});
const form=add('form','');const title=document.createElement('h3');title.textContent='Change password';form.append(title);
const fields={};for(const [name,label] of [['current_password','Current password'],['new_password','New password (12+ characters)']]){const l=document.createElement('label');l.textContent=label;const input=document.createElement('input');input.type='password';input.required=true;input.maxLength=128;input.autocomplete=name==='new_password'?'new-password':'current-password';if(name==='new_password')input.minLength=12;input.style.cssText='display:block;width:100%;padding:10px;margin:6px 0 14px';l.append(input);form.append(l);fields[name]=input;}
const save=document.createElement('button');save.textContent='Change password';save.className='secondary';form.append(save);form.onsubmit=async e=>{e.preventDefault();try{save.disabled=true;await call('/auth/password',{current_password:fields.current_password.value,new_password:fields.new_password.value});location.reload()}catch(e){status.textContent=e.message;save.disabled=false}};
action('Create Apple Health device key',async()=>{const d=await call('/auth/device-token');status.textContent='Copy into the iPhone companion access-key field. Valid 90 days; replaces your previous device key: '+d.token;status.style.overflowWrap='anywhere';});
const old=document.getElementById('appKey');if(old)old.closest('.card').hidden=true;
})();</script>'''
    return html.replace('<head>','<head>'+prefix,1).replace('</body>',suffix+'</body>',1)
