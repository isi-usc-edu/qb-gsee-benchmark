from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.resource_profiles import run_outcome_blind_preflight


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_resource_profiles/preregistration.json"


def test_ml9b_preregistration_freezes_censor_and_competing_risk_rules() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert payload["artifact_id"] == "ml9b_resource_profiles_preregistration_v1"
    assert payload["frozen_before_result_construction"] is True
    assert payload["population"]["panel_tasks"] == 96
    assert payload["thresholds"]["factors"] == [0.5, 1.0, 2.0]
    assert payload["runstatus"]["vocabulary"] == [
        "ok",
        "accuracy_miss",
        "timeout",
        "crash",
    ]
    assert payload["runstatus"]["crash_is_competing_risk"] is True
    assert payload["resource_to_solution"]["monotonic_repair"] is False
    assert payload["summaries"]["par_k"] is False
    assert payload["fences"]["new_solver_runs"] is False


def test_ml9b_local_input_hashes_are_current() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    for specification in payload["inputs"].values():
        assert sha256_file(ROOT / specification["path"]) == specification["sha256"]


def test_ml9b_preflight_is_outcome_blind_and_deterministic(
    tmp_path: Path, monkeypatch
) -> None:
    original_read_csv = pd.read_csv

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path).name in {"normalized_observations.csv", "coverage.csv"}:
            raise AssertionError("ML-9B preflight must not parse outcome/status rows")
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = run_outcome_blind_preflight(ROOT, PREREGISTRATION, first)
    repeated = run_outcome_blind_preflight(ROOT, PREREGISTRATION, second)
    assert report == repeated
    assert report["status"] == "pass"
    assert report["scientific_outcomes_consumed"] is False
    assert report["resource_endpoints_computed"] is False
    assert report["data_profiles_computed"] is False
    assert report["census"] == {
        "panel_tasks": 96,
        "observation_rows_by_line_count_only": 1728,
        "coverage_rows_by_line_count_only": 1728,
        "solver_variants": 18,
        "profiled_variants": 16,
        "ladder_variants": 15,
        "single_point_variants": 1,
        "companion_variants": 2,
        "resource_ladders": 3,
        "threshold_factors": 3,
    }
    assert {
        path.name: path.read_bytes() for path in first.iterdir() if path.is_file()
    } == {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}
