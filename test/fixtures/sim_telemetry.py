from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid5, NAMESPACE_URL


@dataclass(frozen=True)
class ScriptedEvent:
    eventId: UUID
    nodeId: str
    occurredAt: datetime
    kind: str
    payload: dict


class SimTelemetry:
    """Deterministic test-only fault script generator."""

    def heartbeat(self, node_id: str, at: datetime, *, temperature_c: float = 40.0, boot: str = "boot-a", sequence: int = 1, state_loss: bool = False) -> ScriptedEvent:
        identity = f"heartbeat:{node_id}:{at.isoformat()}:{temperature_c}:{boot}:{sequence}:{state_loss}"
        return ScriptedEvent(uuid5(NAMESPACE_URL, identity), node_id, at, "HEARTBEAT", {"temperatureC": temperature_c, "bootSessionId": boot, "sourceSequence": sequence, "stateLoss": state_loss})

    def flapping(self, node_id: str, start: datetime, *, observations: int = 12) -> tuple[ScriptedEvent, ...]:
        return tuple(
            ScriptedEvent(uuid5(NAMESPACE_URL, f"flap:{node_id}:{index}"), node_id, start + timedelta(seconds=5 * index), "CONNECTIVITY", {"status": "ONLINE" if index % 2 == 0 else "OFFLINE"})
            for index in range(observations)
        )

    def reboot(self, at: datetime) -> ScriptedEvent:
        return self.heartbeat("ws-gpu-05", at, boot="boot-b", sequence=1, state_loss=True)
