from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(include_in_schema=False)
_STATIC = Path(__file__).resolve().parents[1] / "static"


@router.get("/technician/fleet-grid")
def fleet_grid() -> FileResponse:
    return FileResponse(_STATIC / "fleet-map.html")
