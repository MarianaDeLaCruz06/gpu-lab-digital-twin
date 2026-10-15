from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class FakeClock:
    """Deterministic test clock. It never sleeps and never reads wall time."""

    current: datetime

    def __post_init__(self) -> None:
        if self.current.tzinfo is None or self.current.utcoffset() is None:
            raise ValueError("FakeClock requires a timezone-aware instant")
        self.current = self.current.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self.current

    def advance(self, *, seconds: float) -> datetime:
        if seconds < 0:
            raise ValueError("FakeClock cannot move backward")
        self.current += timedelta(seconds=seconds)
        return self.current
