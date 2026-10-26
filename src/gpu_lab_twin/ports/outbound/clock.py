from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Source of the current UTC instant. Only adapters may read the wall clock."""

    def now(self) -> datetime: ...
