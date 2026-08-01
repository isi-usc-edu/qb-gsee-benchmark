from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.ml.bayesian_irt import run_outcome_blind_preflight
from qb_gsee_benchmark.ml.core_set import sha256_file


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_bayesian_irt/preregistration.json"


def test_ml9c_preregistration_freezes_reduced_dependence_aware_models() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert payload["artifact_id"] == "ml9c_bayesian_inverted_irt_preregistration_v1"
    assert payload["frozen_before_response_construction"] is True
    assert payload["frozen_before_model_fit"] is True
    assert payload["population"]["respondent_orientation"] == "tasks"
    assert payload["population"]["item_orientation"] == "solver_variants"
    assert payload["population"]["complete_cells"] == 1_728
    assert payload["binary_rasch"]["free_item_discrimination"] is False
    assert payload["continuous_beta"]["free_item_discrimination"] is False
    assert payload["family_dependence"]["method"] == "testlet_style_random_effect"
    assert payload["solver_side_dimensionality"]["comparison"]["criterion"] == (
        "PSIS-LOO"
    )
    assert payload["fences"]["new_solver_runs"] is False
    assert payload["fences"]["label_changes"] is False


def test_ml9c_local_input_hashes_are_current() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    for specification in payload["inputs"].values():
        assert sha256_file(ROOT / specification["path"]) == specification["sha256"]


def test_ml9c_preflight_is_outcome_blind_and_deterministic(
    tmp_path: Path, monkeypatch
) -> None:
    original_read_csv = pd.read_csv

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path).name == "normalized_observations.csv":
            raise AssertionError("ML-9C preflight must not parse response rows")
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = run_outcome_blind_preflight(ROOT, PREREGISTRATION, first)
    repeated = run_outcome_blind_preflight(ROOT, PREREGISTRATION, second)
    assert report == repeated
    assert report["status"] == "pass"
    assert report["scientific_outcomes_consumed"] is False
    assert report["response_matrix_computed"] is False
    assert report["posterior_computed"] is False
    assert report["factor_model_computed"] is False
    assert report["loo_comparison_computed"] is False
    assert report["census"] == {
        "panel_tasks": 96,
        "canonical_task_families": 23,
        "solver_variants": 18,
        "solver_families": 4,
        "observation_rows_by_line_count_only": 1_728,
        "complete_cells_expected": 1_728,
    }
    assert {
        path.name: path.read_bytes() for path in first.iterdir() if path.is_file()
    } == {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}
