"""Artifact orchestration for the frozen interim ML-v2 manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.interim import (
    MODEL_LABELS,
    MODEL_NAMES,
    PRIMARY_MODELS,
    SOURCE_OUTCOME_VOCABULARY,
    calibration_records,
    family_balanced_scores,
    family_bootstrap,
    load_instance_tasks,
    load_pinned_inputs,
    majority_oof,
    oof_probabilities,
    scored_label_frame,
    sha256_file,
    stable_json_dump,
    stratum_status,
)


PROTOCOLS = (
    "leave_one_family_out",
    "random_5fold_leakage_diagnostic_only",
)


def _scored(
    data: pd.DataFrame, probabilities: np.ndarray, bootstrap_resamples: int
) -> dict[str, Any]:
    return {
        "scores": family_balanced_scores(data, probabilities),
        "family_bootstrap_95": family_bootstrap(
            data, probabilities, resamples=bootstrap_resamples
        ),
    }


def _prediction_rows(
    data: pd.DataFrame,
    probabilities: np.ndarray,
    solver: str,
    campaign: str,
    protocol: str,
    model: str,
    feature_set: str,
) -> list[dict[str, Any]]:
    rows = []
    for position, source in data.reset_index(drop=True).iterrows():
        rows.append({
            "task_uuid": source["task_uuid"],
            "solver": solver,
            "campaign": campaign,
            "family": source["family"],
            "tier": source["tier"],
            "protocol": protocol,
            "diagnostic_only": protocol.endswith("diagnostic_only"),
            "model": model,
            "feature_set": feature_set,
            "actual_outcome": source["outcome"],
            "probabilities": {
                label: float(probabilities[position, index])
                for index, label in enumerate(MODEL_LABELS)
            },
        })
    return rows


def _calibration_rows(
    data: pd.DataFrame,
    probabilities: np.ndarray,
    solver: str,
    campaign: str,
    protocol: str,
    model: str,
    feature_set: str,
) -> list[dict[str, Any]]:
    prefix = {
        "solver": solver,
        "campaign": campaign,
        "protocol": protocol,
        "diagnostic_only": protocol.endswith("diagnostic_only"),
        "model": model,
        "feature_set": feature_set,
    }
    return [prefix | row for row in calibration_records(data, probabilities)]


def _baseline_evaluations(
    data: pd.DataFrame,
    protocol: str,
    grids: Mapping[str, Mapping[str, Sequence[Any]]],
    bootstrap_resamples: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, np.ndarray]]:
    majority = majority_oof(data, protocol)
    log_dimension, _ = oof_probabilities(
        data, ["log_fci_dim"], "size_log_dimension", protocol, {}
    )
    spline, _ = oof_probabilities(
        data, ["n_elec", "n_orbs"], "size_spline_gate", protocol, {}
    )
    probabilities = {
        "majority_class": majority,
        "size_log_dimension": log_dimension,
        "size_spline_gate": spline,
    }
    return (
        {
            name: _scored(data, value, bootstrap_resamples)
            for name, value in probabilities.items()
        },
        probabilities,
    )


def _cell_data(
    labels: pd.DataFrame,
    features: pd.DataFrame,
    solver: str,
    campaign: str,
    task_filter: set[str] | None = None,
) -> pd.DataFrame:
    data = labels[
        labels["solver"].eq(solver) & labels["campaign"].eq(campaign)
    ].copy()
    if task_filter is not None:
        data = data[data["task_uuid"].isin(task_filter)].copy()
    merged = data.merge(
        features, on="task_uuid", how="inner", validate="one_to_one"
    )
    return merged.sort_values("task_uuid", kind="stable").reset_index(drop=True)


def _evaluate_feature_set(
    data: pd.DataFrame,
    solver: str,
    campaign: str,
    feature_set: str,
    columns: Sequence[str],
    models: Sequence[str],
    protocols: Sequence[str],
    grids: Mapping[str, Mapping[str, Sequence[Any]]],
    bootstrap_resamples: int,
    include_predictions: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    results = []
    predictions = []
    calibration = []
    folds = []
    status, count_evidence = stratum_status(data)
    for protocol in protocols:
        if status != "ok":
            for model in models:
                results.append({
                    "status": "insufficient_data",
                    "solver": solver,
                    "campaign": campaign,
                    "protocol": protocol,
                    "diagnostic_only": protocol.endswith("diagnostic_only"),
                    "model": model,
                    "feature_set": feature_set,
                    "counts": count_evidence,
                    "score": None,
                    "baselines": None,
                })
            continue
        baselines, baseline_probabilities = _baseline_evaluations(
            data, protocol, grids, bootstrap_resamples
        )
        for baseline_name, baseline_probability in baseline_probabilities.items():
            calibration.extend(_calibration_rows(
                data, baseline_probability, solver, campaign, protocol,
                baseline_name, feature_set,
            ))
        for model in models:
            probabilities, fold_records = oof_probabilities(
                data, columns, model, protocol, grids.get(model, {})
            )
            score = _scored(data, probabilities, bootstrap_resamples)
            results.append({
                "status": "ok",
                "solver": solver,
                "campaign": campaign,
                "protocol": protocol,
                "diagnostic_only": protocol.endswith("diagnostic_only"),
                "model": model,
                "model_role": "primary" if model in PRIMARY_MODELS else "sensitivity_only",
                "feature_set": feature_set,
                "counts": count_evidence,
                "score": score,
                "baselines": baselines,
            })
            folds.extend([
                {
                    "solver": solver,
                    "campaign": campaign,
                    "protocol": protocol,
                    "model": model,
                    "feature_set": feature_set,
                } | row
                for row in fold_records
            ])
            if include_predictions:
                predictions.extend(_prediction_rows(
                    data, probabilities, solver, campaign, protocol, model, feature_set
                ))
            calibration.extend(_calibration_rows(
                data, probabilities, solver, campaign, protocol, model, feature_set
            ))
    return results, predictions, calibration, folds


def _forward_selection(
    data: pd.DataFrame,
    solver: str,
    campaign: str,
    blocks: Mapping[str, Sequence[str]],
    grid: Mapping[str, Sequence[Any]],
) -> dict[str, Any]:
    status, counts = stratum_status(data)
    if status != "ok":
        return {
            "status": "insufficient_data",
            "solver": solver,
            "campaign": campaign,
            "counts": counts,
            "steps": [],
        }
    selected = ["a_size_dimension"]
    remaining = sorted(set(blocks) - set(selected))
    steps = []
    size_probability, _ = oof_probabilities(
        data, list(blocks["a_size_dimension"]), "ridge_logistic",
        "leave_one_family_out", grid,
    )
    current_score = family_balanced_scores(data, size_probability)
    steps.append({
        "step": 0,
        "added_block": "a_size_dimension",
        "selected_blocks": list(selected),
        "scores": current_score,
        "delta_average_precision": None,
    })
    while remaining:
        candidates = []
        for block in remaining:
            candidate_blocks = selected + [block]
            columns = [
                column for name in candidate_blocks for column in blocks[name]
            ]
            probability, _ = oof_probabilities(
                data, columns, "ridge_logistic", "leave_one_family_out", grid
            )
            score = family_balanced_scores(data, probability)
            candidates.append((score["average_precision"], block, score))
        _, chosen, chosen_score = max(candidates, key=lambda item: (item[0], item[1]))
        steps.append({
            "step": len(steps),
            "added_block": chosen,
            "selected_blocks": selected + [chosen],
            "scores": chosen_score,
            "delta_average_precision": (
                chosen_score["average_precision"] - current_score["average_precision"]
            ),
        })
        selected.append(chosen)
        remaining.remove(chosen)
        current_score = chosen_score
    return {
        "status": "ok",
        "solver": solver,
        "campaign": campaign,
        "counts": counts,
        "method": "grouped-CV forward selection using family-balanced average precision",
        "model": "ridge_logistic",
        "steps": steps,
        "narrative_block_order": selected,
    }


def _bundle_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "ml_v2_interim_1.schema.json",
        "title": "QB-GSEE ML v2 interim bundle",
        "type": "object",
        "required": [
            "bundle_version", "interim", "interim_label", "definitions",
            "source_outcome_vocabulary", "model_label_vocabulary",
            "manifest_sha256", "evaluations", "per_task_predictions",
        ],
        "properties": {
            "bundle_version": {"const": "ml-v2-interim-1"},
            "interim": {"const": True},
            "interim_label": {"const": "INTERIM (pre-mean-field feature set)"},
            "definitions": {"type": "object"},
            "source_outcome_vocabulary": {
                "const": list(SOURCE_OUTCOME_VOCABULARY)
            },
            "model_label_vocabulary": {"const": list(MODEL_LABELS)},
            "manifest_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "evaluations": {"type": "array", "items": {"type": "object"}},
            "per_task_predictions": {"type": "array", "items": {"type": "object"}},
        },
        "additionalProperties": True,
    }


def _readme(manifest: Mapping[str, Any], pivotal: list[dict[str, Any]]) -> str:
    return "\n".join([
        "# INTERIM (pre-mean-field feature set): ML v2",
        "",
        "These artifacts are interim and must not headline the paper.",
        "",
        f"- Feature table SHA-256: {manifest['inputs']['feature_table']['sha256']}",
        f"- Metadata SHA-256: {manifest['inputs']['feature_metadata']['sha256']}",
        f"- Labels: metrics spec {manifest['inputs']['labels']['metrics_spec_version']}",
        f"- Universal core columns: {manifest['features']['universal_core']['n_columns']}",
        f"- Solver-campaign cells: {len(manifest['inputs']['labels']['solver_campaign_cells'])}",
        "- Headline protocol: exact leave-one-family-out",
        "- Random-fold values: leakage diagnostic only",
        "- Every score is family-balanced and packaged with both size baselines and majority.",
        f"- Pivotal size-gate flags (plain numeric records, no interpretation): {len(pivotal)}",
        "",
    ])


def run_interim_evaluation(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("interim") or manifest.get("manifest_version") != "ml-v2-interim-1":
        raise ValueError("Refusing to run without the committed interim manifest")
    features, _, metrics = load_pinned_inputs(repo_root)
    labels = scored_label_frame(
        metrics, load_instance_tasks(repo_root / "problem_instances")
    )
    universal = manifest["features"]["universal_core"]
    grids = manifest["models"]["hyperparameter_grids"]
    bootstrap_resamples = int(manifest["validation"]["family_bootstrap_resamples"])
    all_results: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []
    all_calibration: list[dict[str, Any]] = []
    all_folds: list[dict[str, Any]] = []
    importances = []

    for cell in manifest["inputs"]["labels"]["solver_campaign_cells"]:
        solver, campaign = cell["solver"], cell["campaign"]
        data = _cell_data(labels, features, solver, campaign)
        result, prediction, calibration, folds = _evaluate_feature_set(
            data, solver, campaign, "universal_core",
            universal["columns"], MODEL_NAMES, PROTOCOLS, grids,
            bootstrap_resamples, True,
        )
        all_results.extend(result)
        all_predictions.extend(prediction)
        all_calibration.extend(calibration)
        all_folds.extend(folds)
        importances.append(_forward_selection(
            data, solver, campaign, universal["blocks"], grids["ridge_logistic"]
        ))

        for extension in manifest["features"]["domain_extensions"]:
            extension_data = _cell_data(
                labels, features, solver, campaign, set(extension["task_uuids"])
            )
            columns = universal["columns"] + extension["columns"]
            result, prediction, calibration, folds = _evaluate_feature_set(
                extension_data, solver, campaign, extension["name"],
                columns, PRIMARY_MODELS, ["leave_one_family_out"], grids,
                bootstrap_resamples, False,
            )
            all_results.extend(result)
            all_calibration.extend(calibration)
            all_folds.extend(folds)

    pivotal = []
    for record in all_results:
        if record["status"] != "ok" or record["diagnostic_only"]:
            continue
        model_ap = record["score"]["scores"]["average_precision"]
        size_scores = {
            name: record["baselines"][name]["scores"]["average_precision"]
            for name in ("size_log_dimension", "size_spline_gate")
        }
        if model_ap > max(size_scores.values()):
            pivotal.append({
                "solver": record["solver"],
                "campaign": record["campaign"],
                "model": record["model"],
                "feature_set": record["feature_set"],
                "model_average_precision": model_ap,
                "size_baseline_average_precision": size_scores,
            })

    sort_key = lambda row: tuple(str(row.get(key, "")) for key in (
        "solver", "campaign", "feature_set", "protocol", "model",
        "task_uuid", "outcome", "bin", "fold",
    ))
    all_results.sort(key=sort_key)
    all_predictions.sort(key=sort_key)
    all_calibration.sort(key=sort_key)
    all_folds.sort(key=sort_key)
    importances.sort(key=sort_key)
    pivotal.sort(key=sort_key)

    analysis_dir = repo_root / "analysis/ml_v2"
    stable_json_dump(all_results, analysis_dir / "results.json")
    stable_json_dump(all_predictions, analysis_dir / "predictions.json")
    stable_json_dump(all_calibration, analysis_dir / "calibration.json")
    stable_json_dump(all_folds, analysis_dir / "folds.json")
    stable_json_dump(importances, analysis_dir / "feature_importances.json")
    stable_json_dump(pivotal, analysis_dir / "pivotal_size_gate_flags.json")
    (analysis_dir / "README.md").write_text(
        _readme(manifest, pivotal), encoding="utf-8"
    )

    manifest_sha = sha256_file(manifest_path)
    bundle = {
        "$schema": "ml_v2_interim_1.schema.json",
        "bundle_version": "ml-v2-interim-1",
        "interim": True,
        "interim_label": "INTERIM (pre-mean-field feature set)",
        "definitions": {
            "headline": "Exact leave-one-family-out; family-balanced metrics.",
            "leakage_diagnostic": "Random five-fold results are diagnostic only.",
            "score_packaging": "Every model score contains majority and both size baselines.",
            "insufficient_data": "Predeclared task/family/class floor was not met.",
            "not_attempted": "Coverage-only source state; never a model label.",
        },
        "source_outcome_vocabulary": list(SOURCE_OUTCOME_VOCABULARY),
        "model_label_vocabulary": list(MODEL_LABELS),
        "manifest_sha256": manifest_sha,
        "evaluations": all_results,
        "per_task_predictions": all_predictions,
        "calibration": all_calibration,
        "feature_importances": importances,
        "pivotal_size_gate_flags": pivotal,
    }
    dashboard = repo_root / "scripts/dashboard_data"
    stable_json_dump(bundle, dashboard / "ml_v2_interim_1.json")
    stable_json_dump(_bundle_schema(), dashboard / "ml_v2_interim_1.schema.json")
    return {
        "n_evaluations": len(all_results),
        "n_predictions": len(all_predictions),
        "n_pivotal_flags": len(pivotal),
        "bundle": str(dashboard / "ml_v2_interim_1.json"),
    }
