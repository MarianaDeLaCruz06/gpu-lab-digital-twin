from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from gpu_lab_twin.adapters.db.models import Base
from gpu_lab_twin.adapters.sim.fake_clock import FakeClock
from gpu_lab_twin.bootstrap import Container, build_container
from gpu_lab_twin.config.settings import Settings
from gpu_lab_twin.domain.errors import DomainError, ErrorCode
from gpu_lab_twin.domain.heartbeat import GpuSample, HeartbeatPayload
from gpu_lab_twin.domain.node_state import DriverHealth
from tests.conftest import T0, TEST_DATABASE_URL
from tests.support import heartbeat_body


def _payload(node_id: str, at, *, seq: int = 1, temperatures=(40.0,), boot="boot-a", event_id=None):
    eid = event_id or uuid5(NAMESPACE_URL, f"batch:{node_id}:{seq}:{at.isoformat()}:{temperatures}:{boot}")
    temps = tuple(temperatures)
    vram = tuple(0.0 for _ in temps)
    return HeartbeatPayload(
        event_id=eid,
        occurred_at=at,
        received_at=at,
        schema_version="1.0",
        boot_session_id=boot,
        previous_boot_session_id=None,
        state_loss=False,
        source_sequence=seq,
        gpu_samples=tuple(
            GpuSample(f"{node_id}-gpu-{i}", float(t), float(v))
            for i, (t, v) in enumerate(zip(temps, vram, strict=True))
        ),
        driver_health=DriverHealth.HEALTHY,
        storage_free_gb=320.0,
    )


@pytest.fixture
def batch_container(fake_clock: FakeClock):
    settings = Settings(
        database_url=TEST_DATABASE_URL,
        policy_version="test-batch-v1",
        liveness_scan_seconds=0,
        heartbeat_queue_capacity=4096,
        heartbeat_max_batch=32,
        heartbeat_batch_window_ms=20.0,
        heartbeat_enqueue_timeout_s=5.0,
    )
    built = build_container(settings, clock=fake_clock)
    Base.metadata.drop_all(built.engine)
    Base.metadata.create_all(built.engine)
    built.nodes.seed_inventory(built.inventory)
    yield built
    if built.heartbeat_batch_writer is not None:
        built.heartbeat_batch_writer.shutdown(timeout=5.0)
    built.engine.dispose()


def _count_commits(container: Container, fn):
    commits = 0

    def on_commit(conn):
        nonlocal commits
        commits += 1

    event.listen(container.engine, "commit", on_commit)
    try:
        result = fn()
    finally:
        event.remove(container.engine, "commit", on_commit)
    return result, commits


def test_compatible_multi_node_heartbeats_share_fewer_transactions(batch_container: Container, fake_clock: FakeClock):
    specs = list(batch_container.inventory.nodes)[:32]
    fake_clock.advance(seconds=60)
    now = fake_clock.now()
    payloads = []
    for spec in specs:
        temps = tuple(40.0 for _ in spec.gpu_devices)
        payloads.append(
            (
                spec.node_id,
                _payload(
                    spec.node_id,
                    now,
                    seq=1,
                    temperatures=temps,
                    event_id=uuid5(NAMESPACE_URL, f"batch-multi:{spec.node_id}"),
                ),
            )
        )

    def run():
        with ThreadPoolExecutor(max_workers=16) as ex:
            futures = [ex.submit(batch_container.heartbeats.ingest_heartbeat, nid, p) for nid, p in payloads]
            return [f.result(timeout=10) for f in futures]

    results, commits = _count_commits(batch_container, run)
    assert len(results) == 32
    assert all(r.outcome == "APPLIED" for r in results)
    assert 1 <= commits < 32
    assert commits <= 8, f"expected substantial batching, got {commits} commits for 32 heartbeats"

    fleet = batch_container.nodes.list_fleet()
    nodes = [s.node_id for s in specs]
    revisions = sorted(v.snapshot.revision for v in fleet if v.snapshot.node_id in nodes)
    assert revisions == [1] * 32


