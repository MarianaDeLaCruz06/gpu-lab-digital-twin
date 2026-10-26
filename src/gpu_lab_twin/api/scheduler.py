"""Driving adapter that triggers the periodic liveness scan inside the service process."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from starlette.concurrency import run_in_threadpool

from gpu_lab_twin.domain.errors import DomainError

logger = logging.getLogger(__name__)


async def run_periodically(
    task: Callable[[], object],
    period_seconds: float,
    *,
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    iterations: int | None = None,
) -> None:
    """Run ``task`` every ``period_seconds`` until cancelled; one failing run never stops the loop."""
    completed = 0
    while iterations is None or completed < iterations:
        await sleep(period_seconds)
        try:
            await run_in_threadpool(task)
        except DomainError as exc:
            # Expected rejections (e.g. ERR_CLOCK_ORDER after a wall-clock step back) are not crashes.
            logger.warning("periodic task rejected: %s %s", exc.code, exc.message)
        except Exception:
            logger.exception("periodic task failed; retrying next period")
        completed += 1
