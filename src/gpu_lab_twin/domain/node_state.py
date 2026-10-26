"""Closed vocabularies for the node aggregate (ARCHITECTURE §5.1)."""

from __future__ import annotations

from enum import StrEnum


class NodeState(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    DRAINING = "DRAINING"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class ConnectivityStatus(StrEnum):
    """Derived freshness signal; deliberately separate from NodeState."""

    UNKNOWN = "UNKNOWN"
    ONLINE = "ONLINE"
    SILENT = "SILENT"
    CONNECTIVITY_UNSTABLE = "CONNECTIVITY_UNSTABLE"


class DriverHealth(StrEnum):
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"
