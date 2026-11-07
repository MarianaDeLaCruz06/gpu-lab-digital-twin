from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from gpu_lab_twin.api.dependencies import get_container
from gpu_lab_twin.api.schemas import (
    NODE_ID_PATTERN,
    ErrorBody,
    ScheduleMaintenanceDrainRequest,
    ScheduleMaintenanceDrainResponse,
    SubmitWorkloadSnapshotRequest,
    WorkloadSnapshotResponse,
)
from gpu_lab_twin.bootstrap import Container

router = APIRouter(tags=["maintenance"])
_ERRORS = {code: {"model": ErrorBody} for code in (404, 409, 422, 503)}


@router.post(
    "/v1/nodes/{nodeId}/maintenance-drains",
    operation_id="scheduleMaintenanceDrain",
    response_model=ScheduleMaintenanceDrainResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS | {200: {"model": ScheduleMaintenanceDrainResponse}},
)
def schedule_maintenance(
    nodeId: Annotated[str, Path(pattern=NODE_ID_PATTERN)],
    request: ScheduleMaintenanceDrainRequest,
    container: Annotated[Container, Depends(get_container)],
    response: Response,
):
    result = container.maintenance.schedule(nodeId, request.to_window())
    if result.outcome == "DUPLICATE":
        response.status_code = status.HTTP_200_OK
    return ScheduleMaintenanceDrainResponse.model_validate(result.as_document())


@router.post(
    "/v1/fixtures/workload-snapshots",
    operation_id="submitWorkloadSnapshot",
    response_model=WorkloadSnapshotResponse,
    responses=_ERRORS,
)
def submit_workload(
    request: SubmitWorkloadSnapshotRequest,
    container: Annotated[Container, Depends(get_container)],
) -> WorkloadSnapshotResponse:
    result = container.maintenance.submit_workload(request.to_snapshot())
    return WorkloadSnapshotResponse.model_validate(result.as_document())
