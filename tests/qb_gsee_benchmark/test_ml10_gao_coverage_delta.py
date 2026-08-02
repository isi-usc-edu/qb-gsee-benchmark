from __future__ import annotations

import json
from pathlib import Path

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.pyscf_gao_delta import (
    DELTA_CENSUS_COLUMNS,
    run_gao_delta_preflight,
    verify_delta_preregistration,
)


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "analysis/ml10_gao_coverage_delta"
PREREGISTRATION = ANALYSIS / "preregistration.json"


def test_gao_delta_preregistration_is_frozen_and_pinned() -> None:
    payload, _, hashes, order_hash = verify_delta_preregistration(
        ROOT, PREREGISTRATION
    )
    assert payload["frozen_before_gao_result_rows_parsed"] is True
    assert payload["known_aggregate_disclosure_before_freeze"][
        "row_level_results_inspected"
    ] is False
    assert hashes["accepted_gao_inputs.results"] == (
        "ef4aad1142390e4d7ce18aaddda78ba272687c5a5562c1e3c59f97c6c3b5a98d"
    )
    assert order_hash == payload["order"]["section_sha256"]
    assert payload["instance_space"]["projection_refit"] is False
    assert payload["excluded"]["ml10c_update"] is True


def test_gao_status_preflight_is_deterministic_and_outcome_blind(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = run_gao_delta_preflight(ROOT, PREREGISTRATION, first)
    repeated = run_gao_delta_preflight(ROOT, PREREGISTRATION, second)
    assert report == repeated
    assert report["checks"]["energy_values_consumed"] is False
    assert report["checks"]["success_labels_computed"] is False
    assert report["census"]["covered_panel_tasks"] == 96
    assert report["census"]["covered_corpus_tasks"] == 718
    assert report["census"]["gao_delta_cells"] == 635
    assert report["census"]["coverage_counts"] == {
        "failed": 554,
        "labeled": 2527,
        "no_pyscf_coverage": 0,
        "not_attempted_cost_screened": 509,
    }
    assert {
        path.name: path.read_bytes() for path in first.iterdir() if path.is_file()
    } == {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}
    header = (first / "coverage_census.csv").read_text().splitlines()[0].split(",")
    assert header == DELTA_CENSUS_COLUMNS


def test_gao_delta_new_sources_avoid_prohibited_term() -> None:
    prohibited = "lega" + "cy"
    paths = [
        ROOT / "src/qb_gsee_benchmark/ml/pyscf_gao_delta.py",
        ANALYSIS / "AMENDMENT_ML10_GAO_COVERAGE_DELTA.md",
        ANALYSIS / "preregistration.json",
        ANALYSIS / "run_preflight.py",
        ANALYSIS / "verify_preflight.py",
        Path(__file__),
    ]
    for path in paths:
        assert prohibited.encode() not in path.read_bytes().lower()
