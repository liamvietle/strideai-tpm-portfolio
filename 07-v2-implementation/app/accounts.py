"""Opt-in account sessions. Athlete identity comes from server-side sessions."""
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from app.storage import connect

router = APIRouter(prefix='/auth')
COOKIE = 'strideai_session'
PUBLIC = {'/health', '/privacy', '/', '/app/api/strava/callback', '/login', '/auth/status', '/auth/login', '/auth/register', '/auth/bootstrap'}
BODY_IDENTITY = {'/app/api/recommendations', '/app/api/apple-health/sync', '/v2/recommendations', '/v3/recommendations', '/v5/recommendations'}


def enabled():
    return os.getenv('STRIDEAI_ACCOUNT_AUTH', 'false').lower() == 'true'


def init_accounts():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS accounts (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, athlete_id TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, owner INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS account_sessions (token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, csrf TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS account_invites (token_hash TEXT PRIMARY KEY, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS account_devices (token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS account_attempts (bucket TEXT PRIMARY KEY, attempts INTEGER NOT NULL, expires REAL NOT NULL);
        ''')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    result = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=3, maxmem=64*1024*1024)
    return salt + ':' + result.hex()


def verify(password, stored):
    return hmac.compare_digest(password_hash(password, stored.split(':')[0]), stored)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r'^[A-Za-z0-9_.-]+$')
    password: str = Field(min_length=12, max_length=128)
    @field_validator('username')
    @classmethod
    def normalize(cls, value):
        return value.lower()


class Registration(Credentials):
    invite: str = Field('', max_length=256)
    setup_key: str = Field('', max_length=256)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


def require_mode():
    if not enabled():
        raise HTTPException(404, 'Account login is not enabled.')
    init_accounts()


def throttle(request, username):
    now = time.time()
    # Both account and source-address limits; no passwords or raw usernames in this table.
    buckets = [(digest('user:'+username), 10), (digest('ip:'+(request.client.host if request.client else 'unknown')), 100)]
    blocked = False
    with connect() as c:
        c.execute('DELETE FROM account_attempts WHERE expires<?', (now,))
        for bucket, limit in buckets:
            c.execute('INSERT INTO account_attempts VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET attempts=attempts+1', (bucket, now+900))
            count = c.execute('SELECT attempts FROM account_attempts WHERE bucket=?', (bucket,)).fetchone()[0]
            blocked |= count > limit
    if blocked:
        raise HTTPException(429, 'Too many attempts. Try again in 15 minutes.')


def session_response(account):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with connect() as c:
        c.execute('DELETE FROM account_sessions WHERE expires<?', (time.time(),))
        c.execute('INSERT INTO account_sessions VALUES(?,?,?,?)', (digest(token), account['id'], csrf, time.time()+7*86400))
    response = JSONResponse({'username': account['username'], 'csrf': csrf})
    response.set_cookie(COOKIE, token, httponly=True, secure=os.getenv('STRIDEAI_COOKIE_SECURE','true').lower()!='false', samesite='lax', max_age=7*86400, path='/')
    response.headers['Cache-Control'] = 'no-store'
    return response


def account_session(request):
    token = request.cookies.get(COOKIE, '')
    with connect() as c:
        row = c.execute('SELECT a.*,s.csrf FROM account_sessions s JOIN accounts a ON a.id=s.account_id WHERE s.token_hash=? AND s.expires>?', (digest(token),time.time())).fetchone()
    return dict(row) if row else None


@router.get('/status')
def auth_status():
    require_mode()
    with connect() as c:
        exists = c.execute('SELECT 1 FROM accounts LIMIT 1').fetchone()
    return {'initialized': bool(exists)}


@router.post('/bootstrap')
def bootstrap(payload: Registration, request: Request):
    require_mode(); throttle(request, payload.username)
    setup_key = os.getenv('STRIDEAI_APP_KEY','').strip()
    if not setup_key or not hmac.compare_digest(payload.setup_key,setup_key):
        raise HTTPException(403,'Invalid setup credentials.')
    hashed = password_hash(payload.password)
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM accounts LIMIT 1').fetchone():
            raise HTTPException(409,'Owner account already exists. Sign in instead.')
        account = {'id':secrets.token_hex(16), 'username':payload.username}
        c.execute('INSERT INTO accounts VALUES(?,?,?,?,1)', (account['id'], payload.username, 'viet', hashed))
    return session_response(account)


@router.post('/register')
def register(payload: Registration, request: Request):
    require_mode(); throttle(request,payload.username)
    hashed = password_hash(payload.password)
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        invite = c.execute('SELECT 1 FROM account_invites WHERE token_hash=? AND expires>?', (digest(payload.invite),time.time())).fetchone()
        if not invite:
            raise HTTPException(403,'A valid unused invitation is required.')
        if c.execute('SELECT 1 FROM accounts WHERE username=?', (payload.username,)).fetchone():
            raise HTTPException(409,'Choose a different username.')
        account = {'id':secrets.token_hex(16), 'username':payload.username}
        c.execute('INSERT INTO accounts VALUES(?,?,?,?,0)', (account['id'], payload.username, 'athlete_'+secrets.token_hex(16), hashed))
        c.execute('DELETE FROM account_invites WHERE token_hash=?', (digest(payload.invite),))
    return session_response(account)


@router.post('/login')
def login(payload: Credentials, request: Request):
    require_mode(); throttle(request,payload.username)
    with connect() as c:
        row = c.execute('SELECT * FROM accounts WHERE username=?', (payload.username,)).fetchone()
    stored = row['password_hash'] if row else '00'*16+':'+'00'*64
    if not verify(payload.password,stored) or not row:
        raise HTTPException(401,'Username or password is incorrect.')
    return session_response(dict(row))


@router.get('/me')
def me(request: Request):
    a = request.state.account
    return {'username':a['username'], 'owner':bool(a['owner']), 'csrf':a['csrf']}


@router.post('/logout')
def logout(request: Request):
    with connect() as c:
        c.execute('DELETE FROM account_sessions WHERE token_hash=?',(digest(request.cookies.get(COOKIE,'')),))
    response = JSONResponse({'signed_out':True});response.delete_cookie(COOKIE,path='/')
    return response


@router.post('/password')
def change_password(payload: PasswordChange, request: Request):
    a = request.state.account
    throttle(request,a['username'])
    if not verify(payload.current_password,a['password_hash']):
        raise HTTPException(403,'Current password is incorrect.')
    hashed = password_hash(payload.new_password)
    with connect() as c:
        c.execute('UPDATE accounts SET password_hash=? WHERE id=?',(hashed,a['id']))
        c.execute('DELETE FROM account_sessions WHERE account_id=?',(a['id'],))
        c.execute('DELETE FROM account_devices WHERE account_id=?',(a['id'],))
    return session_response(a)


@router.post('/invitations')
def invite(request: Request):
    if not request.state.account['owner']:
        raise HTTPException(403,'Only the owner can invite users.')
    token = secrets.token_urlsafe(32)
    with connect() as c:
        c.execute('DELETE FROM account_invites WHERE expires<?',(time.time(),))
        c.execute('INSERT INTO account_invites VALUES(?,?)',(digest(token),time.time()+86400))
    return {'invitation':token,'expires_in_hours':24}


@router.post('/device-token')
def device_token(request: Request):
    a=request.state.account;token=secrets.token_urlsafe(32)
    with connect() as c:
        c.execute('DELETE FROM account_devices WHERE account_id=?',(a['id'],))
        c.execute('INSERT INTO account_devices VALUES(?,?,?)',(digest(token),a['id'],time.time()+90*86400))
    return {'token':token,'scope':'Apple Health sync only','expires_in_days':90}


async def protect(request, call_next):
    """Only invoked in account mode; never accept a client-chosen athlete identity."""
    init_accounts()
    path=request.url.path.rstrip('/') or '/'
    if request.method not in {'GET','HEAD','OPTIONS'} and request.headers.get('Origin'):
        origin=urlsplit(request.headers['Origin'])
        if origin.netloc != request.url.netloc or origin.scheme != request.url.scheme:
            return JSONResponse({'detail':'Cross-origin request rejected.'},status_code=403)
    if path in PUBLIC:
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        return response
    a=account_session(request)
    device=False
    if not a and path=='/app/api/apple-health/sync' and request.method=='POST':
        token=request.headers.get('X-StrideAI-Key','')
        with connect() as c:
            row=c.execute('SELECT a.* FROM account_devices d JOIN accounts a ON a.id=d.account_id WHERE d.token_hash=? AND d.expires>?',(digest(token),time.time())).fetchone()
        if row:a=dict(row);device=True
    if not a:
        return RedirectResponse('/login',status_code=303) if path=='/app' else JSONResponse({'detail':'Sign in to continue.'},status_code=401)
    request.state.account=a
    if request.method not in {'GET','HEAD','OPTIONS'} and not device:
        if not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),a['csrf']):
            return JSONResponse({'detail':'Refresh the page and try again.'},status_code=403)
    # Identity is injected centrally for every existing query-based API, including metrics.
    pairs=[(k,v) for k,v in parse_qsl(request.scope['query_string'].decode()) if k!='athlete_id']
    pairs.append(('athlete_id',a['athlete_id']))
    request.scope['query_string']=urlencode(pairs).encode()
    if path in BODY_IDENTITY and request.method=='POST':
        try:
            body=await request.json()
            if not isinstance(body,dict):raise ValueError()
            body['athlete_id']=a['athlete_id']
            # BaseHTTPMiddleware forwards its cached request body to FastAPI.
            request._body=json.dumps(body).encode()
        except (ValueError,UnicodeDecodeError):
            return JSONResponse({'detail':'Expected a JSON object.'},status_code=422)
    match=re.fullmatch(r'/v3/recommendations/([^/]+)/outcome',path)
    if match:
        try:
            recommendation_id=int(match[1])
        except ValueError:
            return JSONResponse({'detail':'Recommendation not found.'},status_code=404)
        with connect() as c:
            owned=c.execute('SELECT 1 FROM recommendations WHERE id=? AND athlete_id=?',(recommendation_id,a['athlete_id'])).fetchone()
        if not owned:return JSONResponse({'detail':'Recommendation not found.'},status_code=404)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    return response
