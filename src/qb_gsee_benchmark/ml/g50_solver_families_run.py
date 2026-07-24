"""Deterministic G50 solver-family solvability analysis."""

from __future__ import annotations

import json
import math
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from qb_gsee_benchmark.metrics.v1_8 import classify_outcome_v1_8
from qb_gsee_benchmark.ml.core_set import (
    _require,
    block_aware_distance,
    build_block_models,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.g50_solver_families import (
    PROTOCOL_ID,
    _zip_csv,
    _zip_json,
    canonical_family_map,
    derive_feature_policy,
    g50_variant_rows,
    load_preregistration,
    resolve_input_path,
    run_outcome_blind_preflight,
    verify_inputs,
)

MODEL_ID = "shared_block_distance_knn_k15"
ARMS = ("with_jw", "without_jw")
METRICS = (
    "average_precision_success",
    "roc_auc",
    "brier",
    "balanced_accuracy",
    "mcc",
)
TERMINAL_CELLS = {
    "shci": (
        "g50_shci_clean_slate_2026-07_v1",
        "SHCI_pt_2e-5_nchunks8",
        "SHCI_pt_2e-5_nchunks8",
    ),
    "trimci": (
        "g50_trimci_clean_slate_2026-07_v1",
        "TrimCI_default",
        "TrimCI_default",
    ),
    "ipie": (
        "g50_ipie_swing_clean_slate_2026-07_v2_regimefix",
        "ipie_uhf_trial",
        "ipie_uhf_trial",
    ),
}


def _load_tasks(root: Path) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "problem_instances").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for raw in document.get("tasks", []):
            task = dict(raw)
            task_uuid = str(task["task_uuid"])
            _require(task_uuid not in tasks, f"duplicate task UUID: {task_uuid}")
            task["family"] = path.parent.name
            task["problem_instance_uuid"] = document.get("problem_instance_uuid")
            tasks[task_uuid] = task
    return tasks


def load_size_sector_amendment(
    root: Path, amendment_path: Path, preregistration_path: Path
) -> tuple[dict[str, Any], pd.DataFrame]:
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    _require(
        amendment.get("artifact_id") == "ml_g50_size_sector_backfill_amendment_v1",
        "wrong size-sector amendment",
    )
    _require(amendment.get("frozen_before_model_fitting") is True, "unfrozen amendment")
    _require(
        amendment["prior_exposure"]["scientific_outcomes_consumed"] is False,
        "amendment consumed outcomes",
    )
    parent = amendment["parent_preregistration"]
    _require(
        parent["sha256"] == sha256_file(preregistration_path),
        "parent preregistration changed",
    )
    specification = amendment["backfill"]
    path = root / str(specification["path"])
    _require(path.is_file(), f"missing size-sector backfill: {path}")
    _require(
        sha256_file(path) == specification["sha256"], "size-sector backfill changed"
    )
    frame = pd.read_csv(path)
    _require(
        len(frame) == int(specification["row_count"]), "backfill row count changed"
    )
    _require(frame["task_uuid"].is_unique, "duplicate size-sector backfill task")
    _require(set(frame["metadata_ms2"]) == {0}, "unexpected metadata MS2 backfill")
    return amendment, frame


def build_size_sector_frame(
    features: pd.DataFrame, backfill: pd.DataFrame
) -> pd.DataFrame:
    """Build the frozen strong comparator inputs with no generic imputation."""
    columns = [
        "task_uuid",
        "n_orbs",
        "n_elec",
        "log_fci_dim",
        "ms2",
        "lattice_filling_electrons_per_site",
    ]
    frame = features[columns].copy().set_index("task_uuid")
    backfill = backfill.set_index("task_uuid")
    missing = set(map(str, frame.index[frame["log_fci_dim"].isna()]))
    _require(
        missing == set(map(str, backfill.index)),
        "size-sector backfill coverage changed",
    )
    for task, row in backfill.iterrows():
        _require(
            pd.isna(frame.at[task, "log_fci_dim"]),
            f"unexpected log dimension backfill: {task}",
        )
        _require(pd.isna(frame.at[task, "ms2"]), f"unexpected MS2 backfill: {task}")
        frame.at[task, "log_fci_dim"] = float(row["derived_log_fci_dim"])
        frame.at[task, "ms2"] = float(row["metadata_ms2"])
    frame["abs_ms2_or_filling"] = np.where(
        frame["lattice_filling_electrons_per_site"].notna(),
        frame["lattice_filling_electrons_per_site"],
        frame["ms2"].abs(),
    )
    selected = frame[["n_orbs", "n_elec", "log_fci_dim", "abs_ms2_or_filling"]]
    _require(
        bool(np.isfinite(selected.to_numpy(dtype=float)).all()),
        "unresolved size-sector input",
    )
    return selected


def _variant_maps(
    variants: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, float], dict[str, Any]]]:
    by_name = {str(row["solver_short_name"]): dict(row) for row in variants}
    by_resource = {
        (str(row["solver_family_id"]), float(row["resource_value"])): dict(row)
        for row in variants
        if row["resource_value"] is not None
    }
    _require(len(by_name) == len(variants), "duplicate G50 variant name")
    return by_name, by_resource


def _solution_documents(
    archive: Path, manifest_rows: Sequence[Mapping[str, Any]]
) -> dict[tuple[str, str], dict[str, Any]]:
    documents: dict[tuple[str, str], dict[str, Any]] = {}
    with zipfile.ZipFile(archive) as handle:
        for row in manifest_rows:
            if row.get("package_status") != "terminal_solution":
                continue
            member = "intake/" + str(row["intake_path"])
            document = json.loads(handle.read(member))
            key = (str(row["solver"]), str(row["task_uuid"]))
            _require(key not in documents, f"duplicate terminal document: {key}")
            documents[key] = document
    return documents


