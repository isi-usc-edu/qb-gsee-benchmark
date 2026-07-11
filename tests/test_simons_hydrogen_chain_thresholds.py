from copy import deepcopy

import pytest

from scripts.generate_simons_hydrogen_chain_thresholds import (
    EXPECTED_COUNTS,
    THRESHOLDS_HARTREE,
    apply_thresholds,
)


def test_apply_thresholds_uses_o5_size_classes() -> None:
    tasks = []
    for size, count in EXPECTED_COUNTS.items():
        tasks.extend(
            {
                "task_uuid": f"h{size}-{index}",
                "independent_parameters": {"n_hydrogen": size},
                "requirements": {
                    "absolute_accuracy_threshold": 99.0,
                    "absolute_accuracy_threshold_energy_units": "Hartree",
                },
            }
            for index in range(count)
        )
    payload = {"short_name": "simons_hydrogen_chains", "tasks": tasks}

    assert apply_thresholds(payload) == EXPECTED_COUNTS
    assert all(
        task["requirements"]["absolute_accuracy_threshold"]
        == THRESHOLDS_HARTREE[task["independent_parameters"]["n_hydrogen"]]
        for task in payload["tasks"]
    )


def test_apply_thresholds_rejects_unknown_size() -> None:
    payload = {
        "short_name": "simons_hydrogen_chains",
        "tasks": [
            {
                "task_uuid": "h70",
                "independent_parameters": {"n_hydrogen": 70},
                "requirements": {},
            }
        ],
    }

    with pytest.raises(ValueError, match="unsupported H-chain size"):
        apply_thresholds(deepcopy(payload))
