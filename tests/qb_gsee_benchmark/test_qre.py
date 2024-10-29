################################################################################
# © Copyright 2024 Zapata Computing Inc.
################################################################################


import os

import numpy as np
import pytest
from pyscf.tools import fcidump

from qb_gsee_benchmark.qre import (
    get_df_qpe_circuit,
    get_failure_tolerance_per_shot,
    get_num_shots,
)


@pytest.mark.parametrize(
    "square_overlap, failure_tolerance, expected_num_shots",
    [
        (0.9, 0.1, 1),
        (0.8, 0.1, 2),
    ],
)
def test_get_num_shots(square_overlap, failure_tolerance, expected_num_shots):
    assert (
        get_num_shots(
            square_overlap=square_overlap, failure_tolerance=failure_tolerance
        )
        == expected_num_shots
    )


@pytest.mark.parametrize(
    "failure_tolerance, num_shots, expected_failure_tolerance_per_shot",
    [
        (0.1, 1, 0.1),
        (7 / 16, 2, 1 / 4),
    ],
)
def test_get_failure_tolerance_per_shot(
    failure_tolerance, num_shots, expected_failure_tolerance_per_shot
):
    assert np.isclose(
        get_failure_tolerance_per_shot(
            failure_tolerance=failure_tolerance, num_shots=num_shots
        ),
        expected_failure_tolerance_per_shot,
    )


def test_get_df_qpe_circuit():
    fci = fcidump.read(
        filename=os.path.join(os.path.dirname(__file__), "fcidump.h2_sto-3g")
    )
    square_overlap = 0.8
    failure_tolerance = 1e-2
    error_tolerance = 1.6e-3
    circuit, num_shots, allowable_error = get_df_qpe_circuit(
        fci=fci,
        square_overlap=square_overlap,
        error_tolerance=error_tolerance,
        failure_tolerance=failure_tolerance,
        df_threshold=1e-3,
    )
    assert (1 - square_overlap) ** num_shots < failure_tolerance