def _result(document: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if document is None:
        return None
    rows = document.get("solution_data")
    return (
        rows[0]
        if isinstance(rows, list) and rows and isinstance(rows[0], dict)
        else None
    )


def _scored_observation(
    *,
    task_uuid: str,
    task: Mapping[str, Any],
    canonical_family: str,
    variant: Mapping[str, Any],
    energy: Any,
    source: str,
    reason_override: str | None = None,
    raw_status: str | None = None,
    force_fail: bool = False,
) -> dict[str, Any]:
    scored = classify_outcome_v1_8(energy, task)
    success = (
        not force_fail
        and scored["metric_status"] == "ok"
        and scored["outcome"] == "success"
    )
    if reason_override is not None:
        reason = reason_override
    elif scored["metric_status"] != "ok":
        reason = str(scored["metric_status"])
    elif scored["outcome"] == "miss":
        reason = "accuracy_outside_threshold"
    elif scored["outcome"] == "success":
        reason = "accuracy_within_threshold"
    else:
        reason = "metric_indeterminate"
    return {
        "task_uuid": task_uuid,
        "canonical_family": canonical_family,
        "solver_family_id": variant["solver_family_id"],
        "solver_family_uuid": variant["solver_family_uuid"],
        "solver_short_name": variant["solver_short_name"],
        "solver_uuid": variant["solver_uuid"],
        "solver_variant_id": variant["solver_variant_id"],
        "resource_ladder_id": variant["resource_ladder_id"],
        "resource_axis_name": variant["resource_axis_name"],
        "resource_value": variant["resource_value"],
        "resource_units": variant["resource_units"],
        "resource_rank": variant["resource_rank"],
        "energy_hartree": scored["energy"],
        "observed_outcome": "success" if success else "fail",
        "metric_outcome_annotation": scored["outcome"],
        "metric_status_annotation": scored["metric_status"],
        "label_reason_annotation": reason,
        "raw_status_annotation": raw_status,
        "observation_source": source,
        "absolute_error_hartree": scored["absolute_error"],
        "graded_residual": scored["graded_residual"],
        "reference_energy_hartree": scored["reference_energy"],
        "threshold_hartree": scored["threshold"],
        "reference_grade": scored["reference_grade"],
    }


def normalize_g50_outcomes(
    root: Path,
    preregistration: Mapping[str, Any],
    variants: Sequence[Mapping[str, Any]],
    canonical: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize terminal and rung outcomes under the frozen binary contract."""
    tasks = _load_tasks(root)
    terminal_archive = resolve_input_path(
        root, preregistration["inputs"]["g50_terminal_intake"]
    )
    metrics_path = resolve_input_path(
        root, preregistration["inputs"]["g50_terminal_metrics"]
    )
    recovery_archive = resolve_input_path(
        root, preregistration["inputs"]["g50_trimci_recovery"]
    )
    manifest = _zip_json(terminal_archive, "BASELINE_MANIFEST.json")
    contract = list(manifest["rows"])
    selected_tasks = sorted({str(row["task_uuid"]) for row in contract})
    _require(len(selected_tasks) == 96, "G50 selected task count changed")
    _require(set(selected_tasks) <= set(tasks) & set(canonical), "unknown G50 task")
    contract_lookup = {
        (str(row["solver"]), str(row["task_uuid"])): row for row in contract
    }
    _require(len(contract_lookup) == 384, "duplicate terminal contract row")
    documents = _solution_documents(terminal_archive, contract)
    by_name, by_resource = _variant_maps(variants)

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    primitive_lookup: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for primitive in metrics["primitives"]:
        key = (
            str(primitive.get("campaign")),
            str(primitive.get("solver")),
            str(primitive.get("task_uuid")),
        )
        if any(key[:2] == cell[:2] for cell in TERMINAL_CELLS.values()):
            _require(
                key not in primitive_lookup,
                f"duplicate terminal metric primitive: {key}",
            )
            primitive_lookup[key] = primitive

    observations: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []

    def add_coverage(
        task_uuid: str,
        variant: Mapping[str, Any],
        status: str,
        reason: str,
        labeled: bool,
    ) -> None:
        coverage.append(
            {
                "task_uuid": task_uuid,
                "canonical_family": canonical[task_uuid],
                "solver_family_id": variant["solver_family_id"],
                "solver_short_name": variant["solver_short_name"],
                "solver_uuid": variant["solver_uuid"],
                "solver_variant_id": variant["solver_variant_id"],
                "resource_ladder_id": variant["resource_ladder_id"],
                "resource_value": variant["resource_value"],
                "coverage_status": status,
                "coverage_reason": reason,
                "enters_binary_label_table": labeled,
            }
        )

    for family, detail_key, energy_key in (
        ("dmrg", "dmrg_details", "energy"),
        ("shci", "shci_details", "variational_energy"),
    ):
        family_variants = sorted(
            (
                row
                for row in variants
                if row["solver_family_id"] == family
                and row["resource_value"] is not None
            ),
            key=lambda row: int(row["resource_rank"]),
        )
        for task_uuid in selected_tasks:
            result = _result(documents.get((family, task_uuid)))
            details = {} if result is None else result.get("solution_details", {})
            solver_details = (
                details.get(detail_key, {}) if isinstance(details, dict) else {}
            )
            result_data = (
                solver_details.get("result_data", {})
                if isinstance(solver_details, dict)
                else {}
            )
            rung_rows = (
                result_data.get("completed_rungs", [])
                if isinstance(result_data, dict)
                else []
            )
            observed: dict[float, Mapping[str, Any]] = {}
            for rung in rung_rows if isinstance(rung_rows, list) else []:
                value = float(
                    rung["bond_dimension"] if family == "dmrg" else rung["eps_var"]
                )
                _require(
                    value not in observed,
                    f"duplicate {family} rung: {task_uuid}/{value}",
                )
                observed[value] = rung
            raw = str(contract_lookup[(family, task_uuid)].get("harness_status"))
            for variant in family_variants:
                value = float(variant["resource_value"])
                rung = observed.get(value)
                if rung is None:
                    observations.append(
                        _scored_observation(
                            task_uuid=task_uuid,
                            task=tasks[task_uuid],
                            canonical_family=canonical[task_uuid],
                            variant=variant,
                            energy=None,
                            source=f"{family}_implicit_attempted_rung",
                            reason_override="missing_attempted_rung",
                            raw_status=raw,
                            force_fail=True,
                        )
                    )
                    add_coverage(
                        task_uuid, variant, "missing_attempted_rung", raw, True
                    )
                else:
                    observations.append(
                        _scored_observation(
                            task_uuid=task_uuid,
                            task=tasks[task_uuid],
                            canonical_family=canonical[task_uuid],
                            variant=variant,
                            energy=rung[energy_key],
                            source=f"{family}_completed_rung",
                            raw_status=raw,
                        )
                    )
                    add_coverage(task_uuid, variant, "observed_rung", raw, True)

    recovery = _zip_csv(recovery_archive, "UNFOLDED_RUNG_MATRIX.csv")
    _require(len(recovery) == 38 * 7, "TrimCI recovery matrix changed")
    recovery_lookup = {
        (str(row["task_uuid"]), int(row["target_n_dets"])): row for row in recovery
    }
    _require(len(recovery_lookup) == len(recovery), "duplicate TrimCI recovery cell")
    trimci_variants = sorted(
        (
            row
            for row in variants
            if row["solver_family_id"] == "trimci" and row["resource_value"] is not None
        ),
        key=lambda row: int(row["resource_rank"]),
    )
    for task_uuid in selected_tasks:
        for variant in trimci_variants:
            target = int(variant["resource_value"])
            row = recovery_lookup.get((task_uuid, target))
            if row is None:
                add_coverage(
                    task_uuid,
                    variant,
                    "outside_recovery_parent_set",
                    "parent_not_timeout_recovery_scope",
                    False,
                )
                continue
            status = str(row["rung_status"])
            if status != "observed":
                add_coverage(
                    task_uuid,
                    variant,
                    "right_censored",
                    str(row["right_censor_reason"]),
                    False,
                )
                continue
            observations.append(
                _scored_observation(
                    task_uuid=task_uuid,
                    task=tasks[task_uuid],
                    canonical_family=canonical[task_uuid],
                    variant=variant,
                    energy=row["energy_hartree"],
                    source="trimci_recovered_checkpoint",
                    raw_status=status,
                )
            )
            add_coverage(
                task_uuid,
                variant,
                "observed_recovered_rung",
                "checkpoint_emitted",
                True,
            )

    for contract_family, (campaign, solver, variant_name) in TERMINAL_CELLS.items():
        variant = by_name[variant_name]
        for task_uuid in selected_tasks:
            contract_row = contract_lookup[(contract_family, task_uuid)]
            primitive = primitive_lookup.get((campaign, solver, task_uuid))
            result = _result(documents.get((contract_family, task_uuid)))
            energy = (
                primitive.get("energy")
                if primitive is not None
                else (None if result is None else result.get("energy"))
            )
            if primitive is not None:
                _require(
                    primitive.get("metric_status") == "ok", "non-ok terminal primitive"
                )
            force_fail = primitive is None or primitive.get("outcome") != "success"
            metric_annotation = (
                "not_scored" if primitive is None else str(primitive["outcome"])
            )
            reason = None
            if primitive is None:
                reason = f"not_scored:{contract_row.get('harness_status')}:{contract_row.get('package_status')}"
            observation = _scored_observation(
                task_uuid=task_uuid,
                task=tasks[task_uuid],
                canonical_family=canonical[task_uuid],
                variant=variant,
                energy=energy,
                source="terminal_metrics_v1_9",
                reason_override=reason,
                raw_status=str(contract_row.get("harness_status")),
                force_fail=force_fail,
            )
            observation["metric_outcome_annotation"] = metric_annotation
            observations.append(observation)
            add_coverage(
                task_uuid,
                variant,
                "terminal_contract",
                str(contract_row.get("package_status")),
                True,
            )

    observation_keys = {(row["task_uuid"], row["solver_uuid"]) for row in observations}
    coverage_keys = {(row["task_uuid"], row["solver_uuid"]) for row in coverage}
    _require(
        len(observation_keys) == len(observations) == 1113,
        f"normalized label census changed: {len(observations)}",
    )
    _require(
        len(coverage_keys) == len(coverage) == 1728,
        f"coverage census changed: {len(coverage)}",
    )
    _require(
        sum(
            row["observation_source"] == "trimci_recovered_checkpoint"
            for row in observations
        )
        == 57,
        "TrimCI observed rung census changed",
    )
    observations.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["task_uuid"],
        )
    )
    coverage.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["task_uuid"],
        )
    )
    return observations, coverage


def binary_counts(values: Sequence[str]) -> dict[str, int]:
    counts = Counter(map(str, values))
    _require(set(counts) <= {"fail", "success"}, "non-binary observed outcome")
    return {label: int(counts[label]) for label in ("fail", "success")}


def variant_eligibility(
    observations: pd.DataFrame,
    variants: Sequence[Mapping[str, Any]],
    floor: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in variants:
        data = observations.loc[observations["solver_uuid"] == variant["solver_uuid"]]
        counts = binary_counts(data["observed_outcome"])
        family_counts = Counter(map(str, data["canonical_family"]))
        minimum_fold = min(
            (len(data) - count for count in family_counts.values()), default=0
        )
        checks = {
            "minimum_labeled_tasks": len(data) >= int(floor["minimum_labeled_tasks"]),
            "minimum_successes": counts["success"] >= int(floor["minimum_successes"]),
            "minimum_failures": counts["fail"] >= int(floor["minimum_failures"]),
            "minimum_families": len(family_counts) >= int(floor["minimum_families"]),
            "minimum_fold_training_tasks": minimum_fold
            >= int(floor["minimum_fold_training_tasks"]),
        }
        eligible = all(checks.values())
        rows.append(
            {
                "solver_family_id": variant["solver_family_id"],
                "solver_short_name": variant["solver_short_name"],
                "solver_uuid": variant["solver_uuid"],
                "solver_variant_id": variant["solver_variant_id"],
                "resource_ladder_id": variant["resource_ladder_id"],
                "resource_value": variant["resource_value"],
                "n_labels": len(data),
                "n_success": counts["success"],
                "n_fail": counts["fail"],
                "n_canonical_families": len(family_counts),
                "minimum_fold_training_tasks": minimum_fold,
                "model_status": "eligible" if eligible else "insufficient_data",
                "failed_floor_checks": ";".join(
                    key for key, value in checks.items() if not value
                ),
            }
        )
    return rows


def lofo_knn_probabilities(
    distance: np.ndarray,
    training_indices: np.ndarray,
    training_labels: np.ndarray,
    families: np.ndarray,
    task_uuids: Sequence[str],
    *,
    k: int,
) -> np.ndarray:
    """Predict all corpus tasks from labeled tasks outside each query family."""
    _require(
        distance.shape == (len(families), len(families)),
        "distance shape mismatch",
    )
    _require(
        len(training_indices) == len(training_labels),
        "training label shape mismatch",
    )
    tasks = np.asarray(list(map(str, task_uuids)), dtype=object)
    probabilities = np.empty(len(tasks), dtype=float)
    training_families = families[training_indices]
    for query in range(len(tasks)):
        positions = np.flatnonzero(training_families != families[query])
        _require(len(positions) >= k, f"fewer than k LOFO labels for {tasks[query]}")
        candidates = training_indices[positions]
        order = np.lexsort((tasks[candidates], distance[query, candidates]))
        selected_positions = positions[order[:k]]
        neighbors = training_indices[selected_positions]
        neighbor_distance = distance[query, neighbors]
        scale = float(np.median(neighbor_distance))
        if not math.isfinite(scale) or scale <= 1.0e-12:
            scale = 1.0
        weights = np.exp(-neighbor_distance / scale)
        probabilities[query] = (
            1.0 + float(weights @ training_labels[selected_positions])
        ) / (2.0 + float(weights.sum()))
    _require(bool(np.isfinite(probabilities).all()), "nonfinite KNN probability")
    return probabilities


def lofo_prevalence_probabilities(
    training_indices: np.ndarray,
    training_labels: np.ndarray,
    families: np.ndarray,
) -> np.ndarray:
    probabilities = np.empty(len(families), dtype=float)
    training_families = families[training_indices]
    for family in sorted(set(map(str, families))):
        queries = np.flatnonzero(families == family)
        keep = training_families != family
        y = training_labels[keep]
        _require(len(y) > 0, f"empty prevalence fold: {family}")
        probabilities[queries] = (1.0 + float(y.sum())) / (2.0 + len(y))
    return probabilities


def lofo_size_sector_probabilities(
    size_sector: pd.DataFrame,
    training_indices: np.ndarray,
    training_labels: np.ndarray,
    families: np.ndarray,
    *,
    seed: int,
) -> np.ndarray:
    values = size_sector.to_numpy(dtype=float)
    _require(bool(np.isfinite(values).all()), "nonfinite ridge input")
    probabilities = np.empty(len(families), dtype=float)
    training_families = families[training_indices]
    for family in sorted(set(map(str, families))):
        queries = np.flatnonzero(families == family)
        keep = training_families != family
        indexes = training_indices[keep]
        y = training_labels[keep]
        _require(len(y) >= 15, f"undersized ridge fold: {family}")
        if np.unique(y).size < 2:
            probabilities[queries] = (1.0 + float(y.sum())) / (2.0 + len(y))
            continue
        estimator = Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=4000, random_state=seed)),
            ]
        )
        estimator.fit(values[indexes], y)
        probabilities[queries] = estimator.predict_proba(values[queries])[:, 1]
    _require(bool(np.isfinite(probabilities).all()), "nonfinite ridge probability")
    return probabilities


def _family_weights(
    families: np.ndarray, multiplicities: Mapping[str, int] | None = None
) -> np.ndarray:
    counts = Counter(map(str, families))
    if multiplicities is None:
        multiplicities = {family: 1 for family in counts}
    total = int(sum(multiplicities.values()))
    _require(total > 0, "empty family weighting")
    return np.asarray(
        [
            float(multiplicities.get(str(family), 0)) / (total * counts[str(family)])
            for family in families
        ]
    )


def _weighted_mcc(y: np.ndarray, predicted: np.ndarray, weights: np.ndarray) -> float:
    tp = float(weights[(y == 1) & (predicted == 1)].sum())
    tn = float(weights[(y == 0) & (predicted == 0)].sum())
    fp = float(weights[(y == 0) & (predicted == 1)].sum())
    fn = float(weights[(y == 1) & (predicted == 0)].sum())
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return 0.0 if denominator <= 0 else (tp * tn - fp * fn) / denominator


def family_balanced_metrics(
    y: np.ndarray, probability: np.ndarray, weights: np.ndarray
) -> dict[str, float | None]:
    active = weights > 0
    y_active = y[active]
    probability_active = probability[active]
    weight_active = weights[active]
    weight_active = weight_active / weight_active.sum()
    predicted = (probability_active > 0.5).astype(int)
    positive = float(weight_active[y_active == 1].sum())
    negative = float(weight_active[y_active == 0].sum())
    tp = float(weight_active[(y_active == 1) & (predicted == 1)].sum())
    tn = float(weight_active[(y_active == 0) & (predicted == 0)].sum())
    both = np.unique(y_active).size == 2
    return {
        "average_precision_success": (
            float(
                average_precision_score(
                    y_active, probability_active, sample_weight=weight_active
                )
            )
            if both
            else None
        ),
        "roc_auc": (
            float(
                roc_auc_score(y_active, probability_active, sample_weight=weight_active)
            )
            if both
            else None
        ),
        "brier": float(np.sum(weight_active * (probability_active - y_active) ** 2)),
        "balanced_accuracy": (
            None
            if positive <= 0 or negative <= 0
            else 0.5 * (tp / positive + tn / negative)
        ),
        "mcc": _weighted_mcc(y_active, predicted, weight_active),
    }


def _oriented_delta(metric: str, first: float, second: float) -> float:
    return second - first if metric == "brier" else first - second


def bootstrap_variant(
    *,
    variant: Mapping[str, Any],
    y: np.ndarray,
    families: np.ndarray,
    probability_sets: Mapping[tuple[str, str], np.ndarray],
    resamples: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Score one eligible variant using identical accepted family draws."""
    family_names = sorted(set(map(str, families)))
    rng = np.random.default_rng(seed)
    draw_weights: list[np.ndarray] = []
    attempted = 0
    while len(draw_weights) < resamples:
        attempted += 1
        _require(
            attempted <= resamples * 100,
            "unable to obtain two-class family draws",
        )
        counts = rng.multinomial(
            len(family_names),
            [1.0 / len(family_names)] * len(family_names),
        )
        weights = _family_weights(families, dict(zip(family_names, map(int, counts))))
        if np.unique(y[weights > 0]).size == 2:
            draw_weights.append(weights)

    point_weights = _family_weights(families)
    point: dict[tuple[str, str], dict[str, float | None]] = {}
    samples: dict[tuple[str, str], dict[str, list[float]]] = {}
    performance: list[dict[str, Any]] = []
    for key, probabilities in sorted(probability_sets.items()):
        point[key] = family_balanced_metrics(y, probabilities, point_weights)
        samples[key] = {metric: [] for metric in METRICS}
        for weights in draw_weights:
            scored = family_balanced_metrics(y, probabilities, weights)
            for metric in METRICS:
                _require(
                    scored[metric] is not None,
                    f"invalid bootstrap metric: {key}/{metric}",
                )
                samples[key][metric].append(float(scored[metric]))
        estimator, arm = key
        for metric in METRICS:
            values = np.asarray(samples[key][metric])
            performance.append(
                {
                    "solver_family_id": variant["solver_family_id"],
                    "solver_short_name": variant["solver_short_name"],
                    "solver_uuid": variant["solver_uuid"],
                    "estimator": estimator,
                    "feature_arm": arm,
                    "metric": metric,
                    "point": point[key][metric],
                    "lower_95": float(np.quantile(values, 0.025)),
                    "upper_95": float(np.quantile(values, 0.975)),
                    "accepted_family_draws": resamples,
                    "attempted_family_draws": attempted,
                    "orientation": (
                        "lower_is_better" if metric == "brier" else "higher_is_better"
                    ),
                }
            )

    comparisons = [
        (
            ("physics_knn", "with_jw"),
            ("lofo_prevalence", "not_applicable"),
            "with_jw_vs_prevalence",
        ),
        (
            ("physics_knn", "with_jw"),
            ("lofo_size_sector_ridge", "not_applicable"),
            "with_jw_vs_size_sector",
        ),
        (
            ("physics_knn", "without_jw"),
            ("lofo_prevalence", "not_applicable"),
            "without_jw_vs_prevalence",
        ),
        (
            ("physics_knn", "without_jw"),
            ("lofo_size_sector_ridge", "not_applicable"),
            "without_jw_vs_size_sector",
        ),
        (
            ("physics_knn", "with_jw"),
            ("physics_knn", "without_jw"),
            "with_jw_vs_without_jw",
        ),
    ]
    deltas: list[dict[str, Any]] = []
    for first, second, comparison in comparisons:
        for metric in METRICS:
            values = np.asarray(samples[first][metric])
            other = np.asarray(samples[second][metric])
            delta = np.asarray(
                [
                    _oriented_delta(metric, left, right)
                    for left, right in zip(values, other)
                ]
            )
            point_delta = _oriented_delta(
                metric,
                float(point[first][metric]),
                float(point[second][metric]),
            )
            left_tail = (np.count_nonzero(delta <= 0.0) + 1) / (len(delta) + 1)
            right_tail = (np.count_nonzero(delta >= 0.0) + 1) / (len(delta) + 1)
            deltas.append(
                {
                    "solver_family_id": variant["solver_family_id"],
                    "solver_short_name": variant["solver_short_name"],
                    "solver_uuid": variant["solver_uuid"],
                    "comparison": comparison,
                    "metric": metric,
                    "point_improvement": point_delta,
                    "lower_95": float(np.quantile(delta, 0.025)),
                    "upper_95": float(np.quantile(delta, 0.975)),
                    "two_sided_p": float(min(1.0, 2.0 * min(left_tail, right_tail))),
                    "accepted_family_draws": resamples,
                    "attempted_family_draws": attempted,
                    "orientation": "positive_favors_first_named_estimator",
                }
            )
    return performance, deltas, attempted


def build_growth_table(
    variants: Sequence[Mapping[str, Any]],
    observations: pd.DataFrame,
    coverage: pd.DataFrame,
    predictions: pd.DataFrame,
    selected_tasks: set[str],
    selection_weights: Mapping[str, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in variants:
        observed = observations.loc[
            observations["solver_uuid"] == variant["solver_uuid"]
        ]
        covered = coverage.loc[coverage["solver_uuid"] == variant["solver_uuid"]]
        counts = binary_counts(observed["observed_outcome"])
        observed_tasks = set(map(str, observed["task_uuid"]))
        complete = observed_tasks == selected_tasks
        weighted_success = None
        if complete:
            success_tasks = set(
                map(
                    str,
                    observed.loc[
                        observed["observed_outcome"] == "success", "task_uuid"
                    ],
                )
            )
            weighted_success = sum(
                selection_weights[task] for task in success_tasks
            ) / float(sum(selection_weights.values()))
        predicted = predictions.loc[
            (predictions["solver_uuid"] == variant["solver_uuid"])
            & (predictions["feature_arm"] == "with_jw")
        ]
        predicted_success = (
            int((predicted["predicted_outcome"] == "success").sum())
            if len(predicted)
            else None
        )
        rows.append(
            {
                "solver_family_id": variant["solver_family_id"],
                "solver_short_name": variant["solver_short_name"],
                "solver_uuid": variant["solver_uuid"],
                "solver_variant_id": variant["solver_variant_id"],
                "resource_ladder_id": variant["resource_ladder_id"],
                "resource_axis_name": variant["resource_axis_name"],
                "resource_value": variant["resource_value"],
                "resource_units": variant["resource_units"],
                "resource_rank": variant["resource_rank"],
                "potential_cells": len(covered),
                "labeled_cells": len(observed),
                "coverage_fraction": len(observed) / len(covered),
                "n_success": counts["success"],
                "n_fail": counts["fail"],
                "selected_sample_success_rate": (
                    counts["success"] / len(observed) if len(observed) else None
                ),
                "selection_weighted_population_success_rate": weighted_success,
                "population_rate_status": (
                    "estimated_complete_96_task_panel"
                    if complete
                    else "not_estimable_incomplete_or_censored_panel"
                ),
                "predicted_success_tasks_with_jw": predicted_success,
                "predicted_success_rate_with_jw": (
                    predicted_success / 718.0 if predicted_success is not None else None
                ),
            }
        )
    return rows


def build_nestedness_table(
    variants: Sequence[Mapping[str, Any]],
    observations: pd.DataFrame,
    predictions: pd.DataFrame,
    selected_tasks: set[str],
    selection_weights: Mapping[str, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ladder_ids = sorted(
        {
            str(row["resource_ladder_id"])
            for row in variants
            if row["resource_ladder_id"] is not None
        }
    )
    for ladder_id in ladder_ids:
        ladder = sorted(
            (row for row in variants if row["resource_ladder_id"] == ladder_id),
            key=lambda row: int(row["resource_rank"]),
        )
        for earlier, later in zip(ladder, ladder[1:]):
            left = observations.loc[
                observations["solver_uuid"] == earlier["solver_uuid"],
                ["task_uuid", "observed_outcome"],
            ].set_index("task_uuid")["observed_outcome"]
            right = observations.loc[
                observations["solver_uuid"] == later["solver_uuid"],
                ["task_uuid", "observed_outcome"],
            ].set_index("task_uuid")["observed_outcome"]
            joint = sorted(set(map(str, left.index)) & set(map(str, right.index)))
            categories = Counter((str(left[task]), str(right[task])) for task in joint)
            weighted_lost = None
            weighted_new = None
            if set(joint) == selected_tasks:
                denominator = float(sum(selection_weights.values()))
                weighted_lost = (
                    sum(
                        selection_weights[task]
                        for task in joint
                        if left[task] == "success" and right[task] == "fail"
                    )
                    / denominator
                )
                weighted_new = (
                    sum(
                        selection_weights[task]
                        for task in joint
                        if left[task] == "fail" and right[task] == "success"
                    )
                    / denominator
                )

            predicted_left = predictions.loc[
                (predictions["solver_uuid"] == earlier["solver_uuid"])
                & (predictions["feature_arm"] == "with_jw")
            ].set_index("task_uuid")
            predicted_right = predictions.loc[
                (predictions["solver_uuid"] == later["solver_uuid"])
                & (predictions["feature_arm"] == "with_jw")
            ].set_index("task_uuid")
            predicted_joint = sorted(
                set(map(str, predicted_left.index))
                & set(map(str, predicted_right.index))
            )
            predicted_lost = None
            predicted_new = None
            mean_probability_change = None
            if predicted_joint:
                predicted_lost = sum(
                    predicted_left.at[task, "predicted_outcome"] == "success"
                    and predicted_right.at[task, "predicted_outcome"] == "fail"
                    for task in predicted_joint
                )
                predicted_new = sum(
                    predicted_left.at[task, "predicted_outcome"] == "fail"
                    and predicted_right.at[task, "predicted_outcome"] == "success"
                    for task in predicted_joint
                )
                mean_probability_change = float(
                    np.mean(
                        [
                            float(predicted_right.at[task, "probability_success"])
                            - float(predicted_left.at[task, "probability_success"])
                            for task in predicted_joint
                        ]
                    )
                )
            lost = categories[("success", "fail")]
            rows.append(
                {
                    "solver_family_id": earlier["solver_family_id"],
                    "resource_ladder_id": ladder_id,
                    "earlier_solver_short_name": earlier["solver_short_name"],
                    "earlier_resource_value": earlier["resource_value"],
                    "later_solver_short_name": later["solver_short_name"],
                    "later_resource_value": later["resource_value"],
                    "joint_labeled_tasks": len(joint),
                    "both_fail": categories[("fail", "fail")],
                    "newly_solved": categories[("fail", "success")],
                    "lost_success": lost,
                    "both_success": categories[("success", "success")],
                    "nestedness_violation_rate": (lost / len(joint) if joint else None),
                    "selection_weighted_newly_solved_rate": weighted_new,
                    "selection_weighted_lost_success_rate": weighted_lost,
                    "predicted_joint_tasks_with_jw": len(predicted_joint),
                    "predicted_newly_solved_with_jw": predicted_new,
                    "predicted_lost_success_with_jw": predicted_lost,
                    "mean_predicted_probability_change_with_jw": mean_probability_change,
                }
            )
    _require(len(rows) == 12, f"resource-ladder pair census changed: {len(rows)}")
    return rows


OBSERVATION_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "solver_family_id",
    "solver_family_uuid",
    "solver_short_name",
    "solver_uuid",
    "solver_variant_id",
    "resource_ladder_id",
    "resource_axis_name",
    "resource_value",
    "resource_units",
    "resource_rank",
    "energy_hartree",
    "observed_outcome",
    "metric_outcome_annotation",
    "metric_status_annotation",
    "label_reason_annotation",
    "raw_status_annotation",
    "observation_source",
    "absolute_error_hartree",
    "graded_residual",
    "reference_energy_hartree",
    "threshold_hartree",
    "reference_grade",
]
COVERAGE_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "solver_variant_id",
    "resource_ladder_id",
    "resource_value",
    "coverage_status",
    "coverage_reason",
    "enters_binary_label_table",
]
ELIGIBILITY_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "solver_variant_id",
    "resource_ladder_id",
    "resource_value",
    "n_labels",
    "n_success",
    "n_fail",
    "n_canonical_families",
    "minimum_fold_training_tasks",
    "model_status",
    "failed_floor_checks",
]
PREDICTION_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "solver_family_id",
    "solver_family_uuid",
    "solver_short_name",
    "solver_uuid",
    "solver_variant_id",
    "resource_ladder_id",
    "resource_value",
    "feature_arm",
    "model",
    "protocol",
    "prediction_kind",
    "predicted_outcome",
    "predicted_probability",
    "probability_fail",
    "probability_success",
    "family_used_as_model_input",
    "n_training_labels",
    "n_training_families",
]
PERFORMANCE_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "estimator",
    "feature_arm",
    "metric",
    "point",
    "lower_95",
    "upper_95",
    "accepted_family_draws",
    "attempted_family_draws",
    "orientation",
]
DELTA_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "comparison",
    "metric",
    "point_improvement",
    "lower_95",
    "upper_95",
    "two_sided_p",
    "accepted_family_draws",
    "attempted_family_draws",
    "orientation",
]
GROWTH_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "solver_variant_id",
    "resource_ladder_id",
    "resource_axis_name",
    "resource_value",
    "resource_units",
    "resource_rank",
    "potential_cells",
    "labeled_cells",
    "coverage_fraction",
    "n_success",
    "n_fail",
    "selected_sample_success_rate",
    "selection_weighted_population_success_rate",
    "population_rate_status",
    "predicted_success_tasks_with_jw",
    "predicted_success_rate_with_jw",
]
NESTEDNESS_COLUMNS = [
    "solver_family_id",
    "resource_ladder_id",
    "earlier_solver_short_name",
    "earlier_resource_value",
    "later_solver_short_name",
    "later_resource_value",
    "joint_labeled_tasks",
    "both_fail",
    "newly_solved",
    "lost_success",
    "both_success",
    "nestedness_violation_rate",
    "selection_weighted_newly_solved_rate",
    "selection_weighted_lost_success_rate",
    "predicted_joint_tasks_with_jw",
    "predicted_newly_solved_with_jw",
    "predicted_lost_success_with_jw",
    "mean_predicted_probability_change_with_jw",
]


