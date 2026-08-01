from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.grouped_inference import run_outcome_blind_group_preflight


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_grouped_inference/preregistration.json"
PREFLIGHT = ROOT / "analysis/ml9_grouped_inference/preflight_v1"


def test_ml9d_preregistration_is_frozen_before_target_fit() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    assert payload["artifact_id"] == "ml9d_grouped_inference_preregistration_v1"
    assert payload["frozen_before_target_fit"] is True
    assert payload["population"]["features"] == 193
    assert payload["population"]["expected_canonical_family_blocks"] == 23
    assert payload["correlation_grouping"]["fixed_distance_cut"] == 0.3
    assert len(payload["prespecified_contrasts"]["additions"]) == 5
    assert payload["reporting"]["shap_planned"] is False
    assert (
        payload["target_inputs"]["primary"]["current_retained_raw_files_allowed"]
        is False
    )


def test_ml9d_outcome_blind_input_hashes_are_current() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    for specification in payload["outcome_blind_inputs"].values():
        assert sha256_file(ROOT / specification["path"]) == specification["sha256"]


def test_ml9d_preflight_is_target_blind_and_deterministic(
    tmp_path: Path, monkeypatch
) -> None:
    original_read_csv = pd.read_csv
    forbidden_names = {"labels_by_threshold.csv", "difficulty_handoff_ml9d.csv"}

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path).name in forbidden_names:
            raise AssertionError("ML-9D target must not be parsed during preflight")
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)
    first = tmp_path / "first"
    second = tmp_path / "second"
    report = run_outcome_blind_group_preflight(ROOT, PREREGISTRATION, first)
    repeated = run_outcome_blind_group_preflight(ROOT, PREREGISTRATION, second)

    assert report == repeated
    assert report["status"] == "pass_outcome_blind_groups_frozen"
    assert report["scientific_targets_consumed"] is False
    assert report["primary_target_accessed"] is False
    assert report["secondary_targets_accessed"] is False
    assert report["model_fitted"] is False
    assert report["census"]["panel_tasks"] == 96
    assert report["census"]["panel_canonical_task_families"] == 23
    assert report["census"]["modeling_features"] == 193
    assert report["census"]["constant_after_completion"] == 5
    assert report["census"]["prespecified_contrasts"] == 5
    assert report["target_gate"]["retained_raw_handoff_allowed"] is False

    first_files = {
        path.name: path.read_bytes() for path in first.iterdir() if path.is_file()
    }
    second_files = {
        path.name: path.read_bytes() for path in second.iterdir() if path.is_file()
    }
    assert first_files == second_files


def test_ml9d_committed_preflight_is_hashed_and_target_free() -> None:
    manifest = json.loads(
        (PREFLIGHT / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (PREFLIGHT / "preflight_report.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "pass_outcome_blind_groups_frozen"
    assert manifest["scientific_targets_consumed"] is False
    assert manifest["model_fitted"] is False
    assert manifest["target_dependent_outputs_promoted"] is False
    for record in manifest["files"]:
        assert sha256_file(PREFLIGHT / record["path"]) == record["sha256"]

    groups = pd.read_csv(PREFLIGHT / "feature_groups.csv")
    summaries = pd.read_csv(PREFLIGHT / "group_summary.csv")
    assert len(groups) == 193
    assert groups["feature"].is_unique
    assert groups["group_id"].nunique() == report["census"]["correlation_groups"]
    assert len(summaries) == report["census"]["correlation_groups"]
    assert (
        int(groups["baseline_component"].sum()) == report["census"]["baseline_features"]
    )
    contrast_rows = summaries.loc[summaries["contrast_id"].notna()]
    assert len(contrast_rows) == 5
    assert contrast_rows["contrast_id"].nunique() == 5
    assert not contrast_rows["baseline_component"].any()
    assert report["target_gate"]["status"] == "held_before_target_access"
    assert not (ROOT / "analysis/ml9_bayesian_irt/final_v1").exists()
