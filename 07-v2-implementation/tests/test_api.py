from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_v1_endpoint_is_preserved():
    response = client.post(
        "/v1/recommendations",
        json={
            "athlete_id": "test",
            "planned_distance_km": 10,
            "planned_intensity": "easy",
            "recent_load_ratio": 1.05,
            "hrv_vs_baseline_pct": -2,
            "resting_hr_delta_bpm": 1,
            "sleep_hours": 7.5,
            "soreness_0_10": 2,
        },
    )
    assert response.status_code == 200
    assert response.json()["action"] == "maintain"


def test_v2_endpoint_returns_evidence_and_trace(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post(
        "/v2/recommendations",
        json={
            "athlete_id": "viet-demo",
            "planned_distance_km": 16,
            "planned_intensity": "threshold",
            "recent_load_ratio": 1.42,
            "hrv_vs_baseline_pct": -16,
            "resting_hr_delta_bpm": 7,
            "sleep_hours": 5.6,
            "soreness_0_10": 6,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["action"] == body["evidence"]["approved_action"]
    assert body["explanation"].lower().startswith(
        f'approved action: {body["recommendation"]["action"]}.'
    )
    assert "trace" in body
