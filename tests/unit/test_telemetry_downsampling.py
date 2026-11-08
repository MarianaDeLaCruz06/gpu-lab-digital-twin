from datetime import timedelta
from uuid import uuid4

import pytest

from gpu_lab_twin.domain.heartbeat import GpuSample, HeartbeatPayload
from gpu_lab_twin.domain.node_state import DriverHealth
from gpu_lab_twin.domain.telemetry_downsampling import TelemetryDownsampler
from tests.conftest import T0


def payload(offset_ms: int, temperature: float) -> HeartbeatPayload:
    at = T0 + timedelta(milliseconds=offset_ms)
    return HeartbeatPayload(
        uuid4(),
        at,
        at,
        "1.0",
        "boot-a",
        None,
        False,
        None,
        (GpuSample("ws-gpu-01-gpu-0", temperature, 1.0),),
        DriverHealth.HEALTHY,
        300.0,
        None,
    )


def test_downsamples_to_ten_hz_and_preserves_peak() -> None:
    sampler = TelemetryDownsampler(frequency_hz=10, capacity_windows=4)
    sampler.observe("ws-gpu-01", payload(1, 40.0))
    sampler.observe("ws-gpu-01", payload(50, 89.0))
    sampler.observe("ws-gpu-01", payload(99, 55.0))
    window = sampler.windows()[0]
    assert window.samples_seen == 3
    assert window.gpus[0].peak_temperature_c == 89.0
    assert abs(window.gpus[0].peak_temperature_c - 89.0) / 89.0 * 100 <= 1


def test_capacity_is_strictly_bounded() -> None:
    sampler = TelemetryDownsampler(frequency_hz=10, capacity_windows=2)
    for offset in (0, 100, 200):
        sampler.observe("ws-gpu-01", payload(offset, 40.0 + offset))
    assert sampler.retained_windows == 2
    assert [item.starts_at for item in sampler.windows()] == [
        T0 + timedelta(milliseconds=100),
        T0 + timedelta(milliseconds=200),
    ]


@pytest.mark.parametrize("frequency,capacity", [(0, 1), (10, 0), (-1, 2)])
def test_invalid_configuration_is_rejected(frequency: int, capacity: int) -> None:
    with pytest.raises(ValueError):
        TelemetryDownsampler(frequency_hz=frequency, capacity_windows=capacity)
