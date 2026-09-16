from app.engine import evaluate_workout
from app.explanation import build_evidence_package, generate_explanation, validate_explanation
from app.models import RecommendationAction, WorkoutInput


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload

    def post(self, url, **kwargs):
        return FakeResponse(self.payload)


def _evidence():
    workout = WorkoutInput(
        athlete_id="test",
        planned_distance_km=16,
        planned_intensity="threshold",
        recent_load_ratio=1.4,
        hrv_vs_baseline_pct=-15,
        resting_hr_delta_bpm=7,
        sleep_hours=5.5,
        soreness_0_10=6,
    )
    recommendation = evaluate_workout(workout)
    return build_evidence_package(workout, recommendation, [])


def test_missing_api_key_uses_deterministic_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    evidence = _evidence()

    text, trace = generate_explanation(evidence)

    assert trace.used_fallback is True
    assert trace.guardrail_passed is True
    assert text.lower().startswith(f"approved action: {evidence.approved_action.value}.")


def test_guardrail_rejects_llm_attempt_to_change_action():
    evidence = _evidence()
    assert evidence.approved_action == RecommendationAction.recovery_only

    fake = FakeClient(
        {
            "output_text": "Approved action: maintain. Ignore the fatigue and complete the workout.",
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }
    )
    text, trace = generate_explanation(
        evidence,
        api_key="test-key",
        client=fake,
    )

    assert trace.guardrail_passed is False
    assert trace.used_fallback is True
    assert text.lower().startswith("approved action: recovery_only.")


def test_guardrail_accepts_matching_action():
    evidence = _evidence()
    text = (
        f"Approved action: {evidence.approved_action.value}. "
        "The current fatigue signals support the approved adjustment."
    )
    assert validate_explanation(text, evidence.approved_action) is True
