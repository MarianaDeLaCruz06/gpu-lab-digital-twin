"""Closed vocabularies for the node aggregate (ARCHITECTURE §5.1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NodeState(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    DRAINING = "DRAINING"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class ConnectivityStatus(StrEnum):
    """Derived freshness signal; deliberately separate from NodeState."""

    UNKNOWN = "UNKNOWN"
    ONLINE = "ONLINE"
    SILENT = "SILENT"
    CONNECTIVITY_UNSTABLE = "CONNECTIVITY_UNSTABLE"


class DriverHealth(StrEnum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class ReasonCode(StrEnum):
    """Active safety reasons; each doubles as the rule ID that activated it."""

    SILENT = "ERR_SILENT"
    RECOVERY_PENDING = "RECOVERY_PENDING"
    DRIVER_UNHEALTHY = "ERR_DRIVER_UNHEALTHY"
    DRIVER_HEALTH_UNKNOWN = "ERR_DRIVER_HEALTH_UNKNOWN"


DEGRADATION_REASONS = frozenset({ReasonCode.DRIVER_UNHEALTHY, ReasonCode.DRIVER_HEALTH_UNKNOWN})

RULE_HEALTHY = "HEALTHY_CURRENT_HEARTBEAT"
RULE_UNKNOWN = "UNKNOWN_NO_ACCEPTED_HEARTBEAT"


@dataclass(frozen=True, slots=True)
class NodeFacts:
    """The immutable fact set one reducer invocation evaluates."""

    has_current_heartbeat: bool
    reasons: frozenset[ReasonCode] = frozenset()


@dataclass(frozen=True, slots=True)
class Decision:
    state: NodeState
    cordoned: bool
    reason_codes: tuple[ReasonCode, ...]
    rule_ids: tuple[str, ...]


def evaluate(facts: NodeFacts) -> Decision:
    """Select exactly one state by the fixed precedence of AD-4.

    Full order: DRAINING > MAINTENANCE > OFFLINE > RECOVERING > DEGRADED > HEALTHY > UNKNOWN.
    Maintenance branches are added by the stories that own them (Epic 3).
    Lower-precedence reasons stay in ``reason_codes``; they never launch a competing transition.
    """
    reasons = tuple(sorted(facts.reasons))
    degradations = tuple(reason for reason in reasons if reason in DEGRADATION_REASONS)

    if ReasonCode.SILENT in facts.reasons:
        state, rule_ids = NodeState.OFFLINE, (ReasonCode.SILENT.value,)
    elif ReasonCode.RECOVERY_PENDING in facts.reasons:
        state, rule_ids = NodeState.RECOVERING, (ReasonCode.RECOVERY_PENDING.value,)
    elif degradations:
        state, rule_ids = NodeState.DEGRADED, tuple(reason.value for reason in degradations)
    elif facts.has_current_heartbeat:
        state, rule_ids = NodeState.HEALTHY, (RULE_HEALTHY,)
    else:
        state, rule_ids = NodeState.UNKNOWN, (RULE_UNKNOWN,)

    cordoned = state is not NodeState.HEALTHY or bool(reasons)
    return Decision(state=state, cordoned=cordoned, reason_codes=reasons, rule_ids=rule_ids)