def test_same_node_commands_preserve_order(batch_container: Container, fake_clock: FakeClock):
    node = "ws-gpu-01"
    results = []
    for i in range(4):
        fake_clock.advance(seconds=1)
        p = _payload(node, fake_clock.now(), seq=i + 1)
        results.append(batch_container.heartbeats.ingest_heartbeat(node, p))
    assert [r.outcome for r in results] == ["APPLIED"] * 4
    assert [r.node_revision for r in results] == [1, 2, 3, 4]


def test_duplicate_semantics_unchanged(batch_container: Container, fake_clock: FakeClock):
    node = "ws-gpu-01"
    fake_clock.advance(seconds=1)
    p = _payload(node, fake_clock.now(), seq=1)
    first = batch_container.heartbeats.ingest_heartbeat(node, p)
    dup = batch_container.heartbeats.ingest_heartbeat(node, p)
    assert first.outcome == "APPLIED"
    assert dup.outcome == "DUPLICATE"
    assert dup.node_revision == first.node_revision


def test_late_semantics_unchanged(batch_container: Container, fake_clock: FakeClock):
    node = "ws-gpu-01"
    fake_clock.advance(seconds=2)
    p1 = _payload(node, fake_clock.now(), seq=2)
    assert batch_container.heartbeats.ingest_heartbeat(node, p1).outcome == "APPLIED"
    # occurred/received in the past relative to accepted event but clock now is fine (<= at check uses processing at)
    fake_clock.advance(seconds=1)
    late = _payload(node, T0 + timedelta(seconds=1), seq=1, event_id=uuid5(NAMESPACE_URL, "late-seq1"))
    assert batch_container.heartbeats.ingest_heartbeat(node, late).outcome == "LATE_IGNORED"


def test_boot_change_semantics_unchanged(batch_container: Container, fake_clock: FakeClock):
    node = "ws-gpu-01"
    fake_clock.advance(seconds=1)
    p1 = _payload(node, fake_clock.now(), seq=1, boot="boot-a")
    assert batch_container.heartbeats.ingest_heartbeat(node, p1).outcome == "APPLIED"
    fake_clock.advance(seconds=5)
    now = fake_clock.now()
    p2 = HeartbeatPayload(
        event_id=uuid5(NAMESPACE_URL, "boot-change"),
        occurred_at=now,
        received_at=now,
        schema_version="1.0",
        boot_session_id="boot-b",
        previous_boot_session_id="boot-a",
        state_loss=False,
        source_sequence=1,
        gpu_samples=(GpuSample(f"{node}-gpu-0", 40.0, 0.0),),
        driver_health=DriverHealth.HEALTHY,
        storage_free_gb=320.0,
    )
    assert batch_container.heartbeats.ingest_heartbeat(node, p2).outcome == "BOOT_CHANGE_DETECTED"


def test_thermal_semantics_unchanged(batch_container: Container, fake_clock: FakeClock):
    node = "ws-gpu-01"
    fake_clock.advance(seconds=1)
    hot = _payload(node, fake_clock.now(), seq=1, temperatures=(95.0,))
    res = batch_container.heartbeats.ingest_heartbeat(node, hot)
    assert res.outcome == "APPLIED"
    assert res.state.name == "DEGRADED" or res.state.value == "DEGRADED"


def test_queue_full_backpressure():
    from concurrent.futures import Future

    from gpu_lab_twin.application.heartbeat_batch_writer import DurableHeartbeatBatchWriter, HeartbeatCommand

    writer = DurableHeartbeatBatchWriter(
        process_batch=lambda batch: None,
        write_lock=__import__("threading").Lock(),
        max_queue=1,
        max_batch=1,
        flush_timeout_s=1.0,
        enqueue_timeout_s=0.01,
    )
    # Not started: deterministic queue saturation without a consumer thread.
    writer._queue.put_nowait(HeartbeatCommand("ws-gpu-01", _payload("ws-gpu-01", T0, seq=1), Future()))
    with pytest.raises(DomainError) as caught:
        writer.submit("ws-gpu-02", _payload("ws-gpu-02", T0, seq=2))
    assert caught.value.code is ErrorCode.ERR_INGRESS_UNAVAILABLE
    assert "full" in caught.value.message.lower()


