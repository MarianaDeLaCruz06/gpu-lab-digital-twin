from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.domain.heartbeat import HeartbeatPayload
from gpu_lab_twin.domain.node import NodeSnapshot, NodeView
from gpu_lab_twin.domain.node_state import ConnectivityStatus, NodeState


@dataclass(frozen=True, slots=True)
class RecordedHeartbeat:
    node_id: str
    payload_hash: str
    response: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ProjectionUpdate:
    """New aggregate values, written only if the stored revision still equals ``expected_revision``."""

    node_id: str
    expected_revision: int
    state: NodeState
    cordoned: bool
    connectivity: ConnectivityStatus
    active_reason_codes: tuple[str, ...]
    current_boot_session_id: str | None
    last_accepted_event_at: datetime | None
    last_accepted_receive_at: datetime | None
    evidence_epoch: int | None = None


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    source_event_id: UUID
    prior_state: NodeState
    result_state: NodeState
    prior_cordoned: bool
    result_cordoned: bool
    rule_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    explanation: Mapping[str, Any]
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class AuditRecord:
    event_id: UUID
    event_type: str
    rule_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    body: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class HeartbeatCommit:
    """Everything one accepted heartbeat changes, committed as a single unit of work (AD-1)."""

    projection: ProjectionUpdate
    payload: HeartbeatPayload
    payload_hash: str
    evidence_epoch: int
    explanation: Mapping[str, Any]
    transition: TransitionRecord | None
    alert_reasons: tuple[str, ...]
    audit: AuditRecord
    at: datetime
    disposition: str = "APPLIED"
    closed_alert_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class IgnoredHeartbeatCommit:
    """One ordered stale-heartbeat record with no projection effects."""

    node_id: str
    payload: HeartbeatPayload
    payload_hash: str
    evidence_epoch: int
    explanation: Mapping[str, Any]
    result: Mapping[str, Any]
    at: datetime


@dataclass(frozen=True, slots=True)
class TransitionCommit:
    """A reducer decision triggered by something other than a heartbeat (e.g. a clock evaluation)."""

    projection: ProjectionUpdate
    transition: TransitionRecord
    explanation: Mapping[str, Any]
    alert_reasons: tuple[str, ...]
    audit: AuditRecord
    at: datetime


class NodeRepository(Protocol):
    """Persistence for the node aggregates of one simulation run."""

    def seed_inventory(self, inventory: FleetInventory) -> int:
        """Insert configured nodes/GPUs that are not yet stored; return how many nodes were added."""
        ...

    def count_nodes(self) -> int: ...

    def count_gpu_devices(self) -> int: ...

    def get_node(self, node_id: str) -> NodeSnapshot | None: ...

    def find_heartbeat(self, event_id: UUID) -> RecordedHeartbeat | None: ...

    def commit_heartbeat(self, commit: HeartbeatCommit) -> int:
        """Apply atomically and return the new revision.

        Raises ``DomainError(ERR_REVISION_CONFLICT)`` if the revision moved, and leaves nothing written.
        """
        ...

    def commit_ignored_heartbeat(self, commit: IgnoredHeartbeatCommit) -> None:
        """Persist LATE_IGNORED evidence/audit without mutating the projection."""
        ...

    def has_boot_session(self, node_id: str, boot_session_id: str) -> bool: ...

    def commit_transition(self, commit: TransitionCommit) -> int:
        """Apply atomically and return the new revision; ``ERR_REVISION_CONFLICT`` if the revision moved."""
        ...

    def list_fleet(self) -> tuple[NodeView, ...]: ...
