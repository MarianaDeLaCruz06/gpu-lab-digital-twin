from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from gpu_lab_twin import __version__
from gpu_lab_twin.api.errors import install_error_handlers
from gpu_lab_twin.api.routes import health, maintenance, nodes, telemetry, ui
from gpu_lab_twin.api.scheduler import run_periodically
from gpu_lab_twin.bootstrap import Container, build_container
from gpu_lab_twin.config.settings import get_settings

logger = logging.getLogger(__name__)


def create_app(container: Container | None = None) -> FastAPI:
    """Build the service. Tests inject a container; production builds one from the environment."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved = container or build_container(get_settings())
        logging.basicConfig(level=resolved.settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        added = resolved.nodes.seed_inventory(resolved.inventory)
        logger.info("fleet inventory ready: %d nodes (%d newly seeded)", len(resolved.inventory.nodes), added)
        app.state.container = resolved
        scan = None
        if resolved.settings.liveness_scan_seconds > 0:
            scan = asyncio.create_task(
                run_periodically(resolved.liveness.evaluate_fleet_liveness, resolved.settings.liveness_scan_seconds)
            )
        yield
        if scan is not None:
            scan.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await scan
        if container is None:
            resolved.engine.dispose()

    app = FastAPI(
        title="GPU Lab Digital Twin — Module 3",
        version=__version__,
        description="Standalone simulated digital twin of the 32-node university GPU lab.",
        lifespan=lifespan,
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(telemetry.router)
    app.include_router(nodes.router)
    app.include_router(maintenance.router)
    app.include_router(ui.router)
    app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "static"), name="static")
    return app
