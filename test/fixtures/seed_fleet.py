from dataclasses import dataclass


@dataclass(frozen=True)
class GpuFixture:
    gpuDeviceId: str
    vramCapacityGb: int


@dataclass(frozen=True)
class NodeFixture:
    nodeId: str
    kind: str
    gpuDevices: tuple[GpuFixture, ...]
    state: str = "HEALTHY"
    cordoned: bool = False


def canonical_seed_fleet() -> tuple[NodeFixture, ...]:
    workstations = tuple(
        NodeFixture(
            nodeId=f"ws-gpu-{index:02d}",
            kind="WORKSTATION",
            gpuDevices=(GpuFixture(f"ws-gpu-{index:02d}-gpu-0", 24),),
        )
        for index in range(1, 32)
    )
    server = NodeFixture(
        nodeId="central-gpu-server",
        kind="SERVER",
        gpuDevices=(GpuFixture("central-gpu-server-gpu-0", 48), GpuFixture("central-gpu-server-gpu-1", 48)),
    )
    return workstations + (server,)
