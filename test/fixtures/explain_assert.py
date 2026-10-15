def assert_explanation(explanation: dict, *, observed_key: str, expected_observed: object, threshold_key: str | None = None, expected_threshold: object | None = None, expected_state: str | None = None) -> None:
    assert explanation["ruleIds"], "an automated decision requires at least one rule ID"
    assert explanation["observedValues"][observed_key] == expected_observed
    if threshold_key is not None:
        assert explanation["thresholds"][threshold_key] == expected_threshold
    if expected_state is not None:
        assert explanation["expectedState"] == expected_state
    assert explanation["evidenceIds"]
    assert explanation["summary"].strip()
