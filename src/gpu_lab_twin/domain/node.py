"""Read models of the node aggregate."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from gpu_lab_twin.domain.fleet import NodeKind
from gpu_lab_twin.domain.node_state import ConnectivityStatus, NodeState


@dataclass(frozen=True, slots=True)
class NodeSnapshot:
    node_id: str
    kind: NodeKind
    state: NodeState
    cordoned: bool
    connectivity: ConnectivityStatus
    revision: int
    evidence_epoch: int
    current_boot_session_id: str | None
    heartbeat_interval_ms: int
    last_accepted_event_at: datetime | None
    last_accepted_receive_at: datetime | None
    active_reason_codes: tuple[str, ...]
    # Evidence IDs that last observed each active reason (taken from its open alert episode).
    reason_evidence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    # observedValues recorded by each active reason's open alert (the facts that last activated it).
    reason_observations: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    # eventId of the heartbeat behind the current telemetry snapshot, if any.
    current_heartbeat_event_id: str | None = None
    current_source_sequence: int | None = None


@dataclass(frozen=True, slots=True)
class GpuReading:
    """Configured GPU plus its last accepted sample; ``None`` means no sample yet, never zero."""

    gpu_device_id: str
    vram_capacity_gb: float
    temperature_c: float | None
    vram_occupied_gb: float | None


@dataclass(frozen=True, slots=True)
class NodeView:
    snapshot: NodeSnapshot
    storage_capacity_gb: float
    storage_free_gb: float | None
    gpus: tuple[GpuReading, ...]
