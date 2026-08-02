from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml import grouped_inference_run as grouped_module
from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.grouped_inference_run import (
    FittedComparison,
    PreparedInference,
    TARGET_GATE_DECOUPLING_SHA256,
    _benjamini_hochberg,
    _binary_folds,
    _bootstrap_indices,
    _score_comparisons,
    prepare_inference,
    run_grouped_inference,
    verify_target_gate,
)


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_grouped_inference/preregistration.json"
EXECUTION_CONTRACT = ROOT / "analysis/ml9_grouped_inference/execution_contract_v1.json"
TARGET_GATE_DECOUPLING = (
    ROOT / "analysis/ml9_grouped_inference/target_gate_decoupling_v4.json"
)
RAW_RUNS = ROOT / "analysis/ml9_grouped_inference/raw_runs"
FINAL = ROOT / "analysis/ml9_grouped_inference/final_v1"
IDENTITY = ROOT / "analysis/ml9_grouped_inference/two_run_identity_v1.json"


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


def test_ml9d_target_gate_decoupling_is_frozen_before_target_access() -> None:
    payload = json.loads(TARGET_GATE_DECOUPLING.read_text(encoding="utf-8"))
    assert sha256_file(TARGET_GATE_DECOUPLING) == TARGET_GATE_DECOUPLING_SHA256
    assert payload["frozen_before_target_access"] is True
    assert payload["scientific_targets_consumed"] is False
    assert payload["target_dependent_model_fitted"] is False
    for path_key, hash_key in [
        (
            "prior_target_gate_supersession_path",
            "prior_target_gate_supersession_sha256",
        ),
        ("execution_contract_path", "execution_contract_sha256"),
        ("preregistration_path", "preregistration_sha256"),
        (
            "outcome_blind_preflight_manifest_path",
            "outcome_blind_preflight_manifest_sha256",
        ),
        (
            "ml9c_primary_promotion_amendment_path",
            "ml9c_primary_promotion_amendment_sha256",
        ),
    ]:
        assert sha256_file(ROOT / payload[path_key]) == payload[hash_key]


def test_ml9d_gate_opens_without_parsing_targets(monkeypatch) -> None:
    def forbidden_read_csv(*args, **kwargs):
        raise AssertionError("ML-9D gate verification must precede target parsing")

    monkeypatch.setattr(pd, "read_csv", forbidden_read_csv)
    evidence = verify_target_gate(ROOT, PREREGISTRATION, EXECUTION_CONTRACT)
    assert evidence["status"] == "pass_target_access_authorized"
    assert evidence["primary_target_access_authorized"] is True
    assert evidence["secondary_target_access_authorized"] is True
    assert evidence["retained_raw_handoff_used"] is False
    assert evidence["factor_artifact_used"] is False


def test_ml9d_real_targets_prepare_after_gate() -> None:
    prepared = prepare_inference(ROOT, PREREGISTRATION, EXECUTION_CONTRACT)
    assert prepared.features.shape == (96, 193)
    assert prepared.primary_target.shape == (96,)
    assert set(prepared.binary_targets) == {"dmrg", "ipie_afqmc", "shci", "trimci"}
    assert all(values.shape == (96,) for values in prepared.binary_targets.values())
    assert prepared.gate_evidence["status"] == "pass_target_access_authorized"


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


