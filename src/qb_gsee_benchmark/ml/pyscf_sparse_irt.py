"""Frozen ML-10C sparse 23-item Bayesian inverted-IRT analysis."""

from __future__ import annotations

import json
import math
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import pearsonr, spearmanr

from qb_gsee_benchmark.ml.bayesian_irt_recovery import canonical_family_folds
from qb_gsee_benchmark.ml.bayesian_irt_run import (
    DIFFICULTY_LIMIT_OFFSET,
    _deterministic_npz,
    _diagnostics,
    _posterior_array,
    _sample_model,
    _shortest_hdi,
)
from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.pyscf_hardness_labels import (
    DISPLAY_BY_ITEM,
    METHOD_ORDER,
    prepare_pyscf_data,
)


CPU_MARKER = "g50_bond_dimension_2048"
SECOND_MARKER = "pyscf_ccsd_t"
SOLVER_GROUPS = ("dmrg", "ipie_afqmc", "shci", "trimci", "pyscf_methods")
MODEL_NAMES = ("binary_rasch", "continuous_beta", "one_factor", "two_factor")


@dataclass(frozen=True)
class SparseIrtData:
    task_ids: tuple[str, ...]
    task_families: tuple[str, ...]
    canonical_families: tuple[str, ...]
    item_ids: tuple[str, ...]
    item_names: tuple[str, ...]
    solver_groups: tuple[str, ...]
    task_family_index: np.ndarray
    item_solver_group_index: np.ndarray
    observation_task_index: np.ndarray
    observation_item_index: np.ndarray
    binary: np.ndarray
    clipped_residual: np.ndarray
    quality: np.ndarray
    logit_quality: np.ndarray
    response_rows: pd.DataFrame


@dataclass(frozen=True)
class SparseTransform:
    mean: np.ndarray
    scale: np.ndarray
    standardized: np.ndarray


@dataclass(frozen=True)
class SparseFit:
    traces: dict[str, Any]
    diagnostics: dict[str, dict[str, Any]]
    transform: SparseTransform
    folds: np.ndarray
    cross_validation_diagnostics: list[dict[str, Any]]
    cross_validation_log_predictive_density: dict[str, np.ndarray]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(samples: np.ndarray, index: int | tuple[int, ...]) -> dict[str, float]:
    suffix = (index,) if isinstance(index, int) else index
    values = np.asarray(samples[(..., *suffix)], dtype=float).reshape(-1)
    low, high = _shortest_hdi(values)
    return {
        "mean": float(np.mean(values)),
        "sd": float(np.std(values, ddof=1)),
        "hdi_2_5pct": low,
        "hdi_97_5pct": high,
    }


