"""Bounded, peak-preserving telemetry projection for Story 3.5."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from gpu_lab_twin.domain.heartbeat import HeartbeatPayload


@dataclass(frozen=True, slots=True)
class DownsampledGpu:
    gpu_device_id: str
    peak_temperature_c: float
    latest_vram_occupied_gb: float


@dataclass(frozen=True, slots=True)
class DownsampledWindow:
    node_id: str
    starts_at: datetime
    ends_at: datetime
    samples_seen: int
    gpus: tuple[DownsampledGpu, ...]


class TelemetryDownsampler:
    """Retain a fixed number of 100 ms windows; input cardinality cannot grow memory."""

    def __init__(self, *, frequency_hz: int = 10, capacity_windows: int = 600) -> None:
        if frequency_hz <= 0 or capacity_windows <= 0:
            raise ValueError("frequency_hz and capacity_windows must be positive")
        self._window_us = 1_000_000 // frequency_hz
        self._capacity = capacity_windows
        self._windows: dict[tuple[str, datetime], DownsampledWindow] = {}
        self._order: deque[tuple[str, datetime]] = deque()

    @property
    def retained_windows(self) -> int:
        return len(self._windows)

    def observe(self, node_id: str, payload: HeartbeatPayload) -> DownsampledWindow:
        start = payload.occurred_at.replace(
            microsecond=(payload.occurred_at.microsecond // self._window_us) * self._window_us
        )
        key = (node_id, start)
        existing = self._windows.get(key)
        prior = {gpu.gpu_device_id: gpu for gpu in existing.gpus} if existing else {}
        gpus = tuple(
            DownsampledGpu(
                gpu_device_id=sample.gpu_device_id,
                peak_temperature_c=max(sample.temperature_c, prior.get(sample.gpu_device_id, _zero(sample)).peak_temperature_c),
                latest_vram_occupied_gb=sample.vram_occupied_gb,
            )
            for sample in payload.gpu_samples
        )
        result = DownsampledWindow(
            node_id=node_id,
            starts_at=start,
            ends_at=start + timedelta(microseconds=self._window_us),
            samples_seen=(existing.samples_seen if existing else 0) + 1,
            gpus=gpus,
        )
        if existing is None:
            self._order.append(key)
        self._windows[key] = result
        while len(self._order) > self._capacity:
            self._windows.pop(self._order.popleft(), None)
        return result

    def windows(self, node_id: str | None = None) -> tuple[DownsampledWindow, ...]:
        return tuple(self._windows[key] for key in self._order if node_id is None or key[0] == node_id)


def _zero(sample) -> DownsampledGpu:
    return DownsampledGpu(sample.gpu_device_id, float("-inf"), sample.vram_occupied_gb)

