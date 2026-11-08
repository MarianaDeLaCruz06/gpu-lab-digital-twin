from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from gpu_lab_twin.domain.connectivity_policy import ConnectivityObservation
from gpu_lab_twin.domain.errors import ErrorCode
from gpu_lab_twin.domain.node_state import ConnectivityStatus, NodeState

ConnectivityOutcome = Literal["HELD_POLICY_UNRESOLVED", "DUPLICATE"]


@dataclass(frozen=True, slots=True)
class ConnectivityResult:
    event_id: UUID
    node_id: str
    outcome: ConnectivityOutcome
    node_revision: int
    state: NodeState
    cordoned: bool
    connectivity_status: ConnectivityStatus
    accepted_at: datetime
    observation: ConnectivityObservation
    reason_code: ErrorCode
    policy_id: str
    explanation: Mapping[str, Any]

    def as_document(self) -> dict[str, Any]:
        return {
            "eventId": str(self.event_id),
            "nodeId": self.node_id,
            "outcome": self.outcome,
            "nodeRevision": self.node_revision,
            "state": self.state.value,
            "cordoned": self.cordoned,
            "connectivityStatus": self.connectivity_status.value,
            "acceptedAt": self.accepted_at.isoformat(),
            "observation": self.observation.value,
            "reasonCode": self.reason_code.value,
            "policyId": self.policy_id,
            "explanation": dict(self.explanation),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, outcome: ConnectivityOutcome) -> ConnectivityResult:
        return cls(
            event_id=UUID(document["eventId"]),
            node_id=document["nodeId"],
            outcome=outcome,
            node_revision=document["nodeRevision"],
            state=NodeState(document["state"]),
            cordoned=document["cordoned"],
            connectivity_status=ConnectivityStatus(document["connectivityStatus"]),
            accepted_at=datetime.fromisoformat(document["acceptedAt"]),
            observation=ConnectivityObservation(document["observation"]),
            reason_code=ErrorCode(document["reasonCode"]),
            policy_id=document["policyId"],
            explanation=document["explanation"],
        )


class ConnectivityPort(Protocol):
    def observe(
        self,
        node_id: str,
        *,
        event_id: UUID,
        status: ConnectivityObservation | str,
        observed_at: datetime,
    ) -> ConnectivityResult: ...