def prepare_sparse_irt_data(root: Path, preregistration_path: Path) -> SparseIrtData:
    """Build the frozen 18-complete plus five-sparse response matrix."""

    prepared = prepare_pyscf_data(root, preregistration_path)
    preregistration = prepared.preregistration
    specification = preregistration["ml10c_bayesian_irt"]
    _require(specification["items"] == 23 and specification["tasks"] == 96, "ML-10C dimensions changed")
    _require(specification["primary_model"]["free_item_discrimination"] is False, "free discrimination enabled")
    _require(tuple(specification["primary_model"]["solver_groups"]) == SOLVER_GROUPS, "solver-group order changed")

    panel = prepared.panel[["task_uuid", "canonical_family"]].copy()
    panel = panel.astype(str).sort_values("task_uuid", kind="mergesort").reset_index(drop=True)
    _require(len(panel) == 96 and panel["task_uuid"].is_unique, "panel changed")
    task_ids = tuple(panel["task_uuid"])
    task_family_by_id = dict(zip(panel["task_uuid"], panel["canonical_family"]))

    observations_path = root / preregistration["inputs"]["post_g59_observations"]["path"]
    ladder = pd.read_csv(observations_path, dtype={"task_uuid": str})
    ladder = ladder.loc[ladder["task_uuid"].isin(task_ids)].copy()
    _require(len(ladder) == 96 * 18, "ladder response grid changed")
    _require(not ladder.duplicated(["task_uuid", "solver_variant_id"]).any(), "duplicate ladder response")
    ladder_items = (
        ladder[["solver_family_id", "solver_variant_id", "solver_short_name"]]
        .drop_duplicates()
        .astype(str)
        .sort_values(["solver_family_id", "solver_variant_id"], kind="mergesort")
        .reset_index(drop=True)
    )
    _require(len(ladder_items) == 18, "ladder item count changed")
    pyscf_items = pd.DataFrame(
        [
            {
                "solver_family_id": "pyscf_methods",
                "solver_variant_id": item,
                "solver_short_name": DISPLAY_BY_ITEM[item],
            }
            for item in METHOD_ORDER
        ]
    )
    items = pd.concat([ladder_items, pyscf_items], ignore_index=True)
    item_ids = tuple(items["solver_variant_id"].astype(str))
    _require(len(item_ids) == 23 and len(set(item_ids)) == 23, "item census changed")

    ladder_rows = ladder[
        ["task_uuid", "canonical_family", "solver_family_id", "solver_variant_id", "solver_short_name", "observed_outcome", "graded_residual"]
    ].copy()
    ladder_rows["response_observed"] = True
    ladder_rows["binary_response"] = ladder_rows["observed_outcome"].astype(str).eq("success")
    ladder_rows["missing_reason"] = "observed_ladder_response"

    pyscf = prepared.labels.loc[prepared.labels["in_panel"]].copy()
    _require(len(pyscf) == 96 * 5, "PySCF panel grid changed")
    pyscf_rows = pd.DataFrame(
        {
            "task_uuid": pyscf["task_uuid"].astype(str),
            "canonical_family": pyscf["canonical_family"].astype(str),
            "solver_family_id": "pyscf_methods",
            "solver_variant_id": pyscf["item_id"].astype(str),
            "solver_short_name": pyscf["item_id"].map(DISPLAY_BY_ITEM),
            "observed_outcome": np.where(pyscf["solvable"].eq(True), "success", np.where(pyscf["response_observed"], "fail", "missing")),
            "graded_residual": pyscf["graded_residual"],
            "response_observed": pyscf["response_observed"].astype(bool),
            "binary_response": pyscf["solvable"],
            "missing_reason": pyscf["label_reason"].astype(str),
        }
    )
    response_rows = pd.concat([ladder_rows, pyscf_rows], ignore_index=True)
    task_order = {value: index for index, value in enumerate(task_ids)}
    item_order = {value: index for index, value in enumerate(item_ids)}
    response_rows["task_index"] = response_rows["task_uuid"].map(task_order)
    response_rows["item_index"] = response_rows["solver_variant_id"].map(item_order)
    _require(bool(response_rows[["task_index", "item_index"]].notna().all().all()), "unbound response")
    response_rows = response_rows.sort_values(["task_index", "item_index"], kind="mergesort").reset_index(drop=True)
    _require(len(response_rows) == 96 * 23, "sparse response grid changed")
    _require(not response_rows.duplicated(["task_uuid", "solver_variant_id"]).any(), "duplicate sparse response")
    _require(int(response_rows["response_observed"].sum()) == 96 * 18 + 357, "observed-cell count changed")
    observed = response_rows.loc[response_rows["response_observed"]].copy()
    residual = pd.to_numeric(observed["graded_residual"], errors="coerce").to_numpy(float)
    residual = np.where(np.isfinite(residual), np.clip(residual, 0.0, 4.0), 4.0)
    quality = 1.0 / (1.0 + residual + 1.0e-6)
    _require(bool(np.all((quality > 0.0) & (quality < 1.0))), "quality left open interval")

    canonical_families = tuple(sorted(set(panel["canonical_family"])))
    family_order = {value: index for index, value in enumerate(canonical_families)}
    group_order = {value: index for index, value in enumerate(SOLVER_GROUPS)}
    response_rows["continuous_quality"] = np.nan
    response_rows.loc[response_rows["response_observed"], "continuous_quality"] = quality
    return SparseIrtData(
        task_ids=task_ids,
        task_families=tuple(task_family_by_id[value] for value in task_ids),
        canonical_families=canonical_families,
        item_ids=item_ids,
        item_names=tuple(items["solver_short_name"].astype(str)),
        solver_groups=SOLVER_GROUPS,
        task_family_index=np.asarray([family_order[task_family_by_id[value]] for value in task_ids], dtype=int),
        item_solver_group_index=np.asarray([group_order[value] for value in items["solver_family_id"]], dtype=int),
        observation_task_index=observed["task_index"].to_numpy(int),
        observation_item_index=observed["item_index"].to_numpy(int),
        binary=observed["binary_response"].astype(bool).to_numpy(np.int8),
        clipped_residual=residual,
        quality=quality,
        logit_quality=np.log(quality) - np.log1p(-quality),
        response_rows=response_rows,
    )


