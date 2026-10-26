from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from gpu_lab_twin.api.dependencies import get_container
from gpu_lab_twin.api.schemas import ErrorBody, LivenessResponse, ReadinessResponse
from gpu_lab_twin.bootstrap import Container
from gpu_lab_twin.domain.errors import DomainError, ErrorCode

router = APIRouter(tags=["operations"])


@router.get("/health", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse, responses={503: {"model": ErrorBody}})
def readiness(container: Annotated[Container, Depends(get_container)]) -> ReadinessResponse:
    try:
        with container.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        nodes = container.nodes.count_nodes()
        gpus = container.nodes.count_gpu_devices()
    except SQLAlchemyError as exc:
        raise DomainError(
            ErrorCode.ERR_INGRESS_UNAVAILABLE,
            "Database is unreachable; the twin cannot accept input.",
            details={"reason": type(exc).__name__},
        ) from exc

    expected_nodes, expected_gpus = len(container.inventory.nodes), container.inventory.gpu_count
    if (nodes, gpus) != (expected_nodes, expected_gpus):
        raise DomainError(
            ErrorCode.ERR_INGRESS_UNAVAILABLE,
            "Stored fleet does not match the canonical inventory.",
            details={
                "nodes": nodes,
                "gpuDevices": gpus,
                "expectedNodes": expected_nodes,
                "expectedGpuDevices": expected_gpus,
            },
        )
    return ReadinessResponse(status="ready", nodes=nodes, gpuDevices=gpus)
