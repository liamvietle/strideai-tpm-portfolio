from confidence_engine import RunnerSignals, generate_decision


def run_test(name, signals, expected):
    decision = generate_decision(signals)

    passed = decision.recommendation == expected

    status = "PASS" if passed else "FAIL"

    print(f"{status}: {name}")
    print(f"  Expected: {expected}")
    print(f"  Actual:   {decision.recommendation}")
    print()

    return passed


tests = [
    (
        "Normal training",
        RunnerSignals(
            performance="normal",
            recovery="normal",
            training_load="normal",
            weather="normal",
            confidence=0.90,
            data_completeness=1.0,
        ),
        "Continue current training plan",
    ),

    (
        "Elevated fatigue",
        RunnerSignals(
            performance="poor",
            recovery="poor",
            training_load="high",
            weather="normal",
            confidence=0.90,
            data_completeness=1.0,
        ),
        "Reduce intensity of next hard workout",
    ),

    (
        "Elevated fatigue + hot weather",
        RunnerSignals(
            performance="poor",
            recovery="poor",
            training_load="high",
            weather="hot",
            confidence=0.90,
            data_completeness=1.0,
        ),
        "Reduce intensity and volume of next hard workout",
    ),

    (
        "Insufficient data",
        RunnerSignals(
            performance="normal",
            recovery="normal",
            training_load="normal",
            weather="normal",
            confidence=0.90,
            data_completeness=0.50,
        ),
        "No automatic change",
    ),

    (
        "Extreme fatigue",
        RunnerSignals(
            performance="very_poor",
            recovery="very_poor",
            training_load="high",
            weather="normal",
            confidence=0.70,
            data_completeness=1.0,
        ),
        "Cancel next workout",
    ),
]


passed = 0

for name, signals, expected in tests:
    if run_test(name, signals, expected):
        passed += 1


print("=" * 30)
print(f"Tests passed: {passed}/{len(tests)}")
