from __future__ import annotations

from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.ports.inbound.fleet import FleetView
from gpu_lab_twin.ports.outbound.clock import Clock
from gpu_lab_twin.ports.outbound.node_repository import NodeRepository


class FleetQueryService:
    """Implements FleetQueryPort: one consistent read of every configured node, in inventory order."""

    def __init__(self, *, inventory: FleetInventory, nodes: NodeRepository, clock: Clock) -> None:
        self._order = {spec.node_id: index for index, spec in enumerate(inventory.nodes)}
        self._nodes = nodes
        self._clock = clock

    def list_fleet(self) -> FleetView:
        views = self._nodes.list_fleet()
        stored = {view.snapshot.node_id for view in views}
        if stored != set(self._order):
            # A partial or foreign fleet must never be presented as the complete current fleet.
            raise DomainError(
                ErrorCode.ERR_INGRESS_UNAVAILABLE,
                "Stored fleet does not match the canonical inventory.",
                details={
                    "missingNodeIds": sorted(set(self._order) - stored),
                    "unexpectedNodeIds": sorted(stored - set(self._order)),
                },
            )
        ordered = sorted(views, key=lambda view: self._order[view.snapshot.node_id])
        return FleetView(generated_at=self._clock.now(), nodes=tuple(ordered))
