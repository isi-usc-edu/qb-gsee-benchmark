from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.ml.pyscf_hardness_labels import prepare_pyscf_data
from qb_gsee_benchmark.ml.pyscf_hardness_run import (
    run_desk_finalization,
    run_resource_finalization,
)


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml10_pyscf_hardness/preregistration.json"


def test_ml10_pyscf_label_construction_is_sparse_and_pinned() -> None:
    data = prepare_pyscf_data(ROOT, PREREGISTRATION)
    labels = data.labels
    assert len(labels) == 3590
    assert int(labels["response_observed"].sum()) == 2054
    assert int(labels["solvable"].eq(True).sum()) == 384
    assert Counter(labels["label_reason"]) == {
        "completed_outside_threshold": 1228,
        "no_pyscf_coverage": 635,
        "not_attempted_cost_screened": 509,
        "attempted_failure": 442,
        "not_gradeable": 392,
        "completed_within_threshold": 384,
    }
    summary = labels.groupby("item_id").agg(
        observed=("response_observed", "sum"),
        solved=("solvable", lambda values: int(values.eq(True).sum())),
    )
    assert summary.to_dict(orient="index") == {
        "pyscf_ccsd": {"observed": 387, "solved": 116},
        "pyscf_ccsd_t": {"observed": 372, "solved": 162},
        "pyscf_cisd": {"observed": 387, "solved": 61},
        "pyscf_hf": {"observed": 452, "solved": 10},
        "pyscf_mp2": {"observed": 456, "solved": 35},
    }


def test_ml10b_resource_finalization_is_deterministic_and_extends_base(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = run_resource_finalization(ROOT, PREREGISTRATION, first)
    repeated = run_resource_finalization(ROOT, PREREGISTRATION, second)
    assert report == repeated
    assert report["combined_items"] == 23
    assert report["pyscf_panel_attempted_cells"] == 357
    assert report["pyscf_panel_cost_screened_cells"] == 103
    assert report["pyscf_panel_no_coverage_cells"] == 20
    assert report["pyscf_primary_runstatus_counts"] == {
        "accuracy_miss": 215,
        "crash": 60,
        "ok": 82,
    }
    assert report["pyscf_primary_endpoint_counts"] == {
        "competing_risk_failure": 60,
        "no_pyscf_coverage": 20,
        "not_attempted_cost_screened": 103,
        "right_censored_ladder_exhaustion": 215,
        "solution": 82,
    }
    assert {
        path.name: path.read_bytes() for path in first.iterdir() if path.is_file()
    } == {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}
    base = ROOT / "analysis/ml9_resource_profiles/final_v1"
    for name in (
        "attempt_coverage.csv",
        "runstatus.csv",
        "resource_to_solution.csv",
        "data_profiles.csv",
        "threshold_stability.csv",
        "conditional_resource_quantiles.csv",
    ):
        assert (first / name).read_bytes().startswith((base / name).read_bytes())
    assert (first / "companion_variants.csv").read_bytes() == (
        base / "companion_variants.csv"
    ).read_bytes()


def test_ml10d_desk_finalization_is_deterministic_and_missingness_bounded(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = run_desk_finalization(ROOT, PREREGISTRATION, first)
    repeated = run_desk_finalization(ROOT, PREREGISTRATION, second)
    assert report == repeated
    assert report["pyscf_known_union_successes"] == 34
    assert report["pyscf_union_unique_additions_beyond_ladder"] == 0
    assert report["partial_identification_bounds_reported"] is True
    assert report["missing_imputed"] is False
    assert {
        path.name: path.read_bytes() for path in first.iterdir() if path.is_file()
    } == {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}
    ratios = pd.read_csv(first / "design_based_ratios.csv")
    assert len(ratios) == 5
    assert (ratios["design_lower_bound"] <= ratios["design_upper_bound"]).all()
    assert not ratios["missing_imputed"].any()
    corpus = pd.read_csv(first / "corpus_near_census_rates.csv")
    assert set(corpus["gradeable_covered_tasks"]) == {486}
    assert (
        corpus["near_census_lower_bound"] <= corpus["near_census_upper_bound"]
    ).all()


def test_ml10_outcome_stage_new_files_avoid_prohibited_word() -> None:
    prohibited = "lega" + "cy"
    paths = [
        ROOT / "src/qb_gsee_benchmark/ml/pyscf_hardness_labels.py",
        ROOT / "src/qb_gsee_benchmark/ml/pyscf_hardness_run.py",
        ROOT / "analysis/ml10_resource_profiles/run_finalization.py",
        ROOT / "analysis/ml10_resource_profiles/verify_two_runs.py",
        ROOT / "analysis/ml10_pyscf_desk/run_finalization.py",
        ROOT / "analysis/ml10_pyscf_desk/verify_two_runs.py",
        Path(__file__),
    ]
    for path in paths:
        assert prohibited not in path.read_text(encoding="utf-8").lower()