def sparse_response_model(data: SparseIrtData, continuous: bool):
    """Construct the fixed-discrimination sparse Rasch or beta model."""

    import pymc as pm
    import pytensor.tensor as pt

    coords = {
        "task": data.task_ids,
        "item": data.item_ids,
        "solver_group": data.solver_groups,
        "canonical_family": data.canonical_families,
        "observation": np.arange(len(data.binary)),
    }
    task = data.observation_task_index
    item = data.observation_item_index
    group = data.item_solver_group_index[item]
    with pm.Model(coords=coords) as model:
        group_ability_mean = pm.Normal("solver_group_ability_mean", 0.0, 0.75, dims="solver_group")
        group_item_sd = pm.HalfNormal("solver_group_item_sd", 0.5, dims="solver_group")
        item_offset = pm.Normal("item_ability_offset_raw", 0.0, 1.0, dims="item")
        item_ability = pm.Deterministic(
            "item_ability",
            group_ability_mean[data.item_solver_group_index] + item_offset * group_item_sd[data.item_solver_group_index],
            dims="item",
        )
        family_mean = pm.Normal("canonical_family_difficulty_mean", 0.0, 0.5, dims="canonical_family")
        task_sd = pm.HalfNormal("task_sd", 1.0)
        task_offset = pm.Normal("task_difficulty_offset_raw", 0.0, 1.0, dims="task")
        uncentered = family_mean[data.task_family_index] + task_offset * task_sd
        task_difficulty = pm.Deterministic("task_difficulty", uncentered - pt.mean(uncentered), dims="task")
        testlet_sd = pm.HalfNormal("testlet_sd", 0.5, dims="solver_group")
        testlet_raw = pm.Normal("testlet_raw", 0.0, 1.0, dims=("task", "solver_group"))
        scaled = testlet_raw * testlet_sd[None, :]
        testlet = pm.Deterministic("testlet_effect", scaled - pt.mean(scaled, axis=1, keepdims=True), dims=("task", "solver_group"))
        linear = item_ability[item] - task_difficulty[task] + testlet[task, group]
        if continuous:
            log_precision_mean = pm.Normal("solver_group_log_precision_mean", math.log(20.0), 0.5, dims="solver_group")
            log_precision_sd = pm.HalfNormal("solver_group_log_precision_sd", 0.35, dims="solver_group")
            precision_offset = pm.Normal("item_log_precision_offset_raw", 0.0, 1.0, dims="item")
            precision = pm.Deterministic(
                "item_precision",
                pt.exp(log_precision_mean[data.item_solver_group_index] + precision_offset * log_precision_sd[data.item_solver_group_index]),
                dims="item",
            )
            pm.Deterministic("item_consistency", precision / (precision + 1.0), dims="item")
            mean = pm.math.sigmoid(linear)
            pm.Beta("response", alpha=mean * precision[item], beta=(1.0 - mean) * precision[item], observed=data.quality, dims="observation")
        else:
            pm.Deterministic("difficulty_limit_10pct", item_ability + DIFFICULTY_LIMIT_OFFSET, dims="item")
            pm.Bernoulli("response", logit_p=linear, observed=data.binary, dims="observation")
    return model


