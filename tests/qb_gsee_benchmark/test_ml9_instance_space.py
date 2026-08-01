from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from instancespace.stages.trace import TraceStage

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.instance_space import run_outcome_blind_preflight
from qb_gsee_benchmark.ml.instance_space_run import (
    FAMILY_ORDER,
    TARGET_ORDER,
    THRESHOLD_FACTORS,
    _instancespace_021_trace_compatibility,
    prepare_isa_data,
)


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_instance_space/preregistration.json"


def test_ml9a_preregistration_is_frozen_and_pins_isa() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert payload["artifact_id"] == "ml9a_instance_space_preregistration_v1"
    assert payload["frozen_before_benchmark_fit"] is True
    assert payload["toolkit"]["version"] == "0.2.1"
    assert (
        payload["toolkit"]["wheel_sha256"]
        == "d0d81a7347f52745a0ad58594a3ad1d06cfac6a2a43110970e1fec55cfeb4e8e"
    )
    assert payload["feature_space"]["candidate_columns"] == 193
    assert payload["feature_space"]["jw_columns"] == 17
    assert payload["sifted"]["target_projection_features"] == 8
    assert payload["pilot"]["n_tries"] == 30
    assert payload["trace"]["fitted_surface_integral"] is False
    assert payload["bootstrap"]["replicates"] == 2000
    assert payload["fences"]["new_solver_runs"] is False
    assert payload["prior_exposure"]["ml9_benchmark_model_fitted"] is False


def test_ml9a_local_input_hashes_are_current() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    for specification in payload["inputs"].values():
        path = ROOT / specification["path"]
        assert sha256_file(path) == specification["sha256"]


def test_ml9a_preflight_is_outcome_blind_and_deterministic(
    tmp_path: Path, monkeypatch
) -> None:
    original_read_csv = pd.read_csv
    outcome_name = "normalized_observations.csv"

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path).name == outcome_name:
            raise AssertionError("outcome table must not be parsed during preflight")
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = run_outcome_blind_preflight(ROOT, PREREGISTRATION, first)
    repeated = run_outcome_blind_preflight(ROOT, PREREGISTRATION, second)

    assert report == repeated
    assert report["status"] == "pass"
    assert report["scientific_outcomes_consumed"] is False
    assert report["model_fitted"] is False
    assert report["census"]["corpus_tasks"] == 718
    assert report["census"]["labeled_panel_tasks"] == 96
    assert report["census"]["corpus_canonical_task_families"] == 40
    assert report["census"]["panel_canonical_task_families"] == 23
    assert report["census"]["non_gradeable_coverage_points"] == 109
    assert report["census"]["modeling_features"] == 193
    assert report["census"]["jw_features"] == 17
    assert report["census"]["constant_after_completion"] == 5

    first_files = {
        path.name: path.read_bytes() for path in first.iterdir() if path.is_file()
    }
    second_files = {
        path.name: path.read_bytes() for path in second.iterdir() if path.is_file()
    }
    assert first_files == second_files


def test_ml9a_frozen_response_reproduces_primary_labels() -> None:
    data = prepare_isa_data(ROOT, PREREGISTRATION)
    assert tuple(data.family_costs.columns) == FAMILY_ORDER
    assert tuple(data.all_costs.columns) == TARGET_ORDER
    assert tuple(data.labels) == THRESHOLD_FACTORS
    assert data.family_costs.shape == (96, 4)
    assert data.all_costs.shape == (96, 5)
    assert data.labels[1.0].sum().to_dict() == {
        "dmrg": 54,
        "ipie_afqmc": 29,
        "shci": 52,
        "trimci": 60,
        "portfolio_union": 77,
    }
    assert np.isfinite(data.features_transformed.to_numpy()).all()
    assert data.features_transformed.shape == (718, 193)


def test_ml9a_trace_compatibility_converts_missing_refinement_to_empty(
    monkeypatch,
) -> None:
    monkeypatch.setattr(TraceStage, "tight", lambda self, polygon, y_bin: None)
    with _instancespace_021_trace_compatibility():
        polygon = TraceStage.tight(object(), None, np.array([], dtype=bool))
    assert polygon.is_empty
