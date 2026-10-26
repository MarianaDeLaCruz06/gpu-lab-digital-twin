from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gpu_lab_twin.domain.heartbeat_policy import is_silent, missed_intervals

LAST = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("elapsed", "silent"),
    [
        (timedelta(seconds=29.999), False),
        (timedelta(seconds=30), False),
        (timedelta(seconds=30, microseconds=1), True),
        (timedelta(seconds=45), True),
    ],
    ids=["below", "exactly-3-intervals", "one-microsecond-past", "annex-45s"],
)
def test_strict_boundary_at_three_10s_intervals(elapsed: timedelta, silent: bool) -> None:
    assert is_silent(LAST, LAST + elapsed, interval_ms=10_000) is silent


def test_node_that_never_reported_is_not_silent() -> None:
    assert is_silent(None, LAST + timedelta(days=1), interval_ms=10_000) is False


def test_missed_intervals_reports_the_exact_ratio() -> None:
    assert missed_intervals(LAST, LAST + timedelta(seconds=45), interval_ms=10_000) == 4.5


@given(
    interval_ms=st.integers(min_value=1, max_value=600_000),
    elapsed_us=st.integers(min_value=0, max_value=10**10),
)
def test_silent_exactly_when_elapsed_exceeds_three_intervals(interval_ms: int, elapsed_us: int) -> None:
    evaluation_at = LAST + timedelta(microseconds=elapsed_us)
    assert is_silent(LAST, evaluation_at, interval_ms) is (elapsed_us > 3 * interval_ms * 1000)
