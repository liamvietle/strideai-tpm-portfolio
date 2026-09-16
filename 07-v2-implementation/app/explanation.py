from __future__ import annotations

import os
import time
import uuid
from typing import Any, Protocol

import httpx

from app.models import (
    CoachingRecommendation,
    EvidencePackage,
    ExplanationTrace,
    RecommendationAction,
    RetrievedCase,
    WorkoutInput,
)

PROMPT_VERSION = "v2-m2.0"
DEFAULT_MODEL = "gpt-5.6-luna"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...


ACTION_TEXT = {
    RecommendationAction.maintain: "Keep the planned workout unchanged.",
    RecommendationAction.reduce_volume: "Reduce the planned workout volume.",
    RecommendationAction.reduce_intensity: "Reduce the planned workout intensity.",
    RecommendationAction.recovery_only: "Replace the planned workout with recovery only.",
    RecommendationAction.no_change_due_to_missing_data: "Do not automatically change the plan because key data is missing.",
}


def build_evidence_package(
    workout: WorkoutInput,
    recommendation: CoachingRecommendation,
    retrieved_context: list[RetrievedCase],
) -> EvidencePackage:
    return EvidencePackage(
        athlete_id=workout.athlete_id,
        planned_intensity=workout.planned_intensity,
        approved_action=recommendation.action,
        volume_change_pct=recommendation.volume_change_pct,
        fatigue_state=recommendation.fatigue_state,
        risk_level=recommendation.risk_level,
        confidence=recommendation.confidence,
        autonomy_mode=recommendation.autonomy_mode,
        factor_details=[factor.detail for factor in recommendation.decision_factors],
        safety_flags=recommendation.safety_flags,
        retrieved_context=retrieved_context,
    )


def fallback_explanation(evidence: EvidencePackage) -> str:
    action = evidence.approved_action.value
    action_text = ACTION_TEXT[evidence.approved_action]
    factors = "; ".join(evidence.factor_details[:4]) or "No material fatigue signal was detected."
    context = ""
    if evidence.retrieved_context:
        outcomes = "; ".join(case.outcome for case in evidence.retrieved_context[:2])
        context = f" Similar historical outcomes: {outcomes}"
    return (
        f"Approved action: {action}. {action_text} "
        f"Key evidence: {factors}.{context}"
    )


def _build_prompt(evidence: EvidencePackage) -> str:
    context_lines = [
        f"- {case.session_date}: factors={','.join(case.factor_codes)}; outcome={case.outcome}"
        for case in evidence.retrieved_context
    ]
    context_text = "\n".join(context_lines) if context_lines else "- No similar historical case retrieved."

    return f"""You are the explanation layer for StrideAI.

The coaching action below has already been approved by deterministic safety logic.
You must explain it. You must not replace it, soften it into a different action, or recommend a different workout.

Start your response with exactly:
Approved action: {evidence.approved_action.value}.

Approved decision:
- action: {evidence.approved_action.value}
- volume_change_pct: {evidence.volume_change_pct}
- fatigue_state: {evidence.fatigue_state.value}
- risk_level: {evidence.risk_level.value}
- confidence: {evidence.confidence:.2f}
- autonomy_mode: {evidence.autonomy_mode.value}
- safety_flags: {", ".join(evidence.safety_flags) or "none"}

Current evidence:
{chr(10).join("- " + item for item in evidence.factor_details) if evidence.factor_details else "- No material fatigue signal detected."}

Retrieved historical context:
{context_text}

Write 2-4 concise sentences for the athlete. Use only the evidence above. Do not invent medical claims or new training metrics."""


def validate_explanation(text: str, approved_action: RecommendationAction) -> bool:
    expected_prefix = f"approved action: {approved_action.value}."
    normalized = text.strip().lower()
    if not normalized.startswith(expected_prefix):
        return False

    first_sentence = normalized.split(".", 1)[0] + "."
    return first_sentence == expected_prefix


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    pieces: list[str] = []
    for item in payload.get("output") or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                pieces.append(content["text"])
    return "\n".join(pieces).strip()


def _extract_usage(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = payload.get("usage") or {}
    return usage.get("input_tokens"), usage.get("output_tokens")


def _estimate_cost(input_tokens: int | None, output_tokens: int | None) -> float | None:
    input_rate = os.getenv("OPENAI_INPUT_COST_PER_MTOK")
    output_rate = os.getenv("OPENAI_OUTPUT_COST_PER_MTOK")
    if input_tokens is None or output_tokens is None or input_rate is None or output_rate is None:
        return None
    return round(
        input_tokens / 1_000_000 * float(input_rate)
        + output_tokens / 1_000_000 * float(output_rate),
        8,
    )


def generate_explanation(
    evidence: EvidencePackage,
    *,
    api_key: str | None = None,
    model: str | None = None,
    client: HttpClient | None = None,
) -> tuple[str, ExplanationTrace]:
    request_id = str(uuid.uuid4())
    selected_model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    key = api_key or os.getenv("OPENAI_API_KEY")

    if not key:
        text = fallback_explanation(evidence)
        trace = ExplanationTrace(
            request_id=request_id,
            provider="deterministic_fallback",
            model="none",
            prompt_version=PROMPT_VERSION,
            latency_ms=0,
            retrieval_count=len(evidence.retrieved_context),
            guardrail_passed=True,
            used_fallback=True,
        )
        return text, trace

    owned_client = client is None
    http_client = client or httpx.Client(timeout=15.0)
    start = time.perf_counter()

    try:
        response = http_client.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": selected_model,
                "instructions": (
                    "Explain only the approved StrideAI coaching action. "
                    "Never modify the structured decision."
                ),
                "input": _build_prompt(evidence),
                "text": {"verbosity": "low"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        text = _extract_output_text(payload)
        passed = validate_explanation(text, evidence.approved_action)
        input_tokens, output_tokens = _extract_usage(payload)
        latency_ms = int((time.perf_counter() - start) * 1000)

        if not passed:
            text = fallback_explanation(evidence)

        trace = ExplanationTrace(
            request_id=request_id,
            provider="openai",
            model=selected_model,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            retrieval_count=len(evidence.retrieved_context),
            guardrail_passed=passed,
            used_fallback=not passed,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=_estimate_cost(input_tokens, output_tokens),
        )
        return text, trace
    except Exception:
        latency_ms = int((time.perf_counter() - start) * 1000)
        text = fallback_explanation(evidence)
        trace = ExplanationTrace(
            request_id=request_id,
            provider="openai",
            model=selected_model,
            prompt_version=PROMPT_VERSION,
            latency_ms=latency_ms,
            retrieval_count=len(evidence.retrieved_context),
            guardrail_passed=False,
            used_fallback=True,
        )
        return text, trace
    finally:
        if owned_client and hasattr(http_client, "close"):
            http_client.close()