def _format_interval(point: Any, lower: Any, upper: Any) -> str:
    if point is None:
        return "NA"
    return f"{float(point):.3f} [{float(lower):.3f}, {float(upper):.3f}]"


def _write_markdown_report(
    report: Mapping[str, Any],
    eligibility: Sequence[Mapping[str, Any]],
    growth: Sequence[Mapping[str, Any]],
    performance: Sequence[Mapping[str, Any]],
    deltas: Sequence[Mapping[str, Any]],
    nestedness: Sequence[Mapping[str, Any]],
    path: Path,
) -> None:
    growth_by_uuid = {str(row["solver_uuid"]): row for row in growth}
    performance_lookup = {
        (
            str(row["solver_uuid"]),
            str(row["estimator"]),
            str(row["feature_arm"]),
            str(row["metric"]),
        ): row
        for row in performance
    }
    delta_lookup = {
        (
            str(row["solver_uuid"]),
            str(row["comparison"]),
            str(row["metric"]),
        ): row
        for row in deltas
    }
    lines = [
        "# G50 solver-family solvability analysis",
        "",
        "This is internal descriptive evidence, not a validated predictor or a public/dashboard release. Canonical Hamiltonian family is used only for held-family-out training exclusion, family-balanced scoring, uncertainty, and reporting; it is never a model input.",
        "",
        "## Observed family ladders",
        "",
        "| Variant | Labels | Success | Fail | Weighted population rate | ML status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in eligibility:
        growth_row = growth_by_uuid[str(row["solver_uuid"])]
        weighted = growth_row["selection_weighted_population_success_rate"]
        weighted_text = "NA" if weighted is None else f"{float(weighted):.3f}"
        lines.append(
            f"| {row['solver_short_name']} | {row['n_labels']} | "
            f"{row['n_success']} | {row['n_fail']} | {weighted_text} | "
            f"{row['model_status']} |"
        )
    lines += [
        "",
        "The weighted rate uses the mandatory ML-5 selection weights only for complete 96-task panels. TrimCI checkpoint variants remain incomplete right-censored panels and do not receive a population-rate estimate.",
        "",
        "## Eligible variant performance",
        "",
        "Family-balanced average precision is shown for the with-JW physics KNN and the strong size-sector ridge. The last column is physics minus size-sector under identical whole-family bootstrap draws.",
        "",
        "| Variant | Physics AP | Size-sector AP | AP improvement |",
        "|---|---:|---:|---:|",
    ]
    for row in eligibility:
        if row["model_status"] != "eligible":
            continue
        solver_uuid = str(row["solver_uuid"])
        physics = performance_lookup[
            (solver_uuid, "physics_knn", "with_jw", "average_precision_success")
        ]
        baseline = performance_lookup[
            (
                solver_uuid,
                "lofo_size_sector_ridge",
                "not_applicable",
                "average_precision_success",
            )
        ]
        delta = delta_lookup[
            (solver_uuid, "with_jw_vs_size_sector", "average_precision_success")
        ]
        lines.append(
            f"| {row['solver_short_name']} | "
            f"{_format_interval(physics['point'], physics['lower_95'], physics['upper_95'])} | "
            f"{_format_interval(baseline['point'], baseline['lower_95'], baseline['upper_95'])} | "
            f"{_format_interval(delta['point_improvement'], delta['lower_95'], delta['upper_95'])} |"
        )
    lines += [
        "",
        "## Ladder diagnostics",
        "",
        "| Ladder | Earlier to later | Joint labels | Newly solved | Lost success |",
        "|---|---|---:|---:|---:|",
    ]
    for row in nestedness:
        lines.append(
            f"| {row['resource_ladder_id']} | {row['earlier_resource_value']} to "
            f"{row['later_resource_value']} | {row['joint_labeled_tasks']} | "
            f"{row['newly_solved']} | {row['lost_success']} |"
        )
    lines += [
        "",
        "`lost_success` is reported rather than repaired: no monotonic postprocessing is applied to observed labels or predictions. For TrimCI, only pairs of actually observed recovered checkpoints enter these diagnostics.",
        "",
        "## Reproducibility and scope",
        "",
        f"The normalized table contains {report['panel']['normalized_labels']} binary labels over {report['panel']['potential_variant_task_cells']} potential cells. {report['panel']['eligible_variants']} of 18 variants pass the frozen model floor, producing {report['panel']['prediction_rows']} task-keyed predictions across the with/without-JW arms.",
        "",
        "The bundle preserves the outcome-blind preflight, the pre-fit size-sector amendment, normalized labels and coverage, model eligibility decisions, predictions, family-bootstrap performance and paired deltas, growth/nestedness tables, schemas, and file hashes. Promotion additionally requires two fresh directories to be recursively byte-identical.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_finalization(
    root: Path,
    preregistration_path: Path,
    amendment_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Execute one complete deterministic G50 solver-family ML run."""
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    preregistration = load_preregistration(preregistration_path)
    verify_inputs(root, preregistration)
    amendment, backfill = load_size_sector_amendment(
        root, amendment_path, preregistration_path
    )

    run_outcome_blind_preflight(
        root, preregistration_path, output_directory / "preflight"
    )
    features = pd.read_csv(
        resolve_input_path(root, preregistration["inputs"]["feature_table"]),
        low_memory=False,
    )
    metadata = pd.read_csv(
        resolve_input_path(root, preregistration["inputs"]["feature_metadata"])
    )
    taxonomy = json.loads(
        resolve_input_path(
            root, preregistration["inputs"]["canonical_families"]
        ).read_text(encoding="utf-8")
    )
    identifiers = json.loads(
        resolve_input_path(
            root, preregistration["inputs"]["identifier_screen"]
        ).read_text(encoding="utf-8")
    )["identifier_columns"]
    canonical = canonical_family_map(taxonomy)
    tasks = list(map(str, features["task_uuid"]))
    _require(len(tasks) == len(set(tasks)) == 718, "feature task census changed")
    families = np.asarray([canonical[task] for task in tasks], dtype=object)
    task_index = {task: index for index, task in enumerate(tasks)}
    policy = derive_feature_policy(metadata, identifiers)
    size_sector = build_size_sector_frame(features, backfill).reindex(tasks)

    geometry_cache: dict[tuple[str, ...], np.ndarray] = {}
    distances: dict[tuple[str, str], np.ndarray] = {}
    for solver_family, columns in sorted(policy["solver_family_columns"].items()):
        for arm, arm_columns in (
            ("with_jw", columns),
            ("without_jw", sorted(set(columns) - set(policy["jw"]))),
        ):
            key = tuple(arm_columns)
            if key not in geometry_cache:
                models = build_block_models(
                    features,
                    metadata,
                    arm_columns,
                    scaling=str(preregistration["feature_policy"]["scaling"]),
                    variance_threshold=float(
                        preregistration["feature_policy"]["pca_variance_threshold"]
                    ),
                    universal_only=False,
                )
                geometry_cache[key] = block_aware_distance(len(features), models)[0]
            distances[(solver_family, arm)] = geometry_cache[key]

    variants = g50_variant_rows(
        resolve_input_path(root, preregistration["inputs"]["solver_family_catalog"])
    )
    observations, coverage_rows = normalize_g50_outcomes(
        root, preregistration, variants, canonical
    )
    observation_frame = pd.DataFrame(observations)
    coverage_frame = pd.DataFrame(coverage_rows)
    eligibility = variant_eligibility(
        observation_frame,
        variants,
        preregistration["model_eligibility_floor"],
    )
    eligibility_by_uuid = {str(row["solver_uuid"]): row for row in eligibility}

    weight_frame = pd.read_csv(
        resolve_input_path(root, preregistration["inputs"]["selection_weights"])
    )
    selection_weights = {
        str(row.task_uuid): int(row.selection_weight)
        for row in weight_frame.itertuples(index=False)
    }
    _require(sum(selection_weights.values()) == 718, "selection weight sum changed")
    selected_tasks = set(selection_weights)

    prediction_rows: list[dict[str, Any]] = []
    performance_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    bootstrap_attempts: dict[str, int] = {}
    for variant in variants:
        status = eligibility_by_uuid[str(variant["solver_uuid"])]
        if status["model_status"] != "eligible":
            continue
        data = observation_frame.loc[
            observation_frame["solver_uuid"] == variant["solver_uuid"]
        ].sort_values("task_uuid", kind="stable")
        training_indices = np.asarray(
            [task_index[str(task)] for task in data["task_uuid"]], dtype=int
        )
        y = data["observed_outcome"].eq("success").to_numpy(dtype=int)
        label_families = families[training_indices]
        prevalence = lofo_prevalence_probabilities(training_indices, y, families)
        ridge = lofo_size_sector_probabilities(
            size_sector,
            training_indices,
            y,
            families,
            seed=int(preregistration["seeds"]["model"]),
        )
        full_probabilities: dict[str, np.ndarray] = {}
        for arm in ARMS:
            full_probabilities[arm] = lofo_knn_probabilities(
                distances[(str(variant["solver_family_id"]), arm)],
                training_indices,
                y,
                families,
                tasks,
                k=int(preregistration["model"]["k"]),
            )
        probability_sets = {
            ("physics_knn", "with_jw"): full_probabilities["with_jw"][training_indices],
            ("physics_knn", "without_jw"): full_probabilities["without_jw"][
                training_indices
            ],
            ("lofo_prevalence", "not_applicable"): prevalence[training_indices],
            ("lofo_size_sector_ridge", "not_applicable"): ridge[training_indices],
        }
        performance, deltas, attempted = bootstrap_variant(
            variant=variant,
            y=y,
            families=label_families,
            probability_sets=probability_sets,
            resamples=int(preregistration["bootstrap"]["accepted_two_class_draws"]),
            seed=int(preregistration["bootstrap"]["seed"]),
        )
        performance_rows.extend(performance)
        delta_rows.extend(deltas)
        bootstrap_attempts[str(variant["solver_short_name"])] = attempted
        for index, task_uuid in enumerate(tasks):
            for arm in ARMS:
                probability_success = float(full_probabilities[arm][index])
                predicted = "success" if probability_success > 0.5 else "fail"
                prediction_rows.append(
                    {
                        "task_uuid": task_uuid,
                        "canonical_family": canonical[task_uuid],
                        "solver_family_id": variant["solver_family_id"],
                        "solver_family_uuid": variant["solver_family_uuid"],
                        "solver_short_name": variant["solver_short_name"],
                        "solver_uuid": variant["solver_uuid"],
                        "solver_variant_id": variant["solver_variant_id"],
                        "resource_ladder_id": variant["resource_ladder_id"],
                        "resource_value": variant["resource_value"],
                        "feature_arm": arm,
                        "model": MODEL_ID,
                        "protocol": PROTOCOL_ID,
                        "prediction_kind": "leave_one_canonical_family_out",
                        "predicted_outcome": predicted,
                        "predicted_probability": (
                            probability_success
                            if predicted == "success"
                            else 1.0 - probability_success
                        ),
                        "probability_fail": 1.0 - probability_success,
                        "probability_success": probability_success,
                        "family_used_as_model_input": False,
                        "n_training_labels": len(y),
                        "n_training_families": len(set(map(str, label_families))),
                    }
                )

    prediction_rows.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["task_uuid"],
            row["feature_arm"],
        )
    )
    performance_rows.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["estimator"],
            row["feature_arm"],
            row["metric"],
        )
    )
    delta_rows.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["comparison"],
            row["metric"],
        )
    )
    prediction_frame = pd.DataFrame(prediction_rows)
    growth = build_growth_table(
        variants,
        observation_frame,
        coverage_frame,
        prediction_frame,
        selected_tasks,
        selection_weights,
    )
    nestedness = build_nestedness_table(
        variants,
        observation_frame,
        prediction_frame,
        selected_tasks,
        selection_weights,
    )

    eligible_count = sum(row["model_status"] == "eligible" for row in eligibility)
    _require(
        len(prediction_rows) == eligible_count * 718 * 2,
        "prediction row count changed",
    )
    prediction_schema_path = (
        root / "analysis/ml_g50_solver_families/predictions.schema.json"
    )
    artifact_schemas_path = (
        root / "analysis/ml_g50_solver_families/artifact_schemas.json"
    )
    prediction_schema = json.loads(prediction_schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(prediction_schema).validate(prediction_rows)

    positive_size_ap = sum(
        row["comparison"] == "with_jw_vs_size_sector"
        and row["metric"] == "average_precision_success"
        and float(row["lower_95"]) > 0.0
        for row in delta_rows
    )
    positive_jw_ap = sum(
        row["comparison"] == "with_jw_vs_without_jw"
        and row["metric"] == "average_precision_success"
        and float(row["lower_95"]) > 0.0
        for row in delta_rows
    )
    report = {
        "artifact_id": "ml_g50_solver_family_solvability_v1",
        "status": "complete_internal_descriptive_no_gate",
        "protocol": PROTOCOL_ID,
        "public_or_dashboard_bundle": False,
        "validated_predictor_claim": False,
        "family_used_as_model_input": False,
        "panel": {
            "corpus_tasks": 718,
            "selected_tasks": 96,
            "canonical_families": 40,
            "solver_families": 4,
            "analysis_variants": 18,
            "eligible_variants": eligible_count,
            "normalized_labels": len(observations),
            "potential_variant_task_cells": len(coverage_rows),
            "prediction_rows": len(prediction_rows),
        },
        "label_policy": preregistration["label_policy"],
        "eligibility": eligibility,
        "bootstrap_attempts_by_variant": bootstrap_attempts,
        "signals": {
            "with_jw_ap_lower_bound_above_size_sector_count": positive_size_ap,
            "with_jw_ap_lower_bound_above_without_jw_count": positive_jw_ap,
            "eligible_variant_denominator": eligible_count,
            "interpretation": "descriptive_only_no_multiplicity_claim",
        },
        "coverage_status_counts": dict(
            sorted(Counter(coverage_frame["coverage_status"]).items())
        ),
        "observed_ladder_lost_success_total": int(
            sum(row["lost_success"] for row in nestedness)
        ),
        "size_sector_amendment_sha256": sha256_file(amendment_path),
        "size_sector_backfill_sha256": amendment["backfill"]["sha256"],
        "degenerate_mcc_convention": "zero_denominator_is_zero",
        "no_gate_statement": (
            "Internal descriptive analysis only; no model-performance cutoff, "
            "dashboard overwrite, public release, or validated-predictor claim."
        ),
    }

    stable_csv_dump(
        observations,
        OBSERVATION_COLUMNS,
        output_directory / "normalized_observations.csv",
    )
    stable_csv_dump(coverage_rows, COVERAGE_COLUMNS, output_directory / "coverage.csv")
    stable_csv_dump(
        eligibility, ELIGIBILITY_COLUMNS, output_directory / "variant_eligibility.csv"
    )
    stable_csv_dump(
        prediction_rows, PREDICTION_COLUMNS, output_directory / "predictions.csv"
    )
    stable_csv_dump(
        performance_rows,
        PERFORMANCE_COLUMNS,
        output_directory / "family_balanced_performance.csv",
    )
    stable_csv_dump(delta_rows, DELTA_COLUMNS, output_directory / "paired_deltas.csv")
    stable_csv_dump(growth, GROWTH_COLUMNS, output_directory / "ladder_growth.csv")
    stable_csv_dump(nestedness, NESTEDNESS_COLUMNS, output_directory / "nestedness.csv")
    stable_json_dump(report, output_directory / "report.json")
    _write_markdown_report(
        report,
        eligibility,
        growth,
        performance_rows,
        delta_rows,
        nestedness,
        output_directory / "REPORT.md",
    )
    schema_directory = output_directory / "schemas"
    schema_directory.mkdir()
    shutil.copyfile(
        prediction_schema_path, schema_directory / prediction_schema_path.name
    )
    shutil.copyfile(
        artifact_schemas_path, schema_directory / artifact_schemas_path.name
    )

    files = sorted(path for path in output_directory.rglob("*") if path.is_file())
    manifest = {
        "artifact_id": "ml_g50_solver_family_solvability_manifest_v1",
        "status": "complete_internal_descriptive_no_gate",
        "protocol": PROTOCOL_ID,
        "preregistration_sha256": sha256_file(preregistration_path),
        "amendment_sha256": sha256_file(amendment_path),
        "prediction_schema_sha256": sha256_file(prediction_schema_path),
        "files": [
            {
                "path": path.relative_to(output_directory).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in files
        ],
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return report


def verify_and_promote_two_runs(
    first: Path,
    second: Path,
    promoted: Path,
    identity_path: Path,
) -> dict[str, Any]:
    """Require recursive byte identity and promote exactly one fresh run."""

    def inventory(root: Path) -> dict[str, str]:
        return {
            path.relative_to(root).as_posix(): sha256_file(path)
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    _require(first.is_dir() and second.is_dir(), "both run directories must exist")
    _require(not promoted.exists(), f"promotion destination exists: {promoted}")
    _require(not identity_path.exists(), f"identity report exists: {identity_path}")
    left = inventory(first)
    right = inventory(second)
    _require(left == right, "two G50 ML runs are not byte-identical")
    shutil.copytree(first, promoted)
    report = {
        "artifact_id": "ml_g50_solver_family_two_run_identity_v1",
        "status": "pass",
        "byte_identical": True,
        "file_count": len(left),
        "relative_paths": sorted(left),
        "file_hashes": left,
        "promoted_bundle_manifest_sha256": sha256_file(
            promoted / "artifact_manifest.json"
        ),
    }
    stable_json_dump(report, identity_path)
    return report
