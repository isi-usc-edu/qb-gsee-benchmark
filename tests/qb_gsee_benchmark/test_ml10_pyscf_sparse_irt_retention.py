from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.pyscf_sparse_irt_artifacts import REQUIRED_FILES


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis/ml10_bayesian_irt"
RAW = ANALYSIS / "raw_runs"


def test_ml10c_failed_health_gate_is_byte_identical_and_not_promoted() -> None:
    identity = json.loads((ANALYSIS / "two_run_identity_v1.json").read_text())
    assert identity["status"] == "pass_nonpromotion_diagnostic_failure"
    assert identity["byte_identical"] is True
    assert identity["file_count"] == 17
    assert set(identity["relative_paths"]) == set(REQUIRED_FILES)
    assert identity["promotion_eligible"] is False
    assert identity["promotion_performed"] is False
    assert identity["promoted"] is None
    assert not (ANALYSIS / "final_v1").exists()
    for name, expected_hash in identity["file_hashes"].items():
        first = RAW / "run_1" / name
        second = RAW / "run_2" / name
        assert first.read_bytes() == second.read_bytes()
        assert sha256_file(first) == expected_hash


def test_ml10c_diagnostics_force_the_preregistered_nonpromotion() -> None:
    posterior = pd.read_csv(RAW / "run_1/posterior_diagnostics.csv")
    passed = dict(zip(posterior["model"], posterior["passed"]))
    assert passed == {
        "binary_rasch": True,
        "continuous_beta": False,
        "one_factor": True,
        "two_factor": False,
    }
    beta = posterior.loc[posterior["model"].eq("continuous_beta")]
    assert int(beta["divergences"].iloc[0]) == 1
    cross_validation = pd.read_csv(RAW / "run_1/cross_validation_diagnostics.csv")
    assert cross_validation.loc[
        cross_validation["model"].eq("one_factor"), "passed"
    ].all()
    assert not cross_validation.loc[
        cross_validation["model"].eq("two_factor"), "passed"
    ].any()
    report = json.loads((RAW / "run_1/report.json").read_text())
    assert report["status"] == "retained_internal_diagnostic_failure"
    assert report["all_sampler_diagnostics_pass"] is False
    assert report["dimensionality_comparison"]["reliable"] is False
    assert (
        report["named_single_reference_multireference_hypothesis_supported"]
        is False
    )
    assert report["observed_response_cells"] == 2085
    assert report["missing_response_cells"] == 123


def test_ml10c_retained_files_avoid_prohibited_term() -> None:
    prohibited = "lega" + "cy"
    for directory in (RAW / "run_1", RAW / "run_2"):
        for path in directory.iterdir():
            if path.is_file():
                assert prohibited.encode() not in path.read_bytes().lower()
