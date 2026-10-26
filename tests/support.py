"""Shared builders and probes for HTTP-level tests."""

from __future__ import annotations

from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import yaml
from jsonschema import Draft202012Validator
from sqlalchemy import Engine, func, select

from gpu_lab_twin.adapters.db.models import (
    AlertRow,
    AuditEventRow,
    NodeRow,
    NodeStateHistoryRow,
    TelemetryGpuSampleRow,
    TelemetrySnapshotRow,
)

CONTRACT = Path(__file__).resolve().parents[1] / "docs" / "contracts" / "openapi.yaml"


def heartbeat_body(
    node_id: str,
    at: datetime,
    *,
    seq: int = 1,
    temperatures: tuple[float, ...] = (40.0,),
    vram_gb: tuple[float, ...] = (0.0,),
    driver: str = "HEALTHY",
    boot: str = "boot-a",
    **overrides: Any,
) -> dict[str, Any]:
    """A contract-valid IngestHeartbeatRequest with a deterministic eventId."""
    body: dict[str, Any] = {
        "eventId": str(uuid5(NAMESPACE_URL, f"hb:{node_id}:{at.isoformat()}:{seq}:{temperatures}:{driver}:{boot}")),
        "occurredAt": at.isoformat(),
        "receivedAt": at.isoformat(),
        "schemaVersion": "1.0",
        "bootSessionId": boot,
        "previousBootSessionId": None,
        "stateLoss": False,
        "sourceSequence": seq,
        "gpuSamples": [
            {"gpuDeviceId": f"{node_id}-gpu-{index}", "temperatureC": temperature, "vramOccupiedGb": vram}
            for index, (temperature, vram) in enumerate(zip(temperatures, vram_gb, strict=True))
        ],
        "driverHealth": driver,
        "storageFreeGb": 320.0,
        "externalContext": None,
    }
    body.update(overrides)
    return body


def effect_probe(engine: Engine) -> tuple:
    """Every mutable fact a rejected command must leave untouched."""
    with engine.connect() as connection:
        revisions = tuple(connection.execute(select(NodeRow.node_id, NodeRow.revision).order_by(NodeRow.node_id)))
        counts = tuple(
            connection.scalar(select(func.count()).select_from(table))
            for table in (TelemetrySnapshotRow, TelemetryGpuSampleRow, NodeStateHistoryRow, AlertRow, AuditEventRow)
        )
    return revisions, counts


@cache
def _contract() -> dict[str, Any]:
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def assert_matches_contract(schema_name: str, instance: Any) -> None:
    """Validate a JSON body against a component schema of the active OpenAPI 3.1 contract."""
    schema = {"$ref": f"#/components/schemas/{schema_name}", "components": _contract()["components"]}
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda error: list(error.path))
    assert not errors, [f"{list(e.path)}: {e.message}" for e in errors]
