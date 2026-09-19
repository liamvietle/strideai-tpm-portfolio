import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import accounts, athlete_store
from app.storage import connect

PASSWORD='example-long-password'


def test_garmin_recovery_account_scope_and_csrf(clients):
    owner, other = clients
    body = {'format':'strideai-garmin-recovery-v1', 'days':[{'date':'2026-09-16','sleep_hours':7}]}
    assert owner.post('/app/api/garmin-recovery/import', json=body, headers={'X-CSRF-Token':''}).status_code == 403
    assert other.post('/app/api/garmin-recovery/import?athlete_id=viet', json=body).status_code == 200
    assert owner.get('/app/api/garmin-recovery/history').json()['days'] == 0
    assert other.get('/app/api/garmin-recovery/history?athlete_id=viet').json()['days'] == 1

@pytest.fixture
def clients(tmp_path, monkeypatch):
    monkeypatch.setenv('STRIDEAI_DB_PATH',str(tmp_path/'account.db'))
    monkeypatch.setenv('STRIDEAI_ACCOUNT_AUTH','true')
    monkeypatch.setenv('STRIDEAI_APP_KEY','test-bootstrap-secret')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with TestClient(app,base_url='https://testserver') as owner, TestClient(app,base_url='https://testserver') as other:
        athlete_store.patch_profile({'age':33},'viet')
        response=owner.post('/auth/bootstrap',json={'username':'owner','password':PASSWORD,'setup_key':'test-bootstrap-secret'})
        assert response.status_code==200,response.text
        assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
        owner.headers['X-CSRF-Token']=response.json()['csrf']
        invite=owner.post('/auth/invitations').json()['invitation']
        response=other.post('/auth/register',json={'username':'runner','password':PASSWORD,'invite':invite})
        assert response.status_code==200,response.text
        other.headers['X-CSRF-Token']=response.json()['csrf']
        yield owner,other


def test_identity_scopes_query_body_and_setup(clients):
    owner,other=clients
    assert owner.get('/app/api/coach/profile').json()['profile']['age']==33
    assert other.get('/app/api/coach/profile?athlete_id=viet').json()['profile']['age'] is None
    assert other.patch('/app/api/coach/profile?athlete_id=viet',json={'age':25}).status_code==200
    assert owner.get('/app/api/coach/profile').json()['profile']['age']==33
    assert other.get('/app/api/coach/profile').json()['profile']['age']==25
    r=other.post('/app/api/recommendations',json={'athlete_id':'viet','checkin_date':'2026-09-18','planned_activity_type':'rest'})
    assert r.status_code==200,r.text
    assert owner.get('/app/api/history').json()==[]
    assert len(other.get('/app/api/history?athlete_id=viet').json())==1
    assert other.post('/auth/invitations').status_code==403
    assert other.post('/auth/bootstrap',json={'username':'thief','password':PASSWORD,'setup_key':'test-bootstrap-secret'}).status_code==409


def test_csrf_logout_password_revocation(clients):
    owner,other=clients
    assert owner.patch('/app/api/coach/profile',headers={'X-CSRF-Token':''},json={'age':99}).status_code==403
    old_session=owner.cookies.get(accounts.COOKIE)
    r=owner.post('/auth/password',json={'current_password':PASSWORD,'new_password':'new-example-password'})
    assert r.status_code==200
    owner.headers['X-CSRF-Token']=r.json()['csrf']
    other.cookies.set(accounts.COOKIE,old_session,domain='testserver.local',path='/')
    assert other.get('/auth/me').status_code==401
    assert owner.post('/auth/logout').status_code==200
    assert owner.get('/app/api/history',headers={'X-StrideAI-Key':'test-bootstrap-secret'}).status_code==401
    assert owner.post('/auth/login',json={'username':'owner','password':PASSWORD}).status_code==401
    assert owner.post('/auth/login',json={'username':'owner','password':'new-example-password'}).status_code==200


def test_outcome_ids_and_device_scope(clients):
    owner,other=clients
    with connect() as c:
        c.execute("INSERT INTO recommendations(id,athlete_id,request_json,recommendation_json) VALUES(123,'viet','{}','{}')")
    for path in ['/v3/recommendations/123/outcome','/v3/recommendations/+123/outcome']:
        assert other.put(path,json={'completed':True}).status_code==404
    token=other.post('/auth/device-token').json()['token']
    other.cookies.clear();other.headers.pop('X-CSRF-Token')
    assert other.get('/app/api/history',headers={'X-StrideAI-Key':token}).status_code==401
    r=other.post('/app/api/apple-health/sync',headers={'X-StrideAI-Key':token},json={'athlete_id':'viet','device_id':'test-device','generated_at':'2026-09-18T01:00:00Z','summaries':[{'date':'2026-09-18','timezone':'Asia/Ho_Chi_Minh','hrv_ms':50}]})
    assert r.status_code==200,r.text
    assert owner.get('/app/api/apple-health/status').json()['days']==0


def test_login_throttle_and_invite_consumption(clients):
    owner,other=clients
    for _ in range(10):
        response=other.post('/auth/login',json={'username':'nobody','password':PASSWORD})
    assert response.status_code==401
    assert other.post('/auth/login',json={'username':'nobody','password':PASSWORD}).status_code==429
    assert other.post('/auth/register',json={'username':'someone','password':PASSWORD,'invite':'invalid'}).status_code==403


def test_plan_ownership_invite_replay_and_origin(clients):
    from datetime import date,timedelta
    owner,other=clients
    goal=owner.put('/app/api/goal',json={'name':'Owner race','race_date':(date.today()+timedelta(days=90)).isoformat(),'goal_minutes':240}).json()
    assert other.get('/app/api/plan?athlete_id=viet').json()['goal'] is None
    assert other.post('/app/api/plan',json={'race_id':goal['id'],'days':[{'date':date.today().isoformat(),'distance_km':5}]}).status_code==409
    invitation=owner.post('/auth/invitations').json()['invitation']
    assert other.post('/auth/register',json={'username':'third','password':PASSWORD,'invite':invitation}).status_code==200
    assert other.post('/auth/register',json={'username':'fourth','password':PASSWORD,'invite':invitation}).status_code==403
    assert owner.post('/auth/login',headers={'Origin':'https://other.example'},json={'username':'owner','password':PASSWORD}).status_code==403
    # Railway terminates TLS and forwards an internal HTTP request.
    proxy_headers={'Origin':'https://stride-ai.app','Host':'stride-ai.app','X-Forwarded-Proto':'https','X-Forwarded-Host':'stride-ai.app'}
    assert owner.post('/auth/login',headers=proxy_headers,json={'username':'owner','password':PASSWORD}).status_code==200
    assert owner.post('/auth/login',headers={**proxy_headers,'Origin':'http://stride-ai.app'},json={'username':'owner','password':PASSWORD}).status_code==403
