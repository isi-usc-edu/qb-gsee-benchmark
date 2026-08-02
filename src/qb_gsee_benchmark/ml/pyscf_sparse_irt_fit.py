"""Fitting and artifact construction for the frozen ML-10C sparse analysis."""

from __future__ import annotations

import math
import os
import platform
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import pearsonr, spearmanr

from qb_gsee_benchmark.ml.bayesian_irt_recovery import canonical_family_folds
from qb_gsee_benchmark.ml.bayesian_irt_run import (
    _deterministic_npz,
    _diagnostics,
    _posterior_array,
    _sample_model,
    _shortest_hdi,
)
from qb_gsee_benchmark.ml.core_set import _require, sha256_file, stable_csv_dump, stable_json_dump
from qb_gsee_benchmark.ml.pyscf_sparse_irt import (
    MODEL_NAMES,
    SECOND_MARKER,
    SparseFit,
    SparseIrtData,
    SparseTransform,
    prepare_sparse_irt_data,
    sparse_factor_model,
    sparse_factor_transform,
    sparse_response_model,
)


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


def _factor_diagnostics(trace: Any) -> dict[str, Any]:
    return _diagnostics(trace, ["factor_loading", "item_intercept", "item_residual_sd"])


def heldout_log_predictive_density(
    trace: Any, transform: SparseTransform, data: SparseIrtData, heldout_tasks: np.ndarray
) -> np.ndarray:
    """Marginalize held-out task scores over each task's observed item subset."""

    intercept = _posterior_array(trace, "item_intercept").reshape(-1, len(data.item_ids))
    residual = _posterior_array(trace, "item_residual_sd").reshape(-1, len(data.item_ids))
    loading = _posterior_array(trace, "factor_loading")
    if loading.ndim == 3:
        loading = loading.reshape(-1, len(data.item_ids), 1)
    else:
        loading = loading.reshape(-1, len(data.item_ids), loading.shape[-1])
    _require(len(intercept) == len(residual) == len(loading), "factor draw counts differ")
    result = np.empty(len(heldout_tasks), dtype=float)
    for output_index, task in enumerate(map(int, heldout_tasks)):
        items = np.flatnonzero(np.isfinite(transform.standardized[task]))
        values = transform.standardized[task, items]
        draw_log_density = np.empty(len(intercept), dtype=float)
        for start in range(0, len(intercept), 256):
            stop = min(start + 256, len(intercept))
            load = loading[start:stop][:, items, :]
            covariance = load @ np.swapaxes(load, -1, -2)
            diagonal = np.arange(len(items))
            covariance[:, diagonal, diagonal] += residual[start:stop][:, items] ** 2
            sign, log_determinant = np.linalg.slogdet(covariance)
            _require(bool(np.all(sign > 0)), "non-positive predictive covariance")
            difference = values[None, :] - intercept[start:stop][:, items]
            solved = np.linalg.solve(covariance, difference[..., None])[..., 0]
            quadratic = np.einsum("bi,bi->b", difference, solved)
            draw_log_density[start:stop] = -0.5 * (
                len(items) * math.log(2.0 * math.pi) + log_determinant + quadratic
            )
        result[output_index] = float(logsumexp(draw_log_density) - math.log(len(draw_log_density)))
    _require(bool(np.isfinite(result).all()), "non-finite predictive density")
    return result


