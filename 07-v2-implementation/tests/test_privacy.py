from fastapi.testclient import TestClient

import app.main as main


def test_privacy_is_public_while_personal_data_stays_protected(monkeypatch):
    monkeypatch.setattr(main, "APP_KEY", "test-only-access-key")
    client = TestClient(main.app)
    response = client.get("/privacy")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "viet@stride-ai.app" in response.text
    assert "Open-Meteo" in response.text
    assert "Apple Health recovery summaries" in response.text
    assert 'href="/privacy"' in client.get("/app").text
    assert client.get("/app/api/history").status_code == 401
    assert client.get("/app/api/strava/status").status_code == 401
    assert client.get("/health").json() == {"status": "ok"}