def test_rollback_propagates_to_batch_futures(batch_container: Container, fake_clock: FakeClock, monkeypatch):
    nodes = ["ws-gpu-01", "ws-gpu-02", "ws-gpu-03", "ws-gpu-04"]
    fake_clock.advance(seconds=10)
    now = fake_clock.now()
    payloads = [(n, _payload(n, now, seq=1, event_id=uuid5(NAMESPACE_URL, f"rb:{n}"))) for n in nodes]
    original = batch_container.nodes.commit_heartbeat_batch

    def boom(commits):
        raise RuntimeError("forced batch failure")

    monkeypatch.setattr(batch_container.nodes, "commit_heartbeat_batch", boom)
    errors = []

    def submit(nid, p):
        try:
            batch_container.heartbeats.ingest_heartbeat(nid, p)
        except Exception as e:
            errors.append(e)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(lambda it: submit(*it), payloads))
    assert len(errors) == len(nodes)
    monkeypatch.setattr(batch_container.nodes, "commit_heartbeat_batch", original)
    # No partial durable state
    for n in nodes:
        snap = batch_container.nodes.get_node(n)
        assert snap is not None and snap.revision == 0


def test_global_offsets_unique_and_monotonic(batch_container: Container, fake_clock: FakeClock):
    from sqlalchemy import select

    from gpu_lab_twin.adapters.db.models import TelemetrySnapshotRow

    specs = list(batch_container.inventory.nodes)[:8]
    fake_clock.advance(seconds=30)
    now = fake_clock.now()
    for spec in specs:
        temps = tuple(40.0 for _ in spec.gpu_devices)
        res = batch_container.heartbeats.ingest_heartbeat(
            spec.node_id,
            _payload(
                spec.node_id, now, seq=1, temperatures=temps, event_id=uuid5(NAMESPACE_URL, f"off:{spec.node_id}")
            ),
        )
        assert res.outcome == "APPLIED"
    with batch_container.engine.connect() as conn:
        offsets = list(
            conn.scalars(select(TelemetrySnapshotRow.ingest_offset).order_by(TelemetrySnapshotRow.ingest_offset))
        )
    assert offsets == sorted(offsets)
    assert len(offsets) == len(set(offsets))
    assert len(offsets) >= 8


def test_shutdown_rejects_new_submissions():

    from gpu_lab_twin.application.heartbeat_batch_writer import DurableHeartbeatBatchWriter

    writer = DurableHeartbeatBatchWriter(
        process_batch=lambda batch: None,
        write_lock=__import__("threading").Lock(),
        max_queue=8,
        max_batch=8,
        flush_timeout_s=0.01,
    )
    writer.start()
    writer.shutdown(timeout=2.0)
    with pytest.raises(DomainError) as caught:
        writer.submit("ws-gpu-01", _payload("ws-gpu-01", T0, seq=1))
    assert caught.value.code is ErrorCode.ERR_INGRESS_UNAVAILABLE


def test_http_burst_still_applies_all(client: TestClient, container: Container, fake_clock: FakeClock):
    for index, spec in enumerate(container.inventory.nodes, start=1):
        fake_clock.advance(seconds=0.001)
        temperatures = tuple(45.0 for _ in spec.gpu_devices)
        at = T0 + timedelta(milliseconds=index)
        response = client.post(
            f"/v1/nodes/{spec.node_id}/heartbeats",
            json=heartbeat_body(
                spec.node_id, at, seq=1, temperatures=temperatures, vram_gb=tuple(0.0 for _ in temperatures)
            ),
        )
        assert response.status_code == 200
        assert response.json()["outcome"] == "APPLIED"
    fleet = client.get("/v1/nodes").json()
    assert all(node["nodeRevision"] == 1 for node in fleet["nodes"])
