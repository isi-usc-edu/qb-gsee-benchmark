from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.grouped_inference_run import (
    FittedComparison,
    _benjamini_hochberg,
    _binary_folds,
    _bootstrap_indices,
    _score_comparisons,
    verify_target_gate,
)


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_grouped_inference/preregistration.json"
EXECUTION_CONTRACT = ROOT / "analysis/ml9_grouped_inference/execution_contract_v1.json"
TARGET_GATE_SUPERSESSION = (
    ROOT / "analysis/ml9_grouped_inference/target_gate_supersession_v3.json"
)


def test_ml9d_execution_contract_is_frozen_before_target_access() -> None:
    payload = json.loads(EXECUTION_CONTRACT.read_text(encoding="utf-8"))
    assert payload["frozen_before_target_access"] is True
    assert payload["execution"]["bootstrap_draws"] == 2000
    assert payload["execution"]["randomization_draws"] == 9999
    assert len(payload["outputs"]["required_files"]) == 14
    for path_key, hash_key in [
        ("preregistration_path", "preregistration_sha256"),
        ("target_gate_amendment_path", "target_gate_amendment_sha256"),
        (
            "outcome_blind_preflight_manifest_path",
            "outcome_blind_preflight_manifest_sha256",
        ),
    ]:
        assert sha256_file(ROOT / payload[path_key]) == payload[hash_key]


def test_ml9d_target_gate_supersession_is_frozen_before_target_access() -> None:
    payload = json.loads(TARGET_GATE_SUPERSESSION.read_text(encoding="utf-8"))
    assert payload["frozen_before_target_access"] is True
    assert payload["scientific_targets_consumed"] is False
    assert payload["model_fitted"] is False
    for path_key, hash_key in [
        (
            "prior_target_gate_amendment_path",
            "prior_target_gate_amendment_sha256",
        ),
        ("execution_contract_path", "execution_contract_sha256"),
        ("recovery_preregistration_path", "recovery_preregistration_sha256"),
    ]:
        assert sha256_file(ROOT / payload[path_key]) == payload[hash_key]


def test_ml9d_gate_stops_before_parsing_targets(monkeypatch) -> None:
    def forbidden_read_csv(*args, **kwargs):
        raise AssertionError("ML-9D gate failure must precede target parsing")

    monkeypatch.setattr(pd, "read_csv", forbidden_read_csv)
    try:
        verify_target_gate(ROOT, PREREGISTRATION, EXECUTION_CONTRACT)
    except ValueError as error:
        assert "promoted handoff is unavailable" in str(error)
    else:
        raise AssertionError("ML-9D gate unexpectedly opened")


def test_ml9d_binary_folds_keep_groups_intact() -> None:
    groups = np.repeat(np.array([f"g{i}" for i in range(10)]), 2)
    labels = np.tile(np.array([False, True]), 10)
    folds, gradeable = _binary_folds(labels, groups, 5, 20260731)
    assert gradeable
    assert set(folds) == set(range(5))
    for group in set(groups):
        assert len(set(folds[groups == group])) == 1


def test_ml9d_block_bootstrap_and_scoring_are_deterministic() -> None:
    groups = np.array(["a", "a", "b", "b", "c", "c"])
    first = _bootstrap_indices(groups, 20, 7)
    second = _bootstrap_indices(groups, 20, 7)
    assert all(np.array_equal(left, right) for left, right in zip(first, second))
    assert all(len(indices) == 6 for indices in first)

    observed = np.arange(6, dtype=float)
    comparison = FittedComparison(
        target_kind="continuous",
        target="task_difficulty",
        contrast_id="C1",
        contrast_group_id="G1",
        contrast_group_name="group",
        contrast_anchor="anchor",
        estimator="random_forest",
        baseline_feature_count=1,
        added_feature_count=1,
        observed=observed,
        baseline_prediction=observed + 1.0,
        augmented_prediction=observed + 0.5,
        folds=np.array([0, 0, 1, 1, 2, 2]),
        gradeable=True,
        status="estimated_internal_oof_comparison",
    )
    contract = {"execution": {"bootstrap_draws": 20, "bootstrap_seed": 7}}
    scored_1 = _score_comparisons([comparison], groups, contract)
    scored_2 = _score_comparisons([comparison], groups, contract)
    assert scored_1[0] == scored_2[0]
    assert scored_1[1] == scored_2[1]
    key = ("continuous", "task_difficulty", "random_forest", "C1")
    assert np.array_equal(scored_1[2][key], scored_2[2][key])


def test_ml9d_benjamini_hochberg_is_monotone_in_rank() -> None:
    adjusted = _benjamini_hochberg([0.01, 0.04, 0.03, 0.2])
    assert np.allclose(adjusted, [0.04, 0.05333333333333334, 0.05333333333333334, 0.2])
