"""Canonical AD-7 maintenance commands and pure drain policy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from gpu_lab_twin.domain.node_state import NodeState


@dataclass(frozen=True, slots=True)
class MaintenanceWindow:
    event_id: UUID
    request_id: UUID
    occurred_at: datetime
    starts_at: datetime
    reason: str
    expected_node_revision: int
    actor: str

    def canonical_hash(self, node_id: str) -> str:
        body = {
            "actor": self.actor,
            "eventId": str(self.event_id),
            "expectedNodeRevision": self.expected_node_revision,
            "nodeId": node_id,
            "occurredAt": self.occurred_at.isoformat(),
            "reason": self.reason,
            "requestId": str(self.request_id),
            "startsAt": self.starts_at.isoformat(),
        }
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class WorkloadSnapshot:
    event_id: UUID
    snapshot_id: UUID
    node_id: str
    source_revision: int
    observed_at: datetime
    received_at: datetime
    active_workload_ids: tuple[str, ...]

    @property
    def active_workload_count(self) -> int:
        return len(self.active_workload_ids)


@dataclass(frozen=True, slots=True)
class MaintenanceResult:
    event_id: UUID
    request_id: UUID
    node_id: str
    outcome: str
    lock_id: UUID
    node_revision: int
    state: NodeState
    cordoned: bool
    active_workload_count: int | None
    active_workload_ids: tuple[str, ...]
    workload_observed_at: datetime | None
    explanation: dict

    def as_document(self) -> dict:
        return {
            "eventId": str(self.event_id), "requestId": str(self.request_id), "nodeId": self.node_id,
            "outcome": self.outcome, "lockId": str(self.lock_id), "nodeRevision": self.node_revision,
            "state": self.state.value, "cordoned": self.cordoned,
            "activeWorkloadCount": self.active_workload_count,
            "activeWorkloadIds": list(self.active_workload_ids),
            "workloadObservedAt": self.workload_observed_at.isoformat() if self.workload_observed_at else None,
            "explanation": self.explanation,
        }


def maintenance_state(*, lock_acquired_at: datetime, snapshot: WorkloadSnapshot | None) -> NodeState:
    if snapshot is None or snapshot.observed_at < lock_acquired_at or snapshot.received_at < lock_acquired_at:
        return NodeState.DRAINING
    return NodeState.MAINTENANCE if snapshot.active_workload_count == 0 else NodeState.DRAINING

