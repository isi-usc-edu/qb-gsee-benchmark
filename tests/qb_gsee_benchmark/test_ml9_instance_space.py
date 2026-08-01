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
FINAL = ROOT / "analysis/ml9_instance_space/final_v1"
RAW_RUNS = ROOT / "analysis/ml9_instance_space/raw_runs"
IDENTITY = ROOT / "analysis/ml9_instance_space/two_run_identity_v1.json"


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


def test_ml9a_promoted_bundle_is_identical_hashed_and_fenced() -> None:
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    required = set(preregistration["outputs"]["required_files"])
    identity = json.loads(IDENTITY.read_text(encoding="utf-8"))
    assert identity["status"] == "pass"
    assert identity["byte_identical"] is True
    assert identity["file_count"] == 20
    assert set(identity["relative_paths"]) == required

    for name, expected_hash in identity["file_hashes"].items():
        promoted = FINAL / name
        assert sha256_file(promoted) == expected_hash
        assert promoted.read_bytes() == (RAW_RUNS / "run_1" / name).read_bytes()
        assert promoted.read_bytes() == (RAW_RUNS / "run_2" / name).read_bytes()

    manifest = json.loads(
        (FINAL / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "complete_internal_descriptive"
    assert manifest["internal_only"] is True
    assert manifest["new_solver_runs"] is False
    assert manifest["task_reselection"] is False
    assert manifest["label_changes"] is False
    assert manifest["fitted_surface_integral"] is False
    assert {row["path"] for row in manifest["files"]} == required - {
        "artifact_manifest.json"
    }
    for row in manifest["files"]:
        assert sha256_file(FINAL / row["path"]) == row["sha256"]

    gates = pd.read_csv(FINAL / "pythia_gate.csv")
    assert len(gates) == 15
    primary_gates = gates.loc[gates["threshold_factor"] == 1.0]
    assert len(primary_gates) == 5
    assert primary_gates["gate_passed"].all()

    bootstrap = pd.read_csv(FINAL / "bootstrap_draws.csv")
    assert len(bootstrap) == 20_000
    assert bootstrap["replicate"].nunique() == 2_000
    assert set(bootstrap["output_kind"]) == {"estimate"}
    assert len(pd.read_csv(FINAL / "bootstrap_intervals.csv")) == 50

    corpus = pd.read_csv(FINAL / "corpus_coordinates.csv")
    assert len(corpus) == 718
    assert int(corpus["in_labeled_panel"].sum()) == 96
    assert int((~corpus["gradeable_for_campaign_scoring"]).sum()) == 109
    priorities = pd.read_csv(FINAL / "priority_targets.csv")
    assert len(priorities) == 622
    assert not priorities["authorizes_solver_run"].any()
