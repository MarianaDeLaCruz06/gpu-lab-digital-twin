"""Transport DTOs. Field names and constraints mirror docs/contracts/openapi.yaml."""

from __future__ import annotations

from datetime import UTC
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from gpu_lab_twin.domain.errors import ErrorCode
from gpu_lab_twin.domain.fleet import NodeKind
from gpu_lab_twin.domain.heartbeat import GpuSample, HeartbeatPayload
from gpu_lab_twin.domain.node_state import ConnectivityStatus, DriverHealth, NodeState
from gpu_lab_twin.ports.inbound.fleet import FleetView

NODE_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}$"


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(StrictDTO):
    code: ErrorCode
    message: str
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)


class LivenessResponse(StrictDTO):
    status: Literal["ok"]


class ReadinessResponse(StrictDTO):
    status: Literal["ready"]
    nodes: int
    gpuDevices: int


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


class GpuSampleDTO(StrictDTO):
    gpuDeviceId: str = Field(min_length=1, max_length=128)
    temperatureC: float = Field(ge=0, allow_inf_nan=False)
    vramOccupiedGb: float = Field(ge=0, allow_inf_nan=False)


class ExternalContextDTO(StrictDTO):
    source: Literal["EXTERNAL_MOCK"]
    sourceRevision: int = Field(ge=0)
    observedAt: AwareDatetime
    receivedAt: AwareDatetime
    reservationIds: list[str]
    activeWorkloadIds: list[str]

    def utc_document(self) -> dict[str, Any]:
        normalized = self.model_copy(
            update={"observedAt": self.observedAt.astimezone(UTC), "receivedAt": self.receivedAt.astimezone(UTC)}
        )
        return normalized.model_dump(mode="json")


class IngestHeartbeatRequest(StrictDTO):
    eventId: UUID
    occurredAt: AwareDatetime
    receivedAt: AwareDatetime
    schemaVersion: Literal["1.0"]
    bootSessionId: str = Field(min_length=1, max_length=128)
    previousBootSessionId: str | None = Field(default=None, min_length=1, max_length=128)
    stateLoss: bool
    sourceSequence: int | None = Field(default=None, ge=0)
    gpuSamples: list[GpuSampleDTO] = Field(min_length=1, max_length=2)
    driverHealth: DriverHealth
    storageFreeGb: float = Field(ge=0, allow_inf_nan=False)
    externalContext: ExternalContextDTO | None = None

    def to_payload(self) -> HeartbeatPayload:
        return HeartbeatPayload(
            event_id=self.eventId,
            occurred_at=self.occurredAt,
            received_at=self.receivedAt,
            schema_version=self.schemaVersion,
            boot_session_id=self.bootSessionId,
            previous_boot_session_id=self.previousBootSessionId,
            state_loss=self.stateLoss,
            source_sequence=self.sourceSequence,
            gpu_samples=tuple(GpuSample(s.gpuDeviceId, s.temperatureC, s.vramOccupiedGb) for s in self.gpuSamples),
            driver_health=self.driverHealth,
            storage_free_gb=self.storageFreeGb,
            external_context=self.externalContext.utc_document() if self.externalContext else None,
        )


class IngestHeartbeatResponse(StrictDTO):
    eventId: UUID
    nodeId: str
    outcome: Literal["APPLIED", "DUPLICATE", "LATE_IGNORED", "BOOT_CHANGE_DETECTED"]
    nodeRevision: int = Field(ge=0)
    state: NodeState
    cordoned: bool
    connectivityStatus: ConnectivityStatus
    acceptedAt: AwareDatetime
    explanation: ExplanationDTO


class GpuSummaryDTO(StrictDTO):
    gpuDeviceId: str
    vramCapacityGb: float
    temperatureC: float | None
    vramOccupiedGb: float | None


class NodeSummaryDTO(StrictDTO):
    nodeId: str
    kind: NodeKind
    state: NodeState
    cordoned: bool
    connectivityStatus: ConnectivityStatus
    nodeRevision: int = Field(ge=0)
    activeReasonCodes: list[str]
    lastHeartbeatReceivedAt: AwareDatetime | None
    storageCapacityGb: float
    storageFreeGb: float | None
    gpus: list[GpuSummaryDTO]


class FleetResponse(StrictDTO):
    generatedAt: AwareDatetime
    nodeCount: int
    nodes: list[NodeSummaryDTO]

    @classmethod
    def from_view(cls, view: FleetView) -> FleetResponse:
        return cls(
            generatedAt=view.generated_at,
            nodeCount=len(view.nodes),
            nodes=[
                NodeSummaryDTO(
                    nodeId=node.snapshot.node_id,
                    kind=node.snapshot.kind,
                    state=node.snapshot.state,
                    cordoned=node.snapshot.cordoned,
                    connectivityStatus=node.snapshot.connectivity,
                    nodeRevision=node.snapshot.revision,
                    activeReasonCodes=list(node.snapshot.active_reason_codes),
                    lastHeartbeatReceivedAt=node.snapshot.last_accepted_receive_at,
                    storageCapacityGb=node.storage_capacity_gb,
                    storageFreeGb=node.storage_free_gb,
                    gpus=[
                        GpuSummaryDTO(
                            gpuDeviceId=gpu.gpu_device_id,
                            vramCapacityGb=gpu.vram_capacity_gb,
                            temperatureC=gpu.temperature_c,
                            vramOccupiedGb=gpu.vram_occupied_gb,
                        )
                        for gpu in node.gpus
                    ],
                )
                for node in view.nodes
            ],
        )
