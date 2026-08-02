from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.ml.core_set import sha256_file


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis/ml10_instance_space"
FINAL = ANALYSIS / "final_v2"


def test_ml10a_promoted_tree_is_recursively_identical_and_hashed() -> None:
    identity = json.loads((ANALYSIS / "two_run_identity_v2.json").read_text())
    assert identity["status"] == "pass"
    assert identity["byte_identical"] is True
    assert identity["file_count"] == 15
    for name in identity["relative_paths"]:
        promoted = FINAL / name
        first = ANALYSIS / "raw_runs/run_1" / name
        second = ANALYSIS / "raw_runs/run_2" / name
        assert promoted.read_bytes() == first.read_bytes() == second.read_bytes()
        assert sha256_file(promoted) == identity["file_hashes"][name]
    assert sha256_file(FINAL / "artifact_manifest.json") == (
        identity["promoted_bundle_manifest_sha256"]
    )


def test_ml10a_promoted_result_retains_failed_gates_as_caveats() -> None:
    report = json.loads((FINAL / "report.json").read_text())
    assert report["projection_refit"] is False
    assert report["panel_pythia_gates_passed"] == 1
    assert report["panel_pythia_gates_total"] == 6
    assert report["external_validation_gates_passed"] == 0
    assert report["external_validation_gates_total"] == 5
    assert report["validated_predictor_claim"] is False
    assert report["ccsd_t_known_panel_solves"] == 29
    assert report["pyscf_unique_additions_beyond_ladder"] == 0
    assert report["ladder_plus_pyscf_known_panel_solves"] == 77
    assert report["missing_imputed"] is False
    draws = pd.read_csv(FINAL / "bootstrap_draws.csv")
    intervals = pd.read_csv(FINAL / "bootstrap_intervals.csv")
    assert len(draws) == 6 * 2000
    assert draws["replicate"].nunique() == 2000
    assert len(intervals) == 30


def test_ml10a_promoted_files_avoid_prohibited_term() -> None:
    prohibited = "lega" + "cy"
    for path in FINAL.iterdir():
        if path.is_file():
            assert prohibited.encode() not in path.read_bytes().lower()
