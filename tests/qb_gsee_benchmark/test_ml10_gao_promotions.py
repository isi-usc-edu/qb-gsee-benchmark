from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.ml.core_set import sha256_file


ROOT = Path(__file__).resolve().parents[2]


def _assert_identity(
    analysis: Path, raw_name: str, final_name: str, identity_name: str
) -> dict:
    identity = json.loads((analysis / identity_name).read_text())
    assert identity["status"] == "pass"
    assert identity["byte_identical"] is True
    first = analysis / raw_name / "run_1"
    second = analysis / raw_name / "run_2"
    final = analysis / final_name
    for name in identity["relative_paths"]:
        assert (
            (first / name).read_bytes()
            == (second / name).read_bytes()
            == (final / name).read_bytes()
        )
        assert sha256_file(final / name) == identity["file_hashes"][name]
    return identity


def test_gao_desk_revision_is_exact_and_scoped() -> None:
    analysis = ROOT / "analysis/ml10_pyscf_desk"
    identity = _assert_identity(
        analysis, "gao_raw_runs_v2", "final_v2", "two_run_identity_v2.json"
    )
    assert identity["file_count"] == 9
    report = json.loads((analysis / "final_v2/report.json").read_text())
    assert report["artifact_id"] == "ml10d_pyscf_desk_report_v2"
    assert report["pyscf_known_union_successes"] == 38
    assert report["pyscf_union_unique_additions_beyond_ladder"] == 0
    rates = pd.read_csv(analysis / "final_v2/corpus_near_census_rates.csv")
    assert set(rates["gradeable_covered_tasks"]) == {609}
    labels = pd.read_csv(analysis / "final_v2/pyscf_labels.csv")
    assert int(labels["in_gao_extension"].sum()) == 635
    assert labels["in_accepted_campaign_union"].all()


def test_gao_resource_revision_is_exact_and_scoped() -> None:
    analysis = ROOT / "analysis/ml10_resource_profiles"
    identity = _assert_identity(
        analysis, "gao_raw_runs_v3", "final_v3", "two_run_identity_v3.json"
    )
    assert identity["file_count"] == 13
    report = json.loads((analysis / "final_v3/report.json").read_text())
    assert report["artifact_id"] == "ml10b_resource_profiles_report_v3"
    assert report["pyscf_panel_attempted_cells"] == 377
    assert report["pyscf_panel_cost_screened_cells"] == 103
    assert report["pyscf_panel_no_coverage_cells"] == 0
    assert report["pyscf_primary_endpoint_counts"] == {
        "competing_risk_failure": 60,
        "not_attempted_cost_screened": 103,
        "right_censored_ladder_exhaustion": 227,
        "solution": 90,
    }


def test_gao_revision_preserves_prior_manifests() -> None:
    expected = {
        "analysis/ml10_pyscf_desk/final_v1/artifact_manifest.json": (
            "ce6237083150ebd0e05b862f7375cfd538769812028d1c4bffa675099e5b35cc"
        ),
        "analysis/ml10_resource_profiles/final_v2/artifact_manifest.json": (
            "449073424c01fb2b898f9aecc9988e6f6c87eb0874797e716b46c575f8c604b9"
        ),
        "analysis/ml10_instance_space/final_v2/artifact_manifest.json": (
            "43523e5bcb4b1c391f0752cca115bb092c4991eda11317a9fb220f97f2a4527c"
        ),
    }
    for relative, digest in expected.items():
        assert sha256_file(ROOT / relative) == digest


def test_gao_revision_sources_avoid_prohibited_term() -> None:
    prohibited = "lega" + "cy"
    paths = [
        ROOT / "src/qb_gsee_benchmark/ml/pyscf_gao_delta.py",
        ROOT / "analysis/ml10_gao_coverage_delta/run_desk.py",
        ROOT / "analysis/ml10_gao_coverage_delta/run_resource.py",
        ROOT / "analysis/ml10_gao_coverage_delta/run_instance_space.py",
        ROOT / "analysis/ml10_gao_coverage_delta/verify_revision.py",
        ROOT / "pbs/ml10a_gao_instance_space_v3.pbs",
        Path(__file__),
    ]
    for path in paths:
        assert prohibited.encode() not in path.read_bytes().lower()
