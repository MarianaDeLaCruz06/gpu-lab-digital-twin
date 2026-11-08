"""Composition root: the only module that wires adapters to ports."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from sqlalchemy import Engine

from gpu_lab_twin.adapters.clock.system_clock import SystemClock
from gpu_lab_twin.adapters.db.engine import build_engine, build_session_factory
from gpu_lab_twin.adapters.db.node_repository import SqlNodeRepository
from gpu_lab_twin.adapters.sim.fleet_fixture import load_fleet_inventory
from gpu_lab_twin.application.connectivity_service import ConnectivityService
from gpu_lab_twin.application.fleet_query import FleetQueryService
from gpu_lab_twin.application.heartbeat_batch_writer import DurableHeartbeatBatchWriter
from gpu_lab_twin.application.heartbeat_service import HeartbeatService
from gpu_lab_twin.application.liveness_service import LivenessService
from gpu_lab_twin.application.maintenance_service import MaintenanceService
from gpu_lab_twin.config.settings import Settings
from gpu_lab_twin.domain.fleet import FleetInventory
from gpu_lab_twin.domain.telemetry_downsampling import TelemetryDownsampler
from gpu_lab_twin.ports.inbound.connectivity import ConnectivityPort
from gpu_lab_twin.ports.inbound.fleet import FleetQueryPort
from gpu_lab_twin.ports.inbound.heartbeat import HeartbeatPort
from gpu_lab_twin.ports.inbound.liveness import LivenessPort
from gpu_lab_twin.ports.inbound.maintenance import MaintenancePort
from gpu_lab_twin.ports.outbound.clock import Clock
from gpu_lab_twin.ports.outbound.node_repository import NodeRepository


@dataclass(frozen=True)
class Container:
    settings: Settings
    engine: Engine
    inventory: FleetInventory
    clock: Clock
    nodes: NodeRepository
    heartbeats: HeartbeatPort
    liveness: LivenessPort
    fleet: FleetQueryPort
    connectivity: ConnectivityPort
    telemetry: TelemetryDownsampler
    maintenance: MaintenancePort
    heartbeat_batch_writer: DurableHeartbeatBatchWriter | None = None


def build_container(settings: Settings, *, clock: Clock | None = None, engine: Engine | None = None) -> Container:
    engine = engine or build_engine(settings.database_url)
    clock = clock or SystemClock()
    inventory = load_fleet_inventory(settings.fleet_fixture_path)
    nodes = SqlNodeRepository(build_session_factory(engine))
    write_lock = threading.Lock()
    telemetry = TelemetryDownsampler(frequency_hz=10, capacity_windows=len(inventory.nodes) * 600)
    heartbeat_service = HeartbeatService(
        inventory=inventory,
        nodes=nodes,
        clock=clock,
        policy_version=settings.policy_version,
        write_lock=write_lock,
        downsampler=telemetry,
    )
    batch_writer = DurableHeartbeatBatchWriter(
        process_batch=heartbeat_service.process_commands,
        write_lock=write_lock,
        max_queue=settings.heartbeat_queue_capacity,
        max_batch=settings.heartbeat_max_batch,
        flush_timeout_s=0.05,
        enqueue_timeout_s=settings.heartbeat_enqueue_timeout_s,
        collect_window_s=settings.heartbeat_batch_window_ms / 1000.0,
    )
    heartbeat_service.attach_batch_writer(batch_writer)
    batch_writer.start()
    return Container(
        settings=settings,
        engine=engine,
        inventory=inventory,
        clock=clock,
        nodes=nodes,
        heartbeats=heartbeat_service,
        liveness=LivenessService(
            inventory=inventory,
            nodes=nodes,
            clock=clock,
            policy_version=settings.policy_version,
            write_lock=write_lock,
        ),
        fleet=FleetQueryService(inventory=inventory, nodes=nodes, clock=clock),
        connectivity=ConnectivityService(
            nodes=nodes,
            clock=clock,
            policy_version=settings.policy_version,
            write_lock=write_lock,
        ),
        telemetry=telemetry,
        maintenance=MaintenanceService(inventory=inventory, nodes=nodes, clock=clock, write_lock=write_lock),
        heartbeat_batch_writer=batch_writer,
    )
