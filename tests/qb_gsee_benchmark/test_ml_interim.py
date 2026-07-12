import numpy as np
import pandas as pd
import pytest

from qb_gsee_benchmark.ml.interim import (
    MODEL_LABELS,
    family_balanced_scores,
    feature_contract,
    stratum_status,
)


def _metadata(columns):
    return pd.DataFrame([
        {
            "column": column,
            "model_eligible": True,
            "provenance_tier": "T0",
            "role": "accuracy",
            "implementation_status": "current",
        }
        for column in columns
    ])


def test_feature_contract_requires_and_maps_universal_blocks():
    columns = [
        "task_uuid", "n_elec", "n_orbs", "log_fci_dim",
        "fermionic_coefficient_l1_norm", "interaction_spectrum_effective_rank",
        "det_coupling_scale", "cut_weight_best_max", "narrow_feature",
    ]
    metadata = _metadata(columns)
    metadata.loc[metadata.column == "task_uuid", ["model_eligible", "role"]] = [
        False, "audit-only",
    ]
    features = pd.DataFrame([
        {column: float(index + 1) for column in columns if column != "task_uuid"}
        | {"task_uuid": f"task-{index}"}
        for index in range(3)
    ])
    features.loc[2, "narrow_feature"] = np.nan
    contract = feature_contract(features, metadata)
    assert contract["universal_core"]["n_columns"] == 7
    assert set(contract["universal_core"]["blocks"]) == {
        "a_size_dimension", "b_coefficient_sparsity",
        "c_two_electron_spectrum", "d_determinant_coupling",
        "e_orderability_mpo",
    }
    assert contract["domain_extensions"][0]["columns"] == ["narrow_feature"]
    assert contract["screen_counts"]["model_eligible_false_dropped"] == 1


def test_family_balanced_scores_use_all_three_labels():
    data = pd.DataFrame({
        "outcome": list(MODEL_LABELS),
        "family": ["large", "large", "small"],
    })
    scores = family_balanced_scores(data, np.eye(3))
    assert scores["brier"] == pytest.approx(0.0)
    assert scores["log_loss"] == pytest.approx(0.0)
    assert scores["average_precision"] == pytest.approx(1.0)


def test_stratum_floor_is_explicit():
    data = pd.DataFrame({
        "outcome": ["success", "miss", "indeterminate"] * 2,
        "family": ["a", "b", "c"] * 2,
    })
    status, evidence = stratum_status(data)
    assert status == "insufficient_data"
    assert evidence["n_tasks"] == 6
