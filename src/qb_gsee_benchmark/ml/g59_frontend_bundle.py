"""Deterministic frontend bundle for the promoted post-G59 solver panel."""

from __future__ import annotations

import json
import math
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.core_set import _require, sha256_file
from qb_gsee_benchmark.ml.g50_frontend_bundle import (
    SUMMARY_TABLES,
    _build_task_and_feature_catalog,
    _file_record,
    _json_scalar,
    _load_sources,
    _prediction_chunk_paths,
    _write_json,
    verify_frontend_archive,
    write_deterministic_zip,
)
from qb_gsee_benchmark.ml.g59_panel_refresh import load_g59_panel_refresh

ARTIFACT_ID = "g59_solver_family_frontend_v2"
SCHEMA_VERSION = "2.0.0"
ANALYSIS_DIRECTORY = Path("analysis/ml_g59_panel_refresh/final_v1")
UQ_DIRECTORY = Path("analysis/ml_g59_solvability_uq/held_v1")
PANEL_AMENDMENT = Path(
    "analysis/ml_g59_panel_refresh/amendment_post_g59_panel_refresh.json"
)
UQ_AMENDMENT = Path("analysis/ml_g59_solvability_uq/amendment_post_g59_uq.json")
INDEX_SCHEMA = Path("analysis/ml_g59_panel_refresh/frontend_bundle_v2.schema.json")
PANEL_IDENTITY = Path("analysis/ml_g59_panel_refresh/two_run_identity_v1.json")
UQ_IDENTITY = Path("analysis/ml_g59_solvability_uq/two_run_identity_v1.json")

EXPECTED_COUNTS = {
    "corpus_tasks": 718,
    "gradeable_corpus_tasks": 609,
    "current_panel_tasks": 96,
    "current_gradeable_panel_tasks": 96,
    "historical_panel_tasks": 96,
    "historical_gradeable_panel_tasks": 80,
    "canonical_families": 40,
    "solver_families": 4,
    "solver_variants": 18,
    "selected_features": 193,
    "observations": 1728,
    "coverage_rows": 1728,
    "predictions": 25848,
    "prediction_rows_per_variant": 1436,
    "dmrg_terminal_cells": 96,
    "g59_dmrg_terminal_cells": 30,
    "legacy_dmrg_terminal_cells": 66,
    "g59_parent_terminal_cells": 86,
    "uq_design_rows": 18,
    "uq_posterior_rows": 12924,
}

