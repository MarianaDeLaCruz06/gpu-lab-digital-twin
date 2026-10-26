from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gpu_lab_twin.domain.node_state import (
    DEGRADATION_REASONS,
    RULE_HEALTHY,
    RULE_UNKNOWN,
    NodeFacts,
    NodeState,
    ReasonCode,
    evaluate,
)


def test_no_heartbeat_is_unknown_and_cordoned() -> None:
    decision = evaluate(NodeFacts(has_current_heartbeat=False))
    assert (decision.state, decision.cordoned, decision.rule_ids) == (NodeState.UNKNOWN, True, (RULE_UNKNOWN,))


def test_current_heartbeat_without_reason_is_healthy_and_eligible() -> None:
    decision = evaluate(NodeFacts(has_current_heartbeat=True))
    assert (decision.state, decision.cordoned, decision.rule_ids) == (NodeState.HEALTHY, False, (RULE_HEALTHY,))


@pytest.mark.parametrize("reason", [ReasonCode.DRIVER_UNHEALTHY, ReasonCode.DRIVER_HEALTH_UNKNOWN])
def test_driver_reason_degrades_and_cordons_citing_the_reason(reason: ReasonCode) -> None:
    decision = evaluate(NodeFacts(has_current_heartbeat=True, reasons=frozenset({reason})))
    assert decision.state is NodeState.DEGRADED
    assert decision.cordoned is True
    assert decision.rule_ids == (reason.value,)
    assert decision.reason_codes == (reason,)


reason_sets = st.frozensets(st.sampled_from(list(ReasonCode)))


@given(has_heartbeat=st.booleans(), reasons=reason_sets)
def test_state_follows_fixed_precedence_and_non_healthy_is_cordoned(
    has_heartbeat: bool, reasons: frozenset[ReasonCode]
) -> None:
    decision = evaluate(NodeFacts(has_current_heartbeat=has_heartbeat, reasons=reasons))

    degradations = reasons & DEGRADATION_REASONS
    if degradations:
        expected_state, expected_rules = NodeState.DEGRADED, tuple(sorted(degradations))
    elif has_heartbeat:
        expected_state, expected_rules = NodeState.HEALTHY, (RULE_HEALTHY,)
    else:
        expected_state, expected_rules = NodeState.UNKNOWN, (RULE_UNKNOWN,)

    assert (decision.state, decision.rule_ids) == (expected_state, expected_rules)
    assert decision.reason_codes == tuple(sorted(reasons))
    assert decision.cordoned is (decision.state is not NodeState.HEALTHY)
