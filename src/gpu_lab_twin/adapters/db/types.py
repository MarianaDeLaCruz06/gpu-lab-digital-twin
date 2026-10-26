"""Column types that behave identically on PostgreSQL (target) and SQLite (tests)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.types import DateTime, TypeDecorator


class UtcDateTime(TypeDecorator[datetime]):
    """timestamptz that rejects naive input and always returns aware UTC (SQLite drops offsets)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetimes are not allowed; supply a timezone-aware UTC instant")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


TextArray = ARRAY(Text).with_variant(JSON(), "sqlite")
JsonDocument = JSONB().with_variant(JSON(), "sqlite")