SUMMARY_KEYS = {
    "variant_eligibility": ["solver_uuid"],
    "ladder_growth": ["solver_uuid"],
    "nestedness": [
        "solver_family_id",
        "resource_ladder_id",
        "earlier_solver_short_name",
        "later_solver_short_name",
    ],
    "family_balanced_performance": [
        "solver_uuid",
        "estimator",
        "feature_arm",
        "metric",
    ],
    "paired_deltas": ["solver_uuid", "comparison", "metric"],
}
UQ_TABLES = {
    "design_based_ratios": ["solver_uuid"],
    "model_based_ratios": ["solver_uuid", "lengthscale_variant"],
    "per_task_posterior": ["task_uuid", "solver_uuid"],
    "calibration": ["solver_uuid"],
    "reliability_bins": ["solver_uuid", "bin_index"],
    "calibration_gate": ["solver_uuid"],
    "lengthscale_sensitivity": ["solver_uuid", "lengthscale_variant"],
    "kernel_psd_diagnostics": [
        "solver_family_id",
        "query_canonical_family",
        "lengthscale_variant",
    ],
    "ratio_comparison": ["solver_uuid"],
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _table_payload(
    frame: pd.DataFrame,
    table_name: str,
    primary_key: Sequence[str],
    *,
    source_path: str,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "artifact_id": f"{ARTIFACT_ID}_{table_name}",
        "encoding": "row_array_table_v1",
        "table_name": table_name,
        "source_path": source_path,
        "primary_key": list(primary_key),
        "columns": list(map(str, frame.columns)),
        "rows": [
            [_json_scalar(value) for value in row]
            for row in frame.itertuples(index=False, name=None)
        ],
    }
    if metadata:
        payload["metadata"] = dict(metadata)
    return payload


def _table_records(payload: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    columns = payload["columns"]
    for row in payload["rows"]:
        yield dict(zip(columns, row))


def _verify_manifest_directory(
    directory: Path, expected_artifact_id: str
) -> tuple[dict[str, Any], str]:
    manifest_path = directory / "artifact_manifest.json"
    _require(manifest_path.is_file(), f"missing source manifest: {manifest_path}")
    manifest = _read_json(manifest_path)
    _require(
        manifest.get("artifact_id") == expected_artifact_id,
        f"wrong source manifest: {manifest_path}",
    )
    for record in manifest["files"]:
        path = directory / str(record["path"])
        _require(path.is_file(), f"missing source file: {path}")
        _require(path.stat().st_size == int(record["bytes"]), f"size drift: {path}")
        _require(sha256_file(path) == record["sha256"], f"hash drift: {path}")
    return manifest, sha256_file(manifest_path)


def _load_bundle_sources(root: Path) -> dict[str, Any]:
    base = _load_sources(root)
    panel_bundle = load_g59_panel_refresh(
        root, root / PANEL_AMENDMENT, require_complete=True
    )
    analysis_directory = root / ANALYSIS_DIRECTORY
    analysis_manifest, analysis_manifest_sha256 = _verify_manifest_directory(
        analysis_directory, "ml_g59_solver_family_solvability_manifest_v1"
    )
    analysis_report = _read_json(analysis_directory / "report.json")
    _require(
        analysis_report.get("artifact_id") == "ml_g59_solver_family_solvability_v1",
        "wrong post-G59 analysis report",
    )
    _require(
        analysis_report.get("analysis_revision", {}).get("analysis_revision_id")
        == "ml_g59_panel_refresh_v1",
        "wrong post-G59 analysis revision",
    )
    _require(
        analysis_report.get("validated_predictor_claim") is False,
        "post-G59 analysis predictor claim drift",
    )
    _require(
        analysis_report.get("public_or_dashboard_bundle") is False,
        "post-G59 analysis release drift",
    )

    uq_directory = root / UQ_DIRECTORY
    uq_manifest, uq_manifest_sha256 = _verify_manifest_directory(
        uq_directory, "ml_g59_solvability_uq_manifest_v1"
    )
    uq_report = _read_json(uq_directory / "report.json")
    _require(
        uq_report.get("artifact_id") == "ml_g59_solvability_uq_v1",
        "wrong post-G59 UQ report",
    )
    _require(uq_report.get("ratio_of_record") == "design_based", "ratio drift")
    _require(
        uq_report.get("validated_predictor_claim") is False,
        "post-G59 UQ predictor claim drift",
    )

    for identity_path in (PANEL_IDENTITY, UQ_IDENTITY):
        path = root / identity_path
        _require(path.is_file(), f"missing two-run identity: {path}")
        identity = _read_json(path)
        _require(identity.get("status") == "pass", f"failed identity: {path}")

    return {
        "base": base,
        "panel_bundle": panel_bundle,
        "analysis_directory": analysis_directory,
        "analysis_manifest": analysis_manifest,
        "analysis_manifest_sha256": analysis_manifest_sha256,
        "analysis_report": analysis_report,
        "uq_directory": uq_directory,
        "uq_manifest": uq_manifest,
        "uq_manifest_sha256": uq_manifest_sha256,
        "uq_report": uq_report,
    }


def _build_catalog(
    root: Path,
    sources: Mapping[str, Any],
    prediction_paths: Mapping[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog, features = _build_task_and_feature_catalog(
        sources["base"], prediction_paths
    )
    panel = pd.read_csv(
        root / "analysis/ml_core_set_v2/selection_of_record_v1/panel_of_record.csv"
    )
    panel_by_task = panel.set_index("task_uuid").to_dict(orient="index")
    census = pd.read_csv(root / "analysis/ml_gradeability_census/held_v1/census.csv")
    gradeability = census.set_index("task_uuid").to_dict(orient="index")
    _require(len(panel_by_task) == 96, "promoted panel drift")

    for row in catalog["tasks"]:
        task_uuid = row["task_uuid"]
        historical_selected = bool(row.pop("selected_for_g50"))
        historical_weight = row.pop("selection_weight")
        gradeable = bool(gradeability[task_uuid]["gradeable_for_campaign_scoring"])
        current = panel_by_task.get(task_uuid)
        row.update(
            {
                "gradeable_for_campaign_scoring": gradeable,
                "gradeability_reason": str(
                    gradeability[task_uuid]["gradeability_reason"]
                ),
                "selected_for_current_panel": current is not None,
                "current_panel_origin": None if current is None else current["origin"],
                "current_selection_weight": (
                    None if current is None else int(current["selection_weight_609"])
                ),
                "selected_for_historical_final_v4_panel": historical_selected,
                "historical_final_v4_selection_weight": historical_weight,
                "historical_final_v4_gradeable_panel_member": bool(
                    historical_selected and gradeable
                ),
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in catalog["tasks"]:
        grouped[row["canonical_family"]].append(row)
    catalog["canonical_families"] = [
        {
            "canonical_family": family,
            "task_count": len(rows),
            "gradeable_task_count": sum(
                row["gradeable_for_campaign_scoring"] for row in rows
            ),
            "current_panel_task_count": sum(
                row["selected_for_current_panel"] for row in rows
            ),
            "historical_final_v4_panel_task_count": sum(
                row["selected_for_historical_final_v4_panel"] for row in rows
            ),
            "archive_classes": sorted({row["archive_class"] for row in rows}),
        }
        for family, rows in sorted(grouped.items())
    ]

    eligibility = pd.read_csv(
        sources["analysis_directory"] / "variant_eligibility.csv"
    ).set_index("solver_uuid")
    for row in catalog["solver_variants"]:
        solver_uuid = row["solver_uuid"]
        row["model_eligibility"] = {
            key: _json_scalar(value)
            for key, value in eligibility.loc[solver_uuid].to_dict().items()
        }
    catalog["artifact_id"] = f"{ARTIFACT_ID}_catalog"
    catalog["panel_contract"] = {
        "current": "promoted post-G59 panel of record",
        "historical": "accepted final_v4 sensitivity membership only",
    }
    features["artifact_id"] = f"{ARTIFACT_ID}_features"
    return catalog, features


def _solution_terminal_energy(document: Mapping[str, Any]) -> float:
    data = document.get("solution_data", [])
    _require(len(data) == 1, "DMRG solution must contain exactly one solution row")
    energy = float(data[0]["energy"])
    _require(math.isfinite(energy), "non-finite DMRG terminal energy")
    return energy


def _last_dmrg_rungs(observations: pd.DataFrame) -> dict[str, dict[str, Any]]:
    dmrg = observations.loc[observations["solver_family_id"].astype(str).eq("dmrg")]
    result: dict[str, dict[str, Any]] = {}
    for task_uuid, frame in dmrg.groupby("task_uuid"):
        observed = frame.loc[frame["energy_hartree"].notna()].sort_values(
            "resource_value"
        )
        if observed.empty:
            result[str(task_uuid)] = {
                "last_observed_rung_energy_hartree": None,
                "last_observed_resource_value": None,
            }
        else:
            row = observed.iloc[-1]
            result[str(task_uuid)] = {
                "last_observed_rung_energy_hartree": float(row["energy_hartree"]),
                "last_observed_resource_value": int(row["resource_value"]),
            }
    return result


def _terminal_metric(
    terminal_state: str,
    terminal_energy: float | None,
    reference_energy: float,
    threshold: float,
) -> dict[str, Any]:
    if terminal_state != "completed" or terminal_energy is None:
        return {
            "terminal_observed_outcome": "fail",
            "terminal_metric_annotation": "indeterminate",
            "terminal_absolute_error_hartree": None,
            "terminal_graded_residual": None,
        }
    error = abs(terminal_energy - reference_energy)
    return {
        "terminal_observed_outcome": "success" if error <= threshold else "fail",
        "terminal_metric_annotation": "success" if error <= threshold else "fail",
        "terminal_absolute_error_hartree": error,
        "terminal_graded_residual": error / threshold,
    }


def _build_dmrg_terminal_cells(
    root: Path,
    sources: Mapping[str, Any],
    observations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    panel_tasks = set(sources["panel_bundle"]["selection_weights"])
    last_rungs = _last_dmrg_rungs(observations)
    reference = (
        observations.loc[observations["solver_family_id"].astype(str).eq("dmrg")]
        .sort_values(["task_uuid", "resource_value"])
        .groupby("task_uuid")
        .first()
    )

    terminal_path = sources["panel_bundle"]["terminal_cells_path"]
    g59_all = pd.read_csv(terminal_path, float_precision="round_trip")
    g59_dmrg = g59_all.loc[g59_all["solver_family_id"].astype(str).eq("dmrg")]
    _require(
        len(g59_dmrg) == EXPECTED_COUNTS["g59_dmrg_terminal_cells"], "G59 DMRG census"
    )
    g59_tasks = set(map(str, g59_dmrg["task_uuid"]))

    rows: list[dict[str, Any]] = []
    for source_row in g59_dmrg.to_dict(orient="records"):
        task_uuid = str(source_row["task_uuid"])
        terminal_energy = _json_scalar(source_row["terminal_energy_hartree"])
        state = str(source_row["terminal_state"])
        ref = reference.loc[task_uuid]
        row = {
            "task_uuid": task_uuid,
            "source_cohort": "g59_promoted_panel_rerun",
            "terminal_state": state,
            "terminal_energy_hartree": terminal_energy,
            "last_observed_rung_energy_hartree": _json_scalar(
                source_row["last_observed_rung_energy_hartree"]
            ),
            "last_observed_resource_value": _json_scalar(
                source_row["last_observed_resource_value"]
            ),
            "terminal_minus_last_observed_hartree": (
                None
                if terminal_energy is None
                or pd.isna(source_row["last_observed_rung_energy_hartree"])
                else terminal_energy
                - float(source_row["last_observed_rung_energy_hartree"])
            ),
            "solution_path": _json_scalar(source_row["solution_path"]),
            "solution_sha256": _json_scalar(source_row["solution_sha256"]),
            "source_manifest": str(terminal_path),
            **_terminal_metric(
                state,
                terminal_energy,
                float(ref["reference_energy_hartree"]),
                float(ref["threshold_hartree"]),
            ),
        }
        rows.append(row)

    preregistration = sources["base"]["preregistration"]
    intake_specification = preregistration["inputs"]["g50_terminal_intake"]
    intake_path = Path(intake_specification["external_path"])
    _require(intake_path.is_file(), f"missing legacy terminal intake: {intake_path}")
    _require(
        sha256_file(intake_path) == intake_specification["sha256"],
        "legacy terminal intake changed",
    )
    with zipfile.ZipFile(intake_path) as archive:
        manifest = json.loads(archive.read("BASELINE_MANIFEST.json"))
        legacy = {
            str(row["task_uuid"]): row
            for row in manifest["rows"]
            if row["solver"] == "dmrg"
        }
        legacy_tasks = panel_tasks - g59_tasks
        _require(len(legacy_tasks) == 66, "legacy DMRG panel census changed")
        _require(legacy_tasks <= set(legacy), "legacy DMRG terminal row missing")
        for task_uuid in sorted(legacy_tasks):
            source_row = legacy[task_uuid]
            state = source_row.get("harness_status")
            if state is None:
                state = (
                    "not_started"
                    if source_row["package_status"] == "unresolved_never_started"
                    else "missing_terminal"
                )
            terminal_energy = None
            intake_member = None
            if source_row.get("intake_path"):
                intake_member = f"intake/{source_row['intake_path']}"
                document = json.loads(archive.read(intake_member))
                if state == "completed":
                    terminal_energy = _solution_terminal_energy(document)
            ref = reference.loc[task_uuid]
            last = last_rungs[task_uuid]
            rows.append(
                {
                    "task_uuid": task_uuid,
                    "source_cohort": "g50_retained_terminal_intake",
                    "terminal_state": state,
                    "terminal_energy_hartree": terminal_energy,
                    **last,
                    "terminal_minus_last_observed_hartree": (
                        None
                        if terminal_energy is None
                        or last["last_observed_rung_energy_hartree"] is None
                        else terminal_energy
                        - float(last["last_observed_rung_energy_hartree"])
                    ),
                    "solution_path": intake_member,
                    "solution_sha256": source_row.get("intake_sha256"),
                    "source_manifest": str(intake_path),
                    **_terminal_metric(
                        str(state),
                        terminal_energy,
                        float(ref["reference_energy_hartree"]),
                        float(ref["threshold_hartree"]),
                    ),
                }
            )

    terminal = pd.DataFrame(rows).sort_values("task_uuid").reset_index(drop=True)
    _require(len(terminal) == len(panel_tasks) == 96, "DMRG terminal census changed")
    _require(terminal["task_uuid"].is_unique, "duplicate DMRG terminal task")
    _require(set(terminal["task_uuid"]) == panel_tasks, "DMRG terminal panel mismatch")
    return terminal, g59_all


def _definitions() -> dict[str, Any]:
    return {
        "artifact_id": f"{ARTIFACT_ID}_definitions",
        "metrics": {
            "absolute_error_hartree": (
                "abs(energy_hartree - reference_energy_hartree); null when no "
                "finite observed energy or gradeable reference is available"
            ),
            "graded_residual": (
                "absolute_error_hartree / threshold_hartree; lower is better and "
                "success is graded_residual <= 1"
            ),
            "observed_bounded_run_outcome": (
                "success only when a finite emitted energy is within the stored "
                "task threshold; every attempted but unreached or nonterminal cell "
                "is a bounded fail with null energy and indeterminate metric"
            ),
            "dmrg_terminal_cell": (
                "the parent run terminal state and energy, distinct from the last "
                "completed bond-dimension rung; terminal energy exists only for a "
                "completed parent"
            ),
        },
        "denominators": {
            "current_panel": {
                "n": 96,
                "membership": "promoted post-G59 panel of record",
                "display": "observed successes / 96 current panel tasks",
            },
            "current_gradeable_panel": {
                "n": 96,
                "membership": "all current panel tasks are gradeable",
                "display": "observed successes / 96 current gradeable panel tasks",
                "same_membership_as_current_panel": True,
            },
            "historical_final_v4_gradeable_sensitivity": {
                "n": 80,
                "membership": "gradeable subset of the superseded final_v4 panel",
                "display": "historical sensitivity only; never a current denominator",
            },
            "gradeable_corpus": {
                "n": 609,
                "membership": "accepted ML-8A gradeable corpus",
            },
        },
        "estimators": {
            "design_based_ratio_of_record": (
                "sum(selection_weight_609 * observed_success) / 609 over the 96 "
                "current panel tasks; family-grouped percentile bootstrap is the "
                "primary 95% interval"
            ),
            "shared_block_distance_knn_k15": (
                "leave-one-canonical-family-out k=15 nearest-neighbor estimate over "
                "the frozen block-aware feature distance; estimate only"
            ),
            "gp_laplace_block_aware": (
                "leave-one-canonical-family-out Gaussian-process classification "
                "with Laplace approximation over the frozen block-aware distance; "
                "posterior probabilities and intervals are estimates only"
            ),
            "family_balanced_bootstrap": (
                "canonical families are the resampling unit; point estimates and "
                "intervals are descriptive and make no validated-predictor claim"
            ),
        },
        "display_strings": {
            "observed": "observed bounded-run outcome",
            "predicted": "estimated solvability",
            "ratio_of_record": "design-based ratio of record",
            "model_uq": "model-based estimate; not a validated predictor",
            "unreached": "bounded fail; target not reached",
            "terminal_timeout": "bounded fail; parent did not complete",
        },
    }


def _source_evidence(root: Path, sources: Mapping[str, Any]) -> list[tuple[Path, str]]:
    return [
        (
            sources["analysis_directory"] / "artifact_manifest.json",
            "source_evidence/post_g59_analysis/artifact_manifest.json",
        ),
        (
            sources["analysis_directory"] / "report.json",
            "source_evidence/post_g59_analysis/report.json",
        ),
        (
            sources["uq_directory"] / "artifact_manifest.json",
            "source_evidence/post_g59_uq/artifact_manifest.json",
        ),
        (
            sources["uq_directory"] / "report.json",
            "source_evidence/post_g59_uq/report.json",
        ),
        (root / PANEL_AMENDMENT, "source_evidence/protocol/panel_amendment.json"),
        (root / UQ_AMENDMENT, "source_evidence/protocol/uq_amendment.json"),
        (root / PANEL_IDENTITY, "source_evidence/identity/panel_two_run.json"),
        (root / UQ_IDENTITY, "source_evidence/identity/uq_two_run.json"),
    ]


def _readme() -> str:
    return """# Post-G59 solver-family frontend bundle v2

Load `index.json` first. This bundle supersedes the G50 v1 bundle and its
supplement for the promoted post-G59 panel. It contains all 718 feature rows,
the current 96-task panel, 1,728 observed solver-variant cells, prediction
chunks, updated uncertainty tables, all 96 explicit DMRG terminal cells, and
all 86 G59 parent terminal records.

`definitions.json` is normative for metric, denominator, estimator, and display
semantics. All current panel tasks are gradeable, so the current /96 and current
gradeable /96 denominators have identical membership. The old /80 gradeable
denominator is retained only as a labeled final_v4 historical sensitivity.

Observed ladder rungs and parent terminal cells are separate. A lower rung
emitted before a later timeout remains an observed variational result; an
unreached target and a noncompleted terminal parent are bounded failures with
no invented energy. No monotonic repair is applied.

This package is internal and descriptive. Model probabilities and intervals
are estimates, no predictor is validated, and public dashboard release remains
unauthorized.
"""


def build_g59_frontend_bundle(
    repository_root: Path,
    output_directory: Path,
    *,
    archive_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    output_directory = output_directory.resolve()
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    sources = _load_bundle_sources(repository_root)
    variants = _read_json(
        sources["analysis_directory"] / "preflight/solver_variants.json"
    )
    prediction_paths = _prediction_chunk_paths(variants)
    catalog, features = _build_catalog(repository_root, sources, prediction_paths)

    output_directory.mkdir(parents=True)
    _write_json(output_directory / "catalog.json", catalog)
    _write_json(output_directory / "features.json", features)
    _write_json(output_directory / "definitions.json", _definitions(), pretty=True)

    observations = pd.read_csv(
        sources["analysis_directory"] / "normalized_observations.csv",
        float_precision="round_trip",
    )
    coverage = pd.read_csv(sources["analysis_directory"] / "coverage.csv")
    _write_json(
        output_directory / "observations.json",
        _table_payload(
            observations,
            "observations",
            ["task_uuid", "solver_uuid"],
            source_path=str(ANALYSIS_DIRECTORY / "normalized_observations.csv"),
            metadata={
                "float_encoding": "JSON binary64 round-trip",
                "outcome_semantics": "binary bounded-run label",
                "monotonic_repair_applied": False,
            },
        ),
    )
    _write_json(
        output_directory / "coverage.json",
        _table_payload(
            coverage,
            "coverage",
            ["task_uuid", "solver_uuid"],
            source_path=str(ANALYSIS_DIRECTORY / "coverage.csv"),
        ),
    )

    predictions = pd.read_csv(
        sources["analysis_directory"] / "predictions.csv",
        float_precision="round_trip",
    )
    prediction_records = []
    for variant in variants:
        solver_uuid = str(variant["solver_uuid"])
        frame = predictions.loc[predictions["solver_uuid"].astype(str).eq(solver_uuid)]
        relative = prediction_paths[solver_uuid]
        _write_json(
            output_directory / relative,
            _table_payload(
                frame,
                "predictions",
                ["task_uuid", "solver_uuid", "feature_arm"],
                source_path=str(ANALYSIS_DIRECTORY / "predictions.csv"),
                metadata={
                    "solver_uuid": solver_uuid,
                    "solver_short_name": variant["solver_short_name"],
                    "solver_family_id": variant["solver_family_id"],
                    "output_kind": "estimate",
                },
            ),
        )
        prediction_records.append(
            {
                "solver_uuid": solver_uuid,
                "solver_short_name": variant["solver_short_name"],
                "solver_family_id": variant["solver_family_id"],
                "path": relative,
                "row_count": len(frame),
            }
        )

    summary_tables = {}
    summary_counts = {}
    for name in SUMMARY_TABLES:
        frame = pd.read_csv(
            sources["analysis_directory"] / f"{name}.csv",
            float_precision="round_trip",
        )
        summary_tables[name] = _table_payload(
            frame,
            name,
            SUMMARY_KEYS[name],
            source_path=str(ANALYSIS_DIRECTORY / f"{name}.csv"),
        )
        summary_counts[name] = len(frame)
    _write_json(
        output_directory / "summaries.json",
        {
            "artifact_id": f"{ARTIFACT_ID}_summaries",
            "report": sources["analysis_report"],
            "tables": summary_tables,
        },
    )

    uq_tables = {}
    uq_counts = {}
    for name, key in UQ_TABLES.items():
        frame = pd.read_csv(
            sources["uq_directory"] / f"{name}.csv",
            float_precision="round_trip",
        )
        uq_tables[name] = _table_payload(
            frame,
            name,
            key,
            source_path=str(UQ_DIRECTORY / f"{name}.csv"),
            metadata={"model_outputs_are_estimates": name != "design_based_ratios"},
        )
        uq_counts[name] = len(frame)
    _write_json(
        output_directory / "uncertainty.json",
        {
            "artifact_id": f"{ARTIFACT_ID}_uncertainty",
            "report": sources["uq_report"],
            "tables": uq_tables,
        },
    )

    terminal, g59_terminal = _build_dmrg_terminal_cells(
        repository_root, sources, observations
    )
    _write_json(
        output_directory / "dmrg_terminal_cells.json",
        _table_payload(
            terminal,
            "dmrg_terminal_cells",
            ["task_uuid"],
            source_path="merged pinned G50 intake and G59 terminal ledger",
            metadata={
                "terminal_is_distinct_from_last_observed_rung": True,
                "terminal_energy_requires_completed_parent": True,
            },
        ),
    )
    _write_json(
        output_directory / "g59_parent_terminal_cells.json",
        _table_payload(
            g59_terminal,
            "g59_parent_terminal_cells",
            ["task_uuid", "solver_family_id"],
            source_path=str(sources["panel_bundle"]["terminal_cells_path"]),
        ),
    )

    (output_directory / "README.md").write_text(_readme(), encoding="utf-8")
    schema_source = schema_path or repository_root / INDEX_SCHEMA
    schema_destination = output_directory / "schema/index.schema.json"
    schema_destination.parent.mkdir(parents=True)
    shutil.copyfile(schema_source, schema_destination)

    copied_evidence = []
    for source, relative in _source_evidence(repository_root, sources):
        destination = output_directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied_evidence.append(relative)

    files = [
        _file_record(output_directory, "README.md", role="documentation"),
        _file_record(output_directory, "catalog.json", role="frontend_catalog"),
        _file_record(
            output_directory,
            "coverage.json",
            role="frontend_table",
            row_count=len(coverage),
        ),
        _file_record(
            output_directory, "definitions.json", role="normative_definitions"
        ),
        _file_record(
            output_directory,
            "dmrg_terminal_cells.json",
            role="frontend_table",
            row_count=len(terminal),
        ),
        _file_record(output_directory, "features.json", role="frontend_features"),
        _file_record(
            output_directory,
            "g59_parent_terminal_cells.json",
            role="frontend_table",
            row_count=len(g59_terminal),
        ),
        _file_record(
            output_directory,
            "observations.json",
            role="frontend_table",
            row_count=len(observations),
        ),
        _file_record(output_directory, "schema/index.schema.json", role="schema"),
        _file_record(
            output_directory,
            "summaries.json",
            role="frontend_summaries",
            row_count=sum(summary_counts.values()),
        ),
        _file_record(
            output_directory,
            "uncertainty.json",
            role="frontend_uncertainty",
            row_count=sum(uq_counts.values()),
        ),
    ]
    for record in prediction_records:
        files.append(
            _file_record(
                output_directory,
                record["path"],
                role="frontend_prediction_chunk",
                row_count=record["row_count"],
            )
        )
    for relative in copied_evidence:
        files.append(_file_record(output_directory, relative, role="audit_source"))
    files.sort(key=lambda row: row["path"])

    index = {
        "$schema": "schema/index.schema.json",
        "artifact_id": ARTIFACT_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "complete_internal_descriptive_visualization_bundle",
        "entrypoints": {
            "catalog": "catalog.json",
            "features": "features.json",
            "definitions": "definitions.json",
            "observations": "observations.json",
            "coverage": "coverage.json",
            "summaries": "summaries.json",
            "uncertainty": "uncertainty.json",
            "dmrg_terminal_cells": "dmrg_terminal_cells.json",
            "g59_parent_terminal_cells": "g59_parent_terminal_cells.json",
        },
        "release_scope": {
            "intended_use": "internal interactive descriptive visualization",
            "public_dashboard_release_authorized": False,
            "validated_predictor_claim": False,
            "prediction_display_label": "estimated solvability",
            "observation_display_label": "observed bounded-run outcome",
        },
        "semantics": {
            "definitions_are_normative": True,
            "binary_outcomes": ["fail", "success"],
            "feature_arms": ["with_jw", "without_jw"],
            "current_denominators": [96, 96],
            "historical_sensitivity_denominator": 80,
            "monotonic_repair_applied": False,
            "terminal_energy_requires_completed_parent": True,
            "canonical_family_model_input": False,
        },
        "counts": {
            **EXPECTED_COUNTS,
            "prediction_chunks": len(prediction_records),
            "summary_rows": summary_counts,
            "uq_rows": uq_counts,
            "feature_values": sum(
                len(values) for values in features["features"].values()
            ),
            "feature_null_values": sum(
                value is None
                for values in features["features"].values()
                for value in values
            ),
        },
        "source": {
            "analysis_directory": str(ANALYSIS_DIRECTORY),
            "analysis_manifest_sha256": sources["analysis_manifest_sha256"],
            "uq_directory": str(UQ_DIRECTORY),
            "uq_manifest_sha256": sources["uq_manifest_sha256"],
            "panel_amendment_sha256": sha256_file(repository_root / PANEL_AMENDMENT),
            "uq_amendment_sha256": sha256_file(repository_root / UQ_AMENDMENT),
            "selection_weight_sum": 609,
        },
        "prediction_chunks": prediction_records,
        "files": files,
    }
    _write_json(output_directory / "index.json", index, pretty=True)
    report = verify_g59_frontend_bundle(output_directory)
    if archive_path is not None:
        write_deterministic_zip(output_directory, archive_path)
        report["archive"] = verify_frontend_archive(output_directory, archive_path)
    return report


def _verify_table(
    payload: Mapping[str, Any],
    table_name: str,
    expected_rows: int,
    expected_key: Sequence[str],
) -> list[dict[str, Any]]:
    _require(payload.get("encoding") == "row_array_table_v1", "wrong table encoding")
    _require(payload.get("table_name") == table_name, f"wrong {table_name} table")
    _require(
        payload.get("primary_key") == list(expected_key), f"wrong {table_name} key"
    )
    columns = payload.get("columns")
    rows = payload.get("rows")
    _require(isinstance(columns, list) and len(columns) == len(set(columns)), "columns")
    _require(
        isinstance(rows, list) and len(rows) == expected_rows, f"{table_name} rows"
    )
    _require(all(len(row) == len(columns) for row in rows), f"{table_name} width")
    records = list(_table_records(payload))
    keys = [tuple(row[column] for column in expected_key) for row in records]
    _require(len(keys) == len(set(keys)), f"duplicate {table_name} key")
    return records


def verify_g59_frontend_bundle(output_directory: Path) -> dict[str, Any]:
    output_directory = output_directory.resolve()
    index_path = output_directory / "index.json"
    _require(index_path.is_file(), "missing frontend index")
    index = _read_json(index_path)
    schema = _read_json(output_directory / "schema/index.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(index)
    _require(index.get("artifact_id") == ARTIFACT_ID, "wrong frontend artifact")
    _require(index.get("schema_version") == SCHEMA_VERSION, "wrong schema version")
    _require(
        index["release_scope"]["public_dashboard_release_authorized"] is False,
        "public release claim",
    )
    _require(
        index["release_scope"]["validated_predictor_claim"] is False,
        "validated predictor claim",
    )

    expected_files = {"index.json"}
    for record in index["files"]:
        relative = str(record["path"])
        path = output_directory / relative
        _require(
            path.resolve().is_relative_to(output_directory), f"unsafe path: {relative}"
        )
        _require(path.is_file(), f"missing frontend file: {relative}")
        _require(path.stat().st_size == int(record["bytes"]), f"size drift: {relative}")
        _require(sha256_file(path) == record["sha256"], f"hash drift: {relative}")
        expected_files.add(relative)
    actual_files = {
        str(path.relative_to(output_directory))
        for path in output_directory.rglob("*")
        if path.is_file()
    }
    _require(actual_files == expected_files, "unmanifested frontend files")

    catalog = _read_json(output_directory / "catalog.json")
    tasks = catalog["tasks"]
    _require(len(tasks) == EXPECTED_COUNTS["corpus_tasks"], "catalog task census")
    task_uuids = {row["task_uuid"] for row in tasks}
    current = {row["task_uuid"] for row in tasks if row["selected_for_current_panel"]}
    current_gradeable = {
        row["task_uuid"]
        for row in tasks
        if row["selected_for_current_panel"] and row["gradeable_for_campaign_scoring"]
    }
    historical = {
        row["task_uuid"]
        for row in tasks
        if row["selected_for_historical_final_v4_panel"]
    }
    historical_gradeable = {
        row["task_uuid"]
        for row in tasks
        if row["historical_final_v4_gradeable_panel_member"]
    }
    _require(len(current) == len(current_gradeable) == 96, "current denominator drift")
    _require(
        len(historical) == 96 and len(historical_gradeable) == 80,
        "historical denominator drift",
    )
    _require(
        sum(row["current_selection_weight"] or 0 for row in tasks) == 609, "weight sum"
    )
    _require(
        sum(row["gradeable_for_campaign_scoring"] for row in tasks) == 609,
        "gradeability census",
    )

    features = _read_json(output_directory / "features.json")
    _require(set(features["task_uuid"]) == task_uuids, "feature task mismatch")
    _require(
        len(features["features"]) == EXPECTED_COUNTS["selected_features"],
        "feature count",
    )
    _require(
        all(len(values) == 718 for values in features["features"].values()),
        "feature width",
    )

    observations = _verify_table(
        _read_json(output_directory / "observations.json"),
        "observations",
        1728,
        ["task_uuid", "solver_uuid"],
    )
    coverage = _verify_table(
        _read_json(output_directory / "coverage.json"),
        "coverage",
        1728,
        ["task_uuid", "solver_uuid"],
    )
    observation_keys = {(row["task_uuid"], row["solver_uuid"]) for row in observations}
    coverage_keys = {(row["task_uuid"], row["solver_uuid"]) for row in coverage}
    _require(observation_keys == coverage_keys, "observation/coverage mismatch")
    _require({row["task_uuid"] for row in observations} == current, "observation panel")
    _require(
        {row["observed_outcome"] for row in observations} <= {"fail", "success"},
        "outcomes",
    )
    _require(
        all(row["enters_binary_label_table"] is True for row in coverage),
        "coverage labels",
    )

    variants = {row["solver_uuid"] for row in catalog["solver_variants"]}
    _require(len(variants) == 18, "variant census")
    total_predictions = 0
    for chunk in index["prediction_chunks"]:
        rows = _verify_table(
            _read_json(output_directory / chunk["path"]),
            "predictions",
            1436,
            ["task_uuid", "solver_uuid", "feature_arm"],
        )
        _require(
            {row["solver_uuid"] for row in rows} == {chunk["solver_uuid"]},
            "prediction solver",
        )
        _require(
            Counter(row["feature_arm"] for row in rows)
            == {"with_jw": 718, "without_jw": 718},
            "prediction arms",
        )
        _require({row["task_uuid"] for row in rows} == task_uuids, "prediction tasks")
        total_predictions += len(rows)
    _require(total_predictions == 25848, "prediction census")

    terminal = _verify_table(
        _read_json(output_directory / "dmrg_terminal_cells.json"),
        "dmrg_terminal_cells",
        96,
        ["task_uuid"],
    )
    _require({row["task_uuid"] for row in terminal} == current, "DMRG terminal panel")
    _require(
        Counter(row["source_cohort"] for row in terminal)
        == {"g59_promoted_panel_rerun": 30, "g50_retained_terminal_intake": 66},
        "DMRG source census",
    )
    _require(
        all(
            row["terminal_energy_hartree"] is None
            or row["terminal_state"] == "completed"
            for row in terminal
        ),
        "noncompleted terminal energy",
    )
    _verify_table(
        _read_json(output_directory / "g59_parent_terminal_cells.json"),
        "g59_parent_terminal_cells",
        86,
        ["task_uuid", "solver_family_id"],
    )

    uncertainty = _read_json(output_directory / "uncertainty.json")
    _verify_table(
        uncertainty["tables"]["design_based_ratios"],
        "design_based_ratios",
        18,
        UQ_TABLES["design_based_ratios"],
    )
    posterior = _verify_table(
        uncertainty["tables"]["per_task_posterior"],
        "per_task_posterior",
        12924,
        UQ_TABLES["per_task_posterior"],
    )
    _require({row["task_uuid"] for row in posterior} == task_uuids, "posterior tasks")
    _require(uncertainty["report"]["ratio_of_record"] == "design_based", "ratio role")
    _require(uncertainty["report"]["validated_predictor_claim"] is False, "UQ claim")

    definitions = _read_json(output_directory / "definitions.json")
    denominators = definitions["denominators"]
    _require(denominators["current_panel"]["n"] == 96, "current denominator")
    _require(
        denominators["current_gradeable_panel"]["n"] == 96, "gradeable denominator"
    )
    _require(
        denominators["historical_final_v4_gradeable_sensitivity"]["n"] == 80,
        "historical denominator",
    )

    return {
        "status": "pass",
        "artifact_id": ARTIFACT_ID,
        "files_verified": len(index["files"]),
        "tasks_verified": len(tasks),
        "features_verified": len(features["features"]),
        "observations_verified": len(observations),
        "predictions_verified": total_predictions,
        "dmrg_terminal_cells_verified": len(terminal),
        "uq_posterior_rows_verified": len(posterior),
        "bundle_bytes": sum(int(record["bytes"]) for record in index["files"])
        + index_path.stat().st_size,
        "index_sha256": sha256_file(index_path),
    }
