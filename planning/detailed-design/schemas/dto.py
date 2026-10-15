"""Solu-2 transport schema stubs only; no production logic."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodeState(str, Enum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    DRAINING = "DRAINING"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class ExplanationDTO(StrictDTO):
    ruleIds: list[str] = Field(min_length=1)
    observedValues: dict[str, Any]
    thresholds: dict[str, Any]
    expectedState: NodeState | None = None
    evidenceIds: list[str] = Field(min_length=1)
    policyVersion: str
    priorState: NodeState
    resultState: NodeState
    summary: str = Field(min_length=1, max_length=1000)


class ErrorBody(StrictDTO):
    code: str
    message: str
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)


class GpuSampleDTO(StrictDTO):
    gpuDeviceId: str = Field(min_length=1, max_length=128)
    temperatureC: float = Field(ge=0)
    vramOccupiedGb: float = Field(ge=0)


class ExternalContextDTO(StrictDTO):
    source: Literal["EXTERNAL_MOCK"]
    sourceRevision: int = Field(ge=0)
    observedAt: datetime
    receivedAt: datetime
    reservationIds: list[str] = Field(default_factory=list)
    activeWorkloadIds: list[str] = Field(default_factory=list)


class IngestHeartbeatRequest(StrictDTO):
    eventId: UUID
    occurredAt: datetime
    receivedAt: datetime
    schemaVersion: Literal["1.0"]
    bootSessionId: str = Field(min_length=1, max_length=128)
    previousBootSessionId: str | None = Field(default=None, min_length=1, max_length=128)
    stateLoss: bool
    sourceSequence: int | None = Field(default=None, ge=0)
    gpuSamples: list[GpuSampleDTO] = Field(min_length=1, max_length=2)
    driverHealth: Literal["HEALTHY", "UNHEALTHY", "UNKNOWN"]
    storageFreeGb: float = Field(ge=0)
    externalContext: ExternalContextDTO | None = None


class IngestHeartbeatResponse(StrictDTO):
    eventId: UUID
    nodeId: str
    outcome: Literal["APPLIED", "DUPLICATE", "LATE_IGNORED", "BOOT_CHANGE_DETECTED"]
    nodeRevision: int = Field(ge=0)
    state: NodeState
    cordoned: bool
    connectivityStatus: Literal["UNKNOWN", "ONLINE", "SILENT", "CONNECTIVITY_UNSTABLE"]
    acceptedAt: datetime
    explanation: ExplanationDTO


class TransitionNodeStateRequest(StrictDTO):
    eventId: UUID
    occurredAt: datetime
    schemaVersion: Literal["1.0"]
    signalType: Literal["HEARTBEAT_ACCEPTED", "CLOCK_EVALUATED", "CONNECTIVITY_OBSERVED", "WORKLOAD_SNAPSHOT_ACCEPTED", "MAINTENANCE_COMMAND_ACCEPTED"]
    evidenceId: str = Field(min_length=1, max_length=128)
    evaluationAt: datetime
    connectivityObservation: Literal["ONLINE", "OFFLINE"] | None = None


class TransitionNodeStateResponse(StrictDTO):
    eventId: UUID
    nodeId: str
    outcome: Literal["TRANSITIONED", "HELD", "DUPLICATE"]
    nodeRevision: int = Field(ge=0)
    priorState: NodeState
    state: NodeState
    cordoned: bool
    connectivityStatus: Literal["UNKNOWN", "ONLINE", "SILENT", "CONNECTIVITY_UNSTABLE"]
    activeReasonCodes: list[str]
    transitioned: bool
    explanation: ExplanationDTO


class ScheduleMaintenanceDrainRequest(StrictDTO):
    eventId: UUID
    requestId: UUID
    occurredAt: datetime
    schemaVersion: Literal["1.0"]
    startsAt: datetime
    reason: str = Field(min_length=1, max_length=500)
    expectedNodeRevision: int = Field(ge=0)
    actor: str = Field(min_length=1, max_length=128)


class ScheduleMaintenanceDrainResponse(StrictDTO):
    eventId: UUID
    requestId: UUID
    nodeId: str
    outcome: Literal["SCHEDULED", "DUPLICATE"]
    lockId: UUID
    nodeRevision: int = Field(ge=0)
    state: Literal[NodeState.DRAINING, NodeState.MAINTENANCE]
    cordoned: Literal[True]
    activeWorkloadCount: int | None = Field(default=None, ge=0)
    activeWorkloadIds: list[str]
    workloadObservedAt: datetime | None = None
    explanation: ExplanationDTO