def sparse_factor_transform(data: SparseIrtData, training_tasks: np.ndarray) -> SparseTransform:
    """Standardize each item using observed training-fold cells only."""

    training = set(map(int, np.asarray(training_tasks).tolist()))
    mean = np.empty(len(data.item_ids), dtype=float)
    scale = np.empty(len(data.item_ids), dtype=float)
    standardized = np.full((len(data.task_ids), len(data.item_ids)), np.nan, dtype=float)
    for item in range(len(data.item_ids)):
        mask = (data.observation_item_index == item) & np.asarray([int(value) in training for value in data.observation_task_index])
        values = data.logit_quality[mask]
        _require(len(values) >= 2, f"insufficient training observations for {data.item_ids[item]}")
        mean[item] = float(np.mean(values))
        candidate = float(np.std(values, ddof=1))
        scale[item] = candidate if np.isfinite(candidate) and candidate > 0.0 else 1.0
    standardized[data.observation_task_index, data.observation_item_index] = (
        data.logit_quality - mean[data.observation_item_index]
    ) / scale[data.observation_item_index]
    _require(bool(np.isfinite(standardized[data.observation_task_index, data.observation_item_index]).all()), "non-finite sparse transform")
    return SparseTransform(mean=mean, scale=scale, standardized=standardized)


def sparse_factor_model(
    standardized: np.ndarray,
    item_ids: tuple[str, ...],
    task_ids: tuple[str, ...],
    training_tasks: np.ndarray,
    factors: int,
):
    """Construct the missing-aware nonnegative marker-identified factor model."""

    import pymc as pm
    import pytensor.tensor as pt

    _require(factors in {1, 2}, "factor count must be one or two")
    cpu = item_ids.index(CPU_MARKER)
    second = item_ids.index(SECOND_MARKER)
    coords: dict[str, Any] = {"item": item_ids}
    if factors == 2:
        coords["factor"] = ("ladder_axis", "single_reference_multireference_axis")
    with pm.Model(coords=coords) as model:
        intercept = pm.Normal("item_intercept", 0.0, 0.25, dims="item")
        residual = pm.HalfNormal("item_residual_sd", 0.75, dims="item")
        if factors == 1:
            loading = pm.HalfNormal("nonnegative_loadings", 0.75, dims="item")
            factor_loading = pm.Deterministic("factor_loading", loading, dims="item")
            covariance = pt.outer(factor_loading, factor_loading) + pt.diag(residual**2)
        else:
            first_marker = pm.HalfNormal("first_marker_loading", 0.75)
            second_marker = pm.HalfNormal("second_marker_loading", 0.75)
            free = np.asarray([index for index in range(len(item_ids)) if index not in {cpu, second}], dtype=int)
            free_loadings = pm.HalfNormal("nonnegative_loadings", 0.75, shape=(len(free), 2))
            loading = pt.zeros((len(item_ids), 2))
            loading = pt.set_subtensor(loading[cpu, 0], first_marker)
            loading = pt.set_subtensor(loading[cpu, 1], 0.0)
            loading = pt.set_subtensor(loading[second, 0], 0.0)
            loading = pt.set_subtensor(loading[second, 1], second_marker)
            loading = pt.set_subtensor(loading[free, :], free_loadings)
            factor_loading = pm.Deterministic("factor_loading", loading, dims=("item", "factor"))
            covariance = factor_loading @ factor_loading.T + pt.diag(residual**2)

        pattern_tasks: dict[tuple[int, ...], list[int]] = {}
        for task in map(int, np.asarray(training_tasks)):
            observed_items = tuple(np.flatnonzero(np.isfinite(standardized[task])).tolist())
            _require(bool(observed_items), f"task {task_ids[task]} has no observed items")
            pattern_tasks.setdefault(observed_items, []).append(task)
        for pattern_number, (observed_items, tasks) in enumerate(sorted(pattern_tasks.items())):
            indices = np.asarray(observed_items, dtype=int)
            values = standardized[np.asarray(tasks, dtype=int)][:, indices]
            pattern_loading = factor_loading[indices]
            pattern_covariance = (
                pt.outer(pattern_loading, pattern_loading)
                if factors == 1
                else pattern_loading @ pattern_loading.T
            ) + pt.diag(residual[indices] ** 2)
            pm.MvNormal(
                f"response_pattern_{pattern_number}",
                mu=intercept[indices],
                cov=pattern_covariance,
                observed=values,
                shape=values.shape,
            )
    return model
