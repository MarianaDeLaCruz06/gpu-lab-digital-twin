"""Transport DTOs. Field names and constraints mirror docs/contracts/openapi.yaml."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from gpu_lab_twin.domain.errors import ErrorCode


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