def fit_sparse_models(
    data: SparseIrtData,
    preregistration: dict[str, Any],
    *,
    tune: int | None = None,
    draws: int | None = None,
) -> SparseFit:
    """Fit the two response models and exact blocked factor comparison."""

    sampling = preregistration["ml10c_bayesian_irt"]["sampling"]
    actual_tune = int(sampling["tune"] if tune is None else tune)
    actual_draws = int(sampling["draws"] if draws is None else draws)
    target_accept = float(sampling["target_accept"])
    seeds = list(map(int, sampling["fixed_chain_seeds"]))
    traces: dict[str, Any] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    for name, continuous in (("binary_rasch", False), ("continuous_beta", True)):
        print(f"ML10C_FIT_START model={name}", flush=True)
        traces[name] = _sample_model(
            sparse_response_model(data, continuous),
            tune=actual_tune,
            draws=actual_draws,
            target_accept=target_accept,
            seeds=seeds,
            retain_log_likelihood=False,
        )
        variables = ["task_difficulty", "item_ability"]
        variables += ["item_precision", "item_consistency"] if continuous else ["difficulty_limit_10pct"]
        diagnostics[name] = _diagnostics(traces[name], variables)
        print(f"ML10C_FIT_DONE model={name} pass={diagnostics[name]['passed']}", flush=True)

    all_tasks = np.arange(len(data.task_ids), dtype=int)
    transform = sparse_factor_transform(data, all_tasks)
    for factors, name in ((1, "one_factor"), (2, "two_factor")):
        print(f"ML10C_FIT_START model={name}", flush=True)
        traces[name] = _sample_model(
            sparse_factor_model(transform.standardized, data.item_ids, data.task_ids, all_tasks, factors),
            tune=actual_tune,
            draws=actual_draws,
            target_accept=target_accept,
            seeds=seeds,
            retain_log_likelihood=False,
        )
        diagnostics[name] = _factor_diagnostics(traces[name])
        print(f"ML10C_FIT_DONE model={name} pass={diagnostics[name]['passed']}", flush=True)

    folds = canonical_family_folds(data, 5, int(preregistration["ml10c_bayesian_irt"]["exact_cross_validation"]["fold_seed"]))
    cv_values = {name: np.empty(len(data.task_ids), dtype=float) for name in ("one_factor", "two_factor")}
    cv_diagnostics: list[dict[str, Any]] = []
    for fold in range(5):
        training = np.flatnonzero(folds != fold)
        heldout = np.flatnonzero(folds == fold)
        fold_transform = sparse_factor_transform(data, training)
        for factors, name in ((1, "one_factor"), (2, "two_factor")):
            print(f"ML10C_CV_START fold={fold + 1} model={name}", flush=True)
            trace = _sample_model(
                sparse_factor_model(fold_transform.standardized, data.item_ids, data.task_ids, training, factors),
                tune=actual_tune,
                draws=actual_draws,
                target_accept=target_accept,
                seeds=seeds,
                retain_log_likelihood=False,
            )
            health = _factor_diagnostics(trace)
            cv_values[name][heldout] = heldout_log_predictive_density(trace, fold_transform, data, heldout)
            cv_diagnostics.append({
                "fold": fold + 1,
                "model": name,
                "training_tasks": len(training),
                "heldout_tasks": len(heldout),
                **health,
                "output_kind": "posterior_diagnostic",
            })
            print(f"ML10C_CV_DONE fold={fold + 1} model={name} pass={health['passed']}", flush=True)
    return SparseFit(
        traces=traces,
        diagnostics=diagnostics,
        transform=transform,
        folds=folds,
        cross_validation_diagnostics=cv_diagnostics,
        cross_validation_log_predictive_density=cv_values,
    )


def _comparison(fit: SparseFit) -> dict[str, Any]:
    difference = fit.cross_validation_log_predictive_density["two_factor"] - fit.cross_validation_log_predictive_density["one_factor"]
    delta = float(np.sum(difference))
    standard_error = float(np.sqrt(len(difference) * np.var(difference, ddof=1)))
    decision = "favor_two_factors" if delta > standard_error else "favor_one_factor" if -delta > standard_error else "equivocal"
    return {
        "delta_elpd_two_minus_one": delta,
        "delta_standard_error": standard_error,
        "decision": decision,
        "method": "exact_five_fold_canonical_family_blocked",
        "reliable": bool(all(row["passed"] for row in fit.cross_validation_diagnostics)),
    }


def _response_records(data: SparseIrtData) -> list[dict[str, Any]]:
    columns = [
        "task_uuid", "canonical_family", "solver_family_id", "solver_variant_id",
        "solver_short_name", "response_observed", "observed_outcome", "binary_response",
        "graded_residual", "continuous_quality", "missing_reason",
    ]
    frame = data.response_rows[columns].copy()
    frame.loc[~frame["response_observed"], ["binary_response", "graded_residual", "continuous_quality"]] = None
    frame["output_kind"] = np.where(frame["response_observed"], "observed_response", "excluded_missing_cell")
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def _difficulty_shift(
    root: Path, preregistration: dict[str, Any], new_difficulty: np.ndarray, data: SparseIrtData
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    specification = preregistration["inputs"]["ml9c_primary_posterior_samples"]
    path = root / specification["path"]
    _require(sha256_file(path) == specification["sha256"], "ML-9C posterior source changed")
    with np.load(path) as retained:
        old = np.asarray(retained["binary_task_difficulty"], dtype=float)
    old_flat = old.reshape(-1, len(data.task_ids))
    new_flat = np.asarray(new_difficulty, dtype=float).reshape(-1, len(data.task_ids))
    old_flat -= old_flat.mean(axis=1, keepdims=True)
    new_flat -= new_flat.mean(axis=1, keepdims=True)
    paired_old = old_flat[np.arange(len(new_flat)) % len(old_flat)]
    shift = new_flat - paired_old
    rows = []
    for index, task_id in enumerate(data.task_ids):
        low, high = _shortest_hdi(shift[:, index])
        rows.append({
            "task_uuid": task_id,
            "canonical_family": data.task_families[index],
            "ml9c_posterior_mean": float(np.mean(old_flat[:, index])),
            "ml10c_posterior_mean": float(np.mean(new_flat[:, index])),
            "posterior_mean_shift": float(np.mean(shift[:, index])),
            "shift_hdi_2_5pct": low,
            "shift_hdi_97_5pct": high,
            "alignment": "drawwise_mean_zero",
            "output_kind": "posterior_estimate",
        })
    old_mean = np.mean(old_flat, axis=0)
    new_mean = np.mean(new_flat, axis=0)
    metrics = {
        "pearson_posterior_mean_concordance": float(pearsonr(old_mean, new_mean).statistic),
        "spearman_posterior_mean_concordance": float(spearmanr(old_mean, new_mean).statistic),
        "median_absolute_posterior_mean_shift": float(np.median(np.abs(new_mean - old_mean))),
    }
    return rows, metrics
