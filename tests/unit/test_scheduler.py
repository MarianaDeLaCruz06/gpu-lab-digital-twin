from __future__ import annotations

import asyncio

from gpu_lab_twin.api.scheduler import run_periodically


def test_runs_the_task_once_per_period_without_real_sleeping() -> None:
    waits: list[float] = []
    runs: list[int] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    asyncio.run(run_periodically(lambda: runs.append(1), 5.0, sleep=fake_sleep, iterations=3))

    assert waits == [5.0, 5.0, 5.0]
    assert len(runs) == 3


def test_a_failing_run_does_not_stop_later_runs() -> None:
    attempts: list[int] = []

    def flaky() -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("transient")

    async def fake_sleep(_seconds: float) -> None:
        return None

    asyncio.run(run_periodically(flaky, 1.0, sleep=fake_sleep, iterations=2))

    assert len(attempts) == 2
