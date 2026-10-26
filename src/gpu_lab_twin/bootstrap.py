"""Composition root: the only module that wires adapters to ports."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine

from gpu_lab_twin.adapters.clock.system_clock import SystemClock
from gpu_lab_twin.adapters.db.engine import build_engine, build_session_factory
from gpu_lab_twin.adapters.db.node_repository import SqlNodeRepository
from gpu_lab_twin.adapters.sim.fleet_fixture import load_fleet_inventory
from gpu_lab_twin.config.settings import Settings
from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.ports.outbound.clock import Clock
from gpu_lab_twin.ports.outbound.node_repository import NodeRepository


@dataclass(frozen=True)
class Container:
    settings: Settings
    engine: Engine
    inventory: FleetInventory
    clock: Clock
    nodes: NodeRepository


def build_container(settings: Settings, *, clock: Clock | None = None, engine: Engine | None = None) -> Container:
    engine = engine or build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    return Container(
        settings=settings,
        engine=engine,
        inventory=load_fleet_inventory(settings.fleet_fixture_path),
        clock=clock or SystemClock(),
        nodes=SqlNodeRepository(session_factory),
    )
