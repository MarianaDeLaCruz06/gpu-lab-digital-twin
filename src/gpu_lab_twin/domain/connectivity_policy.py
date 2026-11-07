"""Canonical AD-5 connectivity containment while ODD-5 is unresolved."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from gpu_lab_twin.domain.errors import ErrorCode

ODD5_POLICY_ID = "ODD-5"


class ConnectivityObservation(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


@dataclass(frozen=True, slots=True)
class ConnectivityPolicyDecision:
    reason_code: ErrorCode
    policy_id: str


def evaluate_connectivity(_observation: ConnectivityObservation) -> ConnectivityPolicyDecision:
    """Hold the stable public projection; ODD-5 has no approved classifier or numeric threshold."""
    return ConnectivityPolicyDecision(reason_code=ErrorCode.ERR_POLICY_UNRESOLVED, policy_id=ODD5_POLICY_ID)
