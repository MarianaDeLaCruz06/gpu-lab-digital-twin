from __future__ import annotations

from datetime import UTC, datetime, timedelta


class FakeClock:
    """Manually advanced clock for deterministic simulation; never sleeps or reads wall time."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None or start.utcoffset() is None:
            raise ValueError("FakeClock requires a timezone-aware instant")
        self._current = start.astimezone(UTC)

    def now(self) -> datetime:
        return self._current

    def advance(self, *, seconds: float) -> datetime:
        if seconds < 0:
            raise ValueError("FakeClock cannot move backward")
        self._current += timedelta(seconds=seconds)
        return self._current
