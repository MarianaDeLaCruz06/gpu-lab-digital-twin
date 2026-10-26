from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """The single production wall-clock read in the service."""

    def now(self) -> datetime:
        return datetime.now(UTC)
