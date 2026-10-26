from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from gpu_lab_twin.api.dependencies import get_container
from gpu_lab_twin.api.schemas import ErrorBody, FleetResponse
from gpu_lab_twin.bootstrap import Container

router = APIRouter(tags=["fleet"])


@router.get("/v1/nodes", operation_id="listFleet", response_model=FleetResponse, responses={503: {"model": ErrorBody}})
def list_fleet(container: Annotated[Container, Depends(get_container)]) -> FleetResponse:
    return FleetResponse.from_view(container.fleet.list_fleet())
