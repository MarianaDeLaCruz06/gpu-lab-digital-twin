from __future__ import annotations

import contextlib
import logging
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from typing import TYPE_CHECKING

from gpu_lab_twin.domain.errors import DomainError, ErrorCode

if TYPE_CHECKING:
    from gpu_lab_twin.domain.heartbeat import HeartbeatPayload
    from gpu_lab_twin.ports.inbound.heartbeat import HeartbeatResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HeartbeatCommand:
    node_id: str
    payload: HeartbeatPayload
    future: Future[HeartbeatResult]


class DurableHeartbeatBatchWriter:
    """Single sequencer thread: batches commands into one durable commit while each caller awaits its result."""

    def __init__(
        self,
        *,
        process_batch,
        write_lock: threading.Lock,
        max_queue: int = 4096,
        max_batch: int = 256,
        flush_timeout_s: float = 0.01,
        enqueue_timeout_s: float = 5.0,
    ) -> None:
        self._process_batch = process_batch
        self._write_lock = write_lock
        self._max_batch = max_batch
        self._flush_timeout_s = flush_timeout_s
        self._enqueue_timeout_s = enqueue_timeout_s
        self._queue: queue.Queue[HeartbeatCommand | None] = queue.Queue(maxsize=max_queue)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="heartbeat-batch-writer", daemon=True)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread.start()

    def submit(self, node_id: str, payload: HeartbeatPayload) -> Future[HeartbeatResult]:
        if self._stop.is_set():
            raise DomainError(ErrorCode.ERR_INGRESS_UNAVAILABLE, "Heartbeat ingestion is shutting down.")
        cmd = HeartbeatCommand(node_id=node_id, payload=payload, future=Future())
        try:
            self._queue.put(cmd, timeout=self._enqueue_timeout_s)
        except queue.Full as exc:
            raise DomainError(
                ErrorCode.ERR_INGRESS_UNAVAILABLE,
                "Heartbeat ingress queue is full; explicit backpressure applied.",
                details={"maxQueue": self._queue.maxsize},
            ) from exc
        return cmd.future

    def shutdown(self, *, timeout: float = 5.0) -> None:
        if not self._started:
            return
        self._stop.set()
        with contextlib.suppress(queue.Full):
            self._queue.put_nowait(None)
        self._thread.join(timeout=timeout)
        self._drain_outstanding(
            DomainError(ErrorCode.ERR_INGRESS_UNAVAILABLE, "Heartbeat ingestion stopped before durable commit.")
        )

    def _drain_outstanding(self, error: DomainError) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is not None and not item.future.done():
                item.future.set_exception(error)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                first = self._queue.get(timeout=self._flush_timeout_s)
            except queue.Empty:
                continue
            if first is None:
                break
            batch = [first]
            while len(batch) < self._max_batch:
                try:
                    item = self._queue.get_nowait()
                except queue.Empty:
                    break
                if item is None:
                    self._stop.set()
                    break
                batch.append(item)
            try:
                with self._write_lock:
                    self._process_batch(batch)
            except Exception as exc:  # propagate to all unresolved futures in this batch
                logger.exception("heartbeat batch failed")
                for cmd in batch:
                    if not cmd.future.done():
                        cmd.future.set_exception(exc)
        # graceful drain of any commands already queued before stop was observed
        remainder = []
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is not None:
                remainder.append(item)
        if remainder:
            try:
                with self._write_lock:
                    self._process_batch(remainder)
            except Exception as exc:
                logger.exception("heartbeat final batch failed")
                for cmd in remainder:
                    if not cmd.future.done():
                        cmd.future.set_exception(exc)
