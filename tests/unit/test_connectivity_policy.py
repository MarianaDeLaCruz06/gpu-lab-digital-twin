from __future__ import annotations

import pytest

from gpu_lab_twin.domain.connectivity_policy import (
    ODD5_POLICY_ID,
    ConnectivityObservation,
    evaluate_connectivity,
)
from gpu_lab_twin.domain.errors import ErrorCode


@pytest.mark.parametrize("observation", list(ConnectivityObservation))
def test_unresolved_odd5_holds_every_raw_observation(observation: ConnectivityObservation) -> None:
    decision = evaluate_connectivity(observation)
    assert decision.reason_code is ErrorCode.ERR_POLICY_UNRESOLVED
    assert decision.policy_id == ODD5_POLICY_ID
