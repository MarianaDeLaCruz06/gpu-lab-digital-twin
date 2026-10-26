"""Typed error catalog shared by every contract (contracts.md, Typed Error Catalog)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    ERR_SCHEMA = "ERR_SCHEMA"
    ERR_UNKNOWN_NODE = "ERR_UNKNOWN_NODE"
    ERR_CAPACITY_RANGE = "ERR_CAPACITY_RANGE"
    ERR_IDEMPOTENCY_CONFLICT = "ERR_IDEMPOTENCY_CONFLICT"
    ERR_ORDER_AMBIGUOUS = "ERR_ORDER_AMBIGUOUS"
    ERR_LATE_EVENT = "ERR_LATE_EVENT"
    ERR_DUPLICATE = "ERR_DUPLICATE"
    ERR_BOOT_SUCCESSION = "ERR_BOOT_SUCCESSION"
    ERR_REVISION_CONFLICT = "ERR_REVISION_CONFLICT"
    ERR_EVIDENCE_NOT_FOUND = "ERR_EVIDENCE_NOT_FOUND"
    ERR_CLOCK_ORDER = "ERR_CLOCK_ORDER"
    ERR_INVALID_TRANSITION = "ERR_INVALID_TRANSITION"
    ERR_POLICY_UNRESOLVED = "ERR_POLICY_UNRESOLVED"
    ERR_POLICY_STATE_CONFLICT = "ERR_POLICY_STATE_CONFLICT"
    ERR_MAINTENANCE_CONFLICT = "ERR_MAINTENANCE_CONFLICT"
    ERR_LOCK_SOURCE_MISMATCH = "ERR_LOCK_SOURCE_MISMATCH"
    ERR_INGRESS_UNAVAILABLE = "ERR_INGRESS_UNAVAILABLE"


_RETRYABLE = frozenset(
    {
        ErrorCode.ERR_ORDER_AMBIGUOUS,
        ErrorCode.ERR_REVISION_CONFLICT,
        ErrorCode.ERR_EVIDENCE_NOT_FOUND,
        ErrorCode.ERR_CLOCK_ORDER,
        ErrorCode.ERR_INGRESS_UNAVAILABLE,
    }
)


class DomainError(Exception):
    """A rejection that must reach the caller as a structured ErrorBody."""

    def __init__(self, code: ErrorCode, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    @property
    def retryable(self) -> bool:
        return self.code in _RETRYABLE


class InventoryError(ValueError):
    """The configured fleet does not match the canonical inventory; startup must fail closed."""
