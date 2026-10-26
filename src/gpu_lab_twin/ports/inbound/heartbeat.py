from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from gpu_lab_twin.domain.heartbeat import HeartbeatPayload
from gpu_lab_twin.domain.node_state import ConnectivityStatus, NodeState

HeartbeatOutcome = Literal["APPLIED", "DUPLICATE", "LATE_IGNORED", "BOOT_CHANGE_DETECTED"]


@dataclass(frozen=True, slots=True)
class HeartbeatResult:
    event_id: UUID
    node_id: str
    outcome: HeartbeatOutcome
    node_revision: int
    state: NodeState
    cordoned: bool
    connectivity_status: ConnectivityStatus
    accepted_at: datetime
    explanation: Mapping[str, Any]

    def as_document(self) -> dict[str, Any]:
        """The contract IngestHeartbeatResponse shape; also the recorded result replayed on DUPLICATE."""
        return {
            "eventId": str(self.event_id),
            "nodeId": self.node_id,
            "outcome": self.outcome,
            "nodeRevision": self.node_revision,
            "state": self.state.value,
            "cordoned": self.cordoned,
            "connectivityStatus": self.connectivity_status.value,
            "acceptedAt": self.accepted_at.isoformat(),
            "explanation": dict(self.explanation),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any], *, outcome: HeartbeatOutcome) -> HeartbeatResult:
        return cls(
            event_id=UUID(document["eventId"]),
            node_id=document["nodeId"],
            outcome=outcome,
            node_revision=document["nodeRevision"],
            state=NodeState(document["state"]),
            cordoned=document["cordoned"],
            connectivity_status=ConnectivityStatus(document["connectivityStatus"]),
            accepted_at=datetime.fromisoformat(document["acceptedAt"]),
            explanation=document["explanation"],
        )


class HeartbeatPort(Protocol):
    """`ingestHeartbeat(nodeId, payload, at)`; `at` is taken from the injected Clock by the service."""

    def ingest_heartbeat(self, node_id: str, payload: HeartbeatPayload) -> HeartbeatResult: ...
