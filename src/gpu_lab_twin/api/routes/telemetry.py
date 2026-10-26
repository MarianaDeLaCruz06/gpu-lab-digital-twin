from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from gpu_lab_twin.api.dependencies import get_container
from gpu_lab_twin.api.schemas import NODE_ID_PATTERN, ErrorBody, IngestHeartbeatRequest, IngestHeartbeatResponse
from gpu_lab_twin.bootstrap import Container

router = APIRouter(tags=["telemetry"])

_ERRORS = {status: {"model": ErrorBody} for status in (404, 409, 422, 503)}


@router.post(
    "/v1/nodes/{nodeId}/heartbeats",
    operation_id="ingestHeartbeat",
    response_model=IngestHeartbeatResponse,
    responses=_ERRORS,
)
def ingest_heartbeat(
    nodeId: Annotated[str, Path(pattern=NODE_ID_PATTERN)],
    request: IngestHeartbeatRequest,
    container: Annotated[Container, Depends(get_container)],
) -> IngestHeartbeatResponse:
    result = container.heartbeats.ingest_heartbeat(nodeId, request.to_payload())
    return IngestHeartbeatResponse.model_validate(result.as_document())
