from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

from app.storage import list_activities
from app.strava_integration import (
    complete_authorization,
    create_authorization_url,
    strava_status,
    sync_strava_activities,
)
from app.strava_ui import enhance_personal_app


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _configure(monkeypatch, tmp_path):
    monkeypatch.setenv("STRIDEAI_DB_PATH", str(tmp_path / "strideai.db"))
    monkeypatch.setenv("STRAVA_CLIENT_ID", "12345")
    monkeypatch.setenv("STRAVA_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("STRAVA_REDIRECT_URI", "https://example.test/app/api/strava/callback")


def test_authorization_url_uses_required_scopes_and_state(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    url = create_authorization_url("viet")
    parsed = parse_qs(urlparse(url).query)

    assert parsed["client_id"] == ["12345"]
    assert parsed["scope"] == ["read,activity:read_all"]
    assert parsed["redirect_uri"] == ["https://example.test/app/api/strava/callback"]
    assert parsed["state"][0]


def test_oauth_connection_and_activity_sync(monkeypatch, tmp_path):
    _configure(monkeypatch, tmp_path)
    url = create_authorization_url("viet")
    state = parse_qs(urlparse(url).query)["state"][0]

    token_payload = {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "expires_at": int(time.time()) + 3600,
        "athlete": {"id": 99, "firstname": "Viet", "lastname": "Le"},
    }
    monkeypatch.setattr(
        "app.strava_integration.httpx.post",
        lambda *args, **kwargs: FakeResponse(token_payload),
    )
    complete_authorization(code="auth-code", state=state, scope="read,activity:read_all")

    status = strava_status("viet")
    assert status["configured"] is True
    assert status["connected"] is True
    assert status["athlete_name"] == "Viet Le"
    assert status["auto_sync"] is True

    activities = [
        {
            "id": 1001,
            "name": "Morning Run",
            "sport_type": "Run",
            "start_date": "2026-09-15T23:00:00Z",
            "distance": 10000.0,
            "moving_time": 3600,
            "average_heartrate": 142.0,
            "max_heartrate": 158.0,
        },
        {
            "id": 1002,
            "name": "Indoor Run",
            "sport_type": "VirtualRun",
            "start_date": "2026-09-14T23:00:00Z",
            "distance": 6000.0,
            "moving_time": 2400,
            "average_heartrate": 135.0,
            "max_heartrate": 150.0,
        },
        {
            "id": 1003,
            "name": "Ride",
            "sport_type": "Ride",
            "start_date": "2026-09-13T23:00:00Z",
            "distance": 25000.0,
            "moving_time": 4000,
        },
    ]
    monkeypatch.setattr(
        "app.strava_integration.httpx.get",
        lambda *args, **kwargs: FakeResponse(activities),
    )

    summary = sync_strava_activities("viet", max_pages=1)
    assert summary["fetched"] == 3
    assert summary["activities"] == 3
    assert summary["running_activities"] == 2
    assert summary["inserted"] == 3

    stored = list_activities("viet")
    assert len(stored) == 3
    assert {row["source_activity_id"] for row in stored} == {"1001", "1002", "1003"}
    assert {row["activity_type"] for row in stored} == {"Run", "VirtualRun", "Ride"}
    assert all(row["source"] == "strava" for row in stored)


def test_personal_app_injects_strava_and_daily_controls():
    html = '<html><body><section id="data" class="panel"></section></body></html>'
    enhanced = enhance_personal_app(html)
    assert "Strava activity sync" in enhanced
    assert "connectStravaBtn" in enhanced
    assert "/app/api/strava/sync" in enhanced
    assert "Automatic sync" in enhanced or "automatic" in enhanced.lower()