def test_ml9d_synthetic_full_pipeline_is_deterministic(
    tmp_path: Path, monkeypatch
) -> None:
    rng = np.random.default_rng(20260801)
    groups = np.repeat(np.array([f"family_{index}" for index in range(10)]), 3)
    features = rng.normal(size=(30, 8))
    binary = np.tile(np.array([False, True, False]), 10)
    contrasts = tuple(
        {
            "order": index,
            "contrast_id": f"C{index}",
            "anchor": f"feature_{index + 1}",
            "group_id": f"G{index}",
            "group_name": f"synthetic_group_{index}",
            "indices": np.array([index + 1], dtype=int),
        }
        for index in range(1, 6)
    )
    prepared = PreparedInference(
        task_ids=tuple(f"task_{index:02d}" for index in range(30)),
        canonical_families=groups,
        features=features,
        feature_names=tuple(f"feature_{index}" for index in range(8)),
        baseline_indices=np.array([0, 1], dtype=int),
        contrasts=contrasts,
        primary_target=features[:, 2] + 0.2 * features[:, 0],
        binary_targets={
            family: binary.copy() for family in grouped_module.FAMILY_TARGETS
        },
        gate_evidence={
            "artifact_id": "synthetic_ml9d_target_gate_evidence",
            "status": "pass_target_access_authorized",
            "primary_target_access_authorized": True,
            "secondary_target_access_authorized": True,
            "retained_raw_handoff_used": False,
        },
    )
    monkeypatch.setattr(grouped_module, "prepare_inference", lambda *args: prepared)

    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    preregistration = deepcopy(preregistration)
    preregistration["inference"]["primary_estimator"]["n_estimators"] = 5
    preregistration["inference"]["secondary_estimator"]["n_estimators"] = 5
    contract = json.loads(EXECUTION_CONTRACT.read_text(encoding="utf-8"))
    contract = deepcopy(contract)
    contract["execution"]["bootstrap_draws"] = 20
    contract["execution"]["randomization_draws"] = 31
    synthetic_preregistration = tmp_path / "preregistration.json"
    synthetic_contract = tmp_path / "execution_contract.json"
    synthetic_preregistration.write_text(
        json.dumps(preregistration, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    synthetic_contract.write_text(
        json.dumps(contract, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    first = tmp_path / "run_1"
    second = tmp_path / "run_2"
    report = run_grouped_inference(
        ROOT, synthetic_preregistration, synthetic_contract, first
    )
    repeated = run_grouped_inference(
        ROOT, synthetic_preregistration, synthetic_contract, second
    )
    assert report == repeated
    assert report["panel_tasks"] == 30
    assert report["prespecified_contrasts"] == 5
    assert report["continuous_gradeable_contrasts"] == 5
    assert report["binary_gradeable_contrasts"] == 20
    assert report["bootstrap_replicates"] == 20
    assert report["randomization_draws"] == 31

    required = set(contract["outputs"]["required_files"])
    first_files = {path.name: path.read_bytes() for path in first.iterdir()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir()}
    assert set(first_files) == required
    assert first_files == second_files
    assert len(pd.read_csv(first / "contrast_estimates.csv")) == 50
    assert len(pd.read_csv(first / "fold_assignments.csv")) == 150
    manifest = json.loads((first / "artifact_manifest.json").read_text())
    assert manifest["status"] == "complete_internal_descriptive_inference"
    assert manifest["target_gate_status"] == "pass_target_access_authorized"
    promoted_manifest = json.loads((FINAL / "artifact_manifest.json").read_text())
    assert promoted_manifest["status"] == "complete_internal_descriptive_inference"


def test_ml9d_promoted_runs_are_byte_identical_and_hashed() -> None:
    identity = json.loads(IDENTITY.read_text(encoding="utf-8"))
    assert identity["status"] == "pass"
    assert identity["byte_identical"] is True
    assert identity["target_gate_passed"] is True
    assert identity["file_count"] == 14
    assert identity["promoted"] == "analysis/ml9_grouped_inference/final_v1"
    for name, expected_hash in identity["file_hashes"].items():
        assert sha256_file(RAW_RUNS / "run_1" / name) == expected_hash
        assert sha256_file(RAW_RUNS / "run_2" / name) == expected_hash
        assert sha256_file(FINAL / name) == expected_hash


def test_ml9d_promoted_results_record_the_negative_verdict() -> None:
    report = json.loads((FINAL / "report.json").read_text(encoding="utf-8"))
    assert report["status"] == "complete_internal_descriptive_inference"
    assert report["bh_rejections_primary"] == 0
    assert report["bh_rejections_secondary"] == 0
    assert report["continuous_gradeable_contrasts"] == 5
    assert report["binary_gradeable_contrasts"] == 15
    assert report["stored_targets_or_labels_mutated"] is False
    assert report["new_solver_runs"] is False

    estimates = pd.read_csv(FINAL / "contrast_estimates.csv")
    dmrg = estimates.loc[estimates["target"].eq("dmrg")]
    assert len(dmrg) == 10
    assert not dmrg["gradeable"].any()
    assert set(dmrg["status"]) == {"non_gradeable_degenerate_binary_fold"}
    multiplicity = pd.read_csv(FINAL / "multiplicity_results.csv")
    assert multiplicity["reject_zero_positive_importance"].eq(True).sum() == 0
