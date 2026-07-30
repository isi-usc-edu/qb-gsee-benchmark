"""Verified post-G59 inputs for the accepted ML-8D uncertainty engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from qb_gsee_benchmark.ml.core_set import _require, sha256_file
from qb_gsee_benchmark.ml.g59_panel_refresh import load_g59_panel_refresh
from qb_gsee_benchmark.ml.solvability_uq import run_solvability_uq


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_path(path: Path, expected: str, label: str) -> None:
    _require(path.is_file(), f"missing {label}: {path}")
    _require(sha256_file(path) == expected, f"{label} changed")


def _verify_analysis_directory(
    directory: Path, specification: Mapping[str, Any]
) -> tuple[dict[str, Any], str]:
    manifest_path = directory / "artifact_manifest.json"
    _require(manifest_path.is_file(), f"missing post-G59 manifest: {manifest_path}")
    manifest = _read_json(manifest_path)
    _require(
        manifest.get("artifact_id") == "ml_g59_solver_family_solvability_manifest_v1",
        "wrong post-G59 analysis manifest",
    )
    for record in manifest["files"]:
        path = directory / str(record["path"])
        _require(path.is_file(), f"missing post-G59 analysis file: {path}")
        _require(path.stat().st_size == int(record["bytes"]), f"size drift: {path}")
        _require(sha256_file(path) == record["sha256"], f"hash drift: {path}")

    report = _read_json(directory / "report.json")
    _require(
        report.get("artifact_id") == specification["required_analysis_artifact_id"],
        "wrong post-G59 analysis artifact",
    )
    revision = report.get("analysis_revision", {})
    _require(
        revision.get("analysis_revision_id")
        == specification["required_analysis_revision_id"],
        "wrong post-G59 analysis revision",
    )
    panel = report["panel"]
    expected = {
        "selected_tasks": "required_panel_tasks",
        "analysis_variants": "required_variants",
        "normalized_labels": "required_labels",
        "prediction_rows": "required_prediction_rows",
        "selection_weight_sum": "required_selection_weight_sum",
    }
    for report_key, specification_key in expected.items():
        _require(
            int(panel[report_key]) == int(specification[specification_key]),
            f"post-G59 analysis census changed: {report_key}",
        )
    _require(report.get("validated_predictor_claim") is False, "predictor claim drift")
    _require(
        report.get("public_or_dashboard_bundle") is False,
        "post-G59 analysis release status drift",
    )
    return report, sha256_file(manifest_path)


def load_g59_uq_revision(root: Path, amendment_path: Path) -> dict[str, Any]:
    """Verify the frozen amendment, promoted merge, and deterministic ML output."""

    amendment = _read_json(amendment_path)
    _require(
        amendment.get("amendment_id") == "ml_g59_solvability_uq_amendment_v1",
        "wrong post-G59 UQ amendment",
    )
    _require(amendment.get("frozen_before_refit") is True, "unfrozen UQ amendment")

    parent = amendment["parent_uq"]
    _verify_path(
        root / parent["preregistration_path"],
        parent["preregistration_sha256"],
        "parent UQ preregistration",
    )
    _verify_path(
        root / parent["accepted_manifest_path"],
        parent["accepted_manifest_sha256"],
        "accepted parent UQ manifest",
    )

    panel_specification = amendment["panel_refresh"]
    panel_amendment_path = root / panel_specification["amendment_path"]
    _verify_path(
        panel_amendment_path,
        panel_specification["amendment_sha256"],
        "panel-refresh amendment",
    )
    panel_bundle = load_g59_panel_refresh(
        root, panel_amendment_path, require_complete=True
    )
    analysis_directory = root / panel_specification["analysis_directory"]
    analysis_report, analysis_manifest_sha256 = _verify_analysis_directory(
        analysis_directory, panel_specification
    )

    predictions_path = analysis_directory / "predictions.csv"
    predictions = pd.read_csv(predictions_path)
    _require(
        len(predictions) == int(panel_specification["required_prediction_rows"]),
        "post-G59 prediction census changed",
    )
    scope = amendment["scope"]
    _require(
        len(panel_bundle["selection_weights"]) == int(scope["training_panel_tasks"]),
        "post-G59 UQ panel census changed",
    )
    _require(
        sum(panel_bundle["selection_weights"].values())
        == int(panel_specification["required_selection_weight_sum"]),
        "post-G59 UQ weight sum changed",
    )

    revision = {
        "revision_id": "ml_g59_solvability_uq_revision_v1",
        "artifact_id": amendment["output"]["artifact_id"],
        "manifest_artifact_id": amendment["output"]["manifest_artifact_id"],
        "training_panel_tasks": int(scope["training_panel_tasks"]),
        "design_estimand": "gradeable_population",
        "design_population": {
            "gradeable_population_covered": int(scope["design_population_covered"]),
            "gradeable_population_orphaned": int(scope["design_population_orphaned"]),
            "restated_weight_sum": int(
                panel_specification["required_selection_weight_sum"]
            ),
        },
        "inputs": {
            "post_g59_uq_amendment": {
                "path": str(amendment_path.relative_to(root)),
                "sha256": sha256_file(amendment_path),
            },
            "post_g59_solver_family_manifest": {
                "path": str(
                    (analysis_directory / "artifact_manifest.json").relative_to(root)
                ),
                "sha256": analysis_manifest_sha256,
            },
            "post_g59_predictions": {
                "path": str(predictions_path.relative_to(root)),
                "sha256": sha256_file(predictions_path),
            },
            "post_g59_harvest": dict(panel_bundle["input_hashes"]),
        },
        "source_analysis_revision": analysis_report["analysis_revision"],
        "validated_predictor_claim": False,
        "public_or_dashboard_release": False,
    }
    return {
        "amendment": amendment,
        "panel_bundle": panel_bundle,
        "predictions": predictions,
        "analysis_report": analysis_report,
        "analysis_manifest_sha256": analysis_manifest_sha256,
        "revision": revision,
    }


def run_g59_solvability_uq(
    root: Path, amendment_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Run the unchanged ML-8D engine on the verified promoted panel."""

    bundle = load_g59_uq_revision(root, amendment_path)
    panel = bundle["panel_bundle"]
    parent_preregistration = (
        root / bundle["amendment"]["parent_uq"]["preregistration_path"]
    )
    return run_solvability_uq(
        root,
        parent_preregistration,
        output_directory,
        observations_override=panel["observations"],
        selection_weights_override=panel["selection_weights"],
        knn_predictions_override=bundle["predictions"],
        analysis_revision=bundle["revision"],
    )
