from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.ml.core_set import sha256_file


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis/ml10_instance_space"
FINAL = ANALYSIS / "final_v3"


def test_gao_instance_revision_is_recursively_identical_and_hashed() -> None:
    identity = json.loads((ANALYSIS / "two_run_identity_v3.json").read_text())
    assert identity["status"] == "pass"
    assert identity["byte_identical"] is True
    assert identity["file_count"] == 15
    for name in identity["relative_paths"]:
        first = ANALYSIS / "gao_raw_runs_v3/run_1" / name
        second = ANALYSIS / "gao_raw_runs_v3/run_2" / name
        promoted = FINAL / name
        assert first.read_bytes() == second.read_bytes() == promoted.read_bytes()
        assert sha256_file(promoted) == identity["file_hashes"][name]
    assert sha256_file(FINAL / "artifact_manifest.json") == (
        identity["promoted_bundle_manifest_sha256"]
    )


def test_gao_instance_revision_reports_complete_coverage_and_caveats() -> None:
    report = json.loads((FINAL / "report.json").read_text())
    assert report["artifact_id"] == "ml10a_instance_space_report_v3"
    assert report["projection_refit"] is False
    assert report["covered_panel_tasks"] == report["panel_tasks"] == 96
    assert report["covered_corpus_tasks"] == report["corpus_tasks"] == 718
    assert report["panel_pythia_gates_passed"] == 2
    assert report["panel_pythia_gates_total"] == 6
    assert report["external_validation_gates_passed"] == 0
    assert report["external_validation_gates_total"] == 5
    assert report["validated_predictor_claim"] is False
    assert report["ccsd_t_known_panel_solves"] == 33
    assert report["pyscf_unique_additions_beyond_ladder"] == 0
    assert report["ladder_plus_pyscf_known_panel_solves"] == 77
    assert report["bootstrap_replicates"] == 2000
    draws = pd.read_csv(FINAL / "bootstrap_draws.csv")
    intervals = pd.read_csv(FINAL / "bootstrap_intervals.csv")
    assert len(draws) == 12_000
    assert draws["replicate"].nunique() == 2_000
    assert len(intervals) == 30


def test_gao_instance_revision_preserves_prior_tree_and_vocabulary() -> None:
    assert sha256_file(
        ANALYSIS / "final_v2/artifact_manifest.json"
    ) == "43523e5bcb4b1c391f0752cca115bb092c4991eda11317a9fb220f97f2a4527c"
    prohibited = "lega" + "cy"
    for directory in (
        ANALYSIS / "gao_raw_runs_v3/run_1",
        ANALYSIS / "gao_raw_runs_v3/run_2",
        FINAL,
    ):
        for path in directory.iterdir():
            if path.is_file():
                assert prohibited.encode() not in path.read_bytes().lower()
