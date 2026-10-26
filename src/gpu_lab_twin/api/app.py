from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from gpu_lab_twin import __version__
from gpu_lab_twin.api.errors import install_error_handlers
from gpu_lab_twin.api.routes import health
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
        yield
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
    return app
