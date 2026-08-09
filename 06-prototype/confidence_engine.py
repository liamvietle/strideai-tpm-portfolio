from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class RunnerSignals:
    performance: str
    recovery: str
    training_load: str
    weather: str
    confidence: float
    data_completeness: float


@dataclass
class CoachingDecision:
    fatigue_state: str
    recommendation: str
    confidence_level: str
    automation: str
    safety: str
    reasons: list[str]


def classify_fatigue(signals: RunnerSignals) -> tuple[str, list[str]]:
    reasons = []

    if signals.data_completeness < 0.70:
        return "UNKNOWN", ["insufficient data"]

    extreme_signals = 0
    elevated_signals = 0

    if signals.recovery == "poor":
        elevated_signals += 1
        reasons.append("poor recovery")

    if signals.training_load == "high":
        elevated_signals += 1
        reasons.append("high training load")

    if signals.performance == "poor":
        elevated_signals += 1
        reasons.append("poor recent performance")

    if signals.recovery == "very_poor":
        extreme_signals += 1
        reasons.append("very poor recovery")

    if signals.performance == "very_poor":
        extreme_signals += 1
        reasons.append("very poor recent performance")

    if extreme_signals >= 2:
        return "EXTREME", reasons

    if elevated_signals >= 2:
        return "ELEVATED", reasons

    return "NORMAL", reasons


def classify_confidence(confidence: float) -> str:
    if confidence >= 0.80:
        return "HIGH"

    if confidence >= 0.60:
        return "MEDIUM"

    return "LOW"


def generate_decision(signals: RunnerSignals) -> CoachingDecision:
    fatigue_state, fatigue_reasons = classify_fatigue(signals)

    reasons = list(fatigue_reasons)

    # Insufficient data
    if signals.data_completeness < 0.70:
        return CoachingDecision(
            fatigue_state="UNKNOWN",
            recommendation="No automatic change",
            confidence_level="LOW",
            automation="NONE",
            safety="PASSED",
            reasons=["insufficient data"]
        )

    confidence_level = classify_confidence(signals.confidence)

    # Safety-critical condition
    if fatigue_state == "EXTREME":
        return CoachingDecision(
            fatigue_state=fatigue_state,
            recommendation="Cancel next workout",
            confidence_level=confidence_level,
            automation="MANDATORY SAFETY ACTION",
            safety="SAFETY ACTION TRIGGERED",
            reasons=reasons
        )

    recommendation = "Continue current training plan"

    if fatigue_state == "ELEVATED":
        recommendation = "Reduce intensity of next hard workout"

    if signals.weather == "hot":
        recommendation = "Reduce volume of next run"
        reasons.append("hot weather")

    if fatigue_state == "ELEVATED" and signals.weather == "hot":
        recommendation = "Reduce intensity and volume of next hard workout"

    if confidence_level == "HIGH":
        automation = "AUTOMATIC"
    elif confidence_level == "MEDIUM":
        automation = "USER CONFIRMATION"
    else:
        automation = "NONE"
        recommendation = "No automatic change"

    return CoachingDecision(
        fatigue_state=fatigue_state,
        recommendation=recommendation,
        confidence_level=confidence_level,
        automation=automation,
        safety="PASSED",
        reasons=reasons
    )


def run_example():
    signals = RunnerSignals(
        performance="poor",
        recovery="poor",
        training_load="high",
        weather="hot",
        confidence=0.86,
        data_completeness=1.0
    )

    decision = generate_decision(signals)

    print("StrideAI Coaching Decision")
    print("=" * 30)

    for key, value in asdict(decision).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    run_example()
