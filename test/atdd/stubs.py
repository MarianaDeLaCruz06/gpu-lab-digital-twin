from dataclasses import dataclass, field


class TypedContractError(Exception):
    def __init__(self, code: str, status: int, retryable: bool = False):
        self.code = code
        self.status = status
        self.retryable = retryable
        super().__init__(code)


@dataclass
class EffectProbe:
    node_revisions: dict[str, int] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    audits: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)
    locks: list[dict] = field(default_factory=list)
    forbidden_work_commands: list[dict] = field(default_factory=list)

    def snapshot(self) -> tuple:
        return (
            tuple(sorted(self.node_revisions.items())),
            tuple(map(repr, self.history)),
            tuple(map(repr, self.audits)),
            tuple(map(repr, self.events)),
            tuple(map(repr, self.alerts)),
            tuple(map(repr, self.locks)),
            tuple(map(repr, self.forbidden_work_commands)),
        )


class GpuLabDigitalTwinContractStub:
    """Intentional RED seam. Phase 3 must not implement these operations."""

    def __init__(self, effects: EffectProbe):
        self.effects = effects

    async def ingestHeartbeat(self, nodeId: str, payload: dict, at):
        raise NotImplementedError("RED: ingestHeartbeat contract has no production implementation")

    def transitionNodeState(self, nodeId: str, signal: dict):
        raise NotImplementedError("RED: transitionNodeState contract has no production implementation")

    async def scheduleMaintenanceDrain(self, nodeId: str, window: dict):
        raise NotImplementedError("RED: scheduleMaintenanceDrain contract has no production implementation")
