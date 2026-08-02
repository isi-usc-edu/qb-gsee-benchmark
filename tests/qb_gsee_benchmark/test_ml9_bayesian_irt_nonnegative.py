from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pymc as pm

from qb_gsee_benchmark.ml.bayesian_irt_nonnegative import nonnegative_factor_model
from qb_gsee_benchmark.ml.bayesian_irt_recovery import (
    factor_transform,
    verify_recovery_preregistration,
)
from qb_gsee_benchmark.ml.bayesian_irt_run import prepare_irt_data
from qb_gsee_benchmark.ml.core_set import sha256_file


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_bayesian_irt/recovery_preregistration_v3.json"
RAW_RUNS = ROOT / "analysis/ml9_bayesian_irt/recovery_raw_runs_v3"
RETAINED_IDENTITY = ROOT / "analysis/ml9_bayesian_irt/two_run_identity_retained_v3.json"


def test_ml9c_v3_preregistration_is_frozen_and_pinned() -> None:
    payload = verify_recovery_preregistration(ROOT, PREREGISTRATION)
    assert payload["artifact_id"] == "ml9c_nonnegative_recovery_preregistration_v3"
    assert payload["frozen_before_recovery_fit"] is True
    assert (
        payload["identified_factor_models"]["loading_sign_constraint"]
        == "all_free_loading_elements_are_nonnegative"
    )
    sampling = payload["exact_cross_validation"]["fit_sampling"]
    assert (sampling["tune"], sampling["draws"], sampling["target_accept"]) == (
        2000,
        2000,
        0.99,
    )
    final_manifest = json.loads(
        (ROOT / "analysis/ml9_bayesian_irt/final_v1/artifact_manifest.json").read_text()
    )
    assert final_manifest["scope"] == (
        "family_aware_binary_rasch_task_difficulty_posterior_only"
    )
    assert final_manifest["factor_artifacts_included"] is False


def test_ml9c_v3_factor_graph_is_nonnegative_with_pure_markers() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    data = prepare_irt_data(ROOT, ROOT / payload["original_preregistration"]["path"])
    training = np.arange(12)
    transform = factor_transform(data.logit_quality, training)
    model = nonnegative_factor_model(
        transform.standardized[training],
        data.variant_ids,
        tuple(data.task_ids[index] for index in training),
        factors=2,
    )
    with model:
        prior = pm.sample_prior_predictive(draws=5, random_seed=20260801)
    loading = np.asarray(prior.prior["factor_loading"])
    assert loading.shape == (1, 5, 18, 2)
    assert np.all(loading >= 0.0)
    cpu_anchor = data.variant_ids.index("g50_bond_dimension_2048")
    ipie_anchor = data.variant_ids.index("uhf_trial_512_walkers_1000_blocks")
    assert np.all(loading[..., cpu_anchor, 1] == 0.0)
    assert np.all(loading[..., ipie_anchor, 0] == 0.0)


def test_ml9c_v3_failed_cv_is_identical_and_not_jointly_promoted() -> None:
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    required = set(preregistration["outputs"]["required_files"])
    identity = json.loads(RETAINED_IDENTITY.read_text(encoding="utf-8"))
    assert identity["status"] == "pass_retained_not_promoted"
    assert identity["byte_identical"] is True
    assert identity["promoted"] is False
    assert identity["file_count"] == 18
    assert set(identity["relative_paths"]) == required
    assert not (ROOT / "analysis/ml9_bayesian_irt/two_run_identity_v3.json").exists()
    for name, expected_hash in identity["file_hashes"].items():
        first = RAW_RUNS / "run_1" / name
        second = RAW_RUNS / "run_2" / name
        assert first.read_bytes() == second.read_bytes()
        assert sha256_file(first) == expected_hash

    posterior = pd.read_csv(RAW_RUNS / "run_1/posterior_diagnostics.csv")
    assert posterior["passed"].all()
    cross_validation = pd.read_csv(RAW_RUNS / "run_1/cross_validation_diagnostics.csv")
    one_factor = cross_validation.loc[cross_validation["model"].eq("one_factor")]
    two_factor = cross_validation.loc[cross_validation["model"].eq("two_factor")]
    assert one_factor["passed"].tolist() == [True, True, False, True, True]
    assert not two_factor["passed"].any()

    report = json.loads((RAW_RUNS / "run_1/report.json").read_text(encoding="utf-8"))
    assert report["status"] == "retained_internal_recovery_diagnostic_failure"
    assert report["all_recovery_diagnostics_pass"] is False
    assert report["dimensionality_comparison"]["reliable"] is False
    assert report["named_ipie_axis_hypothesis_supported"] is False
