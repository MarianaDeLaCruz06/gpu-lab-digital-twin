"""Heartbeat value objects (ARCHITECTURE §7.2)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from gpu_lab_twin.domain.node_state import DriverHealth


@dataclass(frozen=True, slots=True)
class GpuSample:
    gpu_device_id: str
    temperature_c: float
    vram_occupied_gb: float


@dataclass(frozen=True, slots=True)
class HeartbeatPayload:
    event_id: UUID
    occurred_at: datetime
    received_at: datetime
    schema_version: str
    boot_session_id: str
    previous_boot_session_id: str | None
    state_loss: bool
    source_sequence: int | None
    gpu_samples: tuple[GpuSample, ...]
    driver_health: DriverHealth
    storage_free_gb: float
    external_context: Mapping[str, Any] | None = None

    @property
    def max_temperature_c(self) -> float:
        return max(sample.temperature_c for sample in self.gpu_samples)

    def canonical_hash(self, node_id: str) -> str:
        """SHA-256 over a normalized, key-sorted JSON rendering; identifies "the same payload" for idempotency.

        Instants are rendered in UTC and GPU samples sorted by device, so an equivalent retry that only
        differs in offset notation or sample order is still recognised as a duplicate.
        """
        document = {
            "nodeId": node_id,
            "eventId": str(self.event_id),
            "occurredAt": self.occurred_at.astimezone(UTC).isoformat(),
            "receivedAt": self.received_at.astimezone(UTC).isoformat(),
            "schemaVersion": self.schema_version,
            "bootSessionId": self.boot_session_id,
            "previousBootSessionId": self.previous_boot_session_id,
            "stateLoss": self.state_loss,
            "sourceSequence": self.source_sequence,
            "gpuSamples": [
                {
                    "gpuDeviceId": s.gpu_device_id,
                    "temperatureC": s.temperature_c,
                    "vramOccupiedGb": s.vram_occupied_gb,
                }
                for s in sorted(self.gpu_samples, key=lambda sample: sample.gpu_device_id)
            ],
            "driverHealth": self.driver_health.value,
            "storageFreeGb": self.storage_free_gb,
            "externalContext": dict(self.external_context) if self.external_context is not None else None,
        }
        canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
