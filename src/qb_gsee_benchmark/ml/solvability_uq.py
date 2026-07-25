"""ML-8D UQ solvability estimator and solvability-ratio v2.

Two tracks over gradeable tasks only:

1. **Design-based** -- the selection-weighted population success rate over the
   retained gradeable centers. This is the ratio OF RECORD; no model output
   displaces it. ML-8D adds family-grouped bootstrap uncertainty.
2. **Model-based** -- Gaussian-process classification with the Laplace
   approximation over the frozen block-aware distance, giving per-point
   posterior uncertainty, leave-one-family-out CALIBRATION assessment as the
   validation gate, and a corpus ratio with credible intervals.

The frozen design lives in ``analysis/ml_solvability_uq/PREREGISTRATION.md``.
Every model output is an estimate; the ML-6 no-validated-predictor rule stands.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator
from scipy.linalg import cho_solve, cholesky
from scipy.special import expit
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from qb_gsee_benchmark.ml.core_set import (
    _require,
    block_aware_distance,
    build_block_models,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.g50_solver_families import (
    canonical_family_map,
    derive_feature_policy,
    g50_variant_rows,
    load_preregistration as load_parent_preregistration,
    resolve_input_path,
    verify_inputs,
)

PREREGISTRATION_ID = "ml8d_solvability_uq_preregistration_v1"
ARTIFACT_ID = "ml8d_solvability_uq_v1"

EXPECTED_CORPUS_TASKS = 718
GRADEABLE_CORPUS_TASKS = 609
RETAINED_PANEL_TASKS = 80
MODEL_ARM = "with_jw"

DESIGN_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "solver_variant_id",
    "resource_ladder_id",
    "resource_value",
    "n_centers",
    "n_canonical_families",
    "weight_sum",
    "n_success_centers",
    "design_based_ratio",
    "family_grouped_lower_95",
    "family_grouped_upper_95",
    "family_grouped_accepted_draws",
    "family_grouped_attempted_draws",
    "center_level_lower_95",
    "center_level_upper_95",
    "center_level_accepted_draws",
    "center_level_attempted_draws",
    "primary_interval",
    "estimand",
    "role",
]
MODEL_RATIO_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "estimator",
    "lengthscale_variant",
    "n_gradeable_corpus_tasks",
    "model_based_ratio",
    "credible_lower_95",
    "credible_upper_95",
    "cross_fold_correlation_treatment",
    "output_kind",
]
POSTERIOR_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "gradeable_for_campaign_scoring",
    "in_training_panel",
    "probability_success",
    "probability_success_mackay",
    "latent_mean",
    "latent_sd",
    "credible_lower_95",
    "credible_upper_95",
    "estimator",
    "family_used_as_model_input",
    "output_kind",
]
CALIBRATION_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "estimator",
    "n_labelled",
    "expected_calibration_error",
    "ece_lower_95",
    "ece_upper_95",
    "calibration_slope",
    "slope_lower_95",
    "slope_upper_95",
    "calibration_intercept",
    "brier",
    "brier_reliability",
    "brier_resolution",
    "brier_uncertainty",
    "mean_predicted",
    "observed_frequency",
]
RELIABILITY_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "estimator",
    "bin_index",
    "n_tasks",
    "mean_predicted",
    "observed_frequency",
    "absolute_gap",
]
GATE_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "estimator",
    "expected_calibration_error",
    "ece_threshold",
    "ece_condition_met",
    "calibration_slope",
    "slope_lower_95",
    "slope_upper_95",
    "slope_interval_contains_one",
    "calibration_gate_passed",
]
LENGTHSCALE_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "lengthscale_variant",
    "lengthscale_multiplier",
    "model_based_ratio",
    "expected_calibration_error",
    "calibration_slope",
]
PSD_COLUMNS = [
    "solver_family_id",
    "query_canonical_family",
    "lengthscale_variant",
    "n_training",
    "lengthscale",
    "min_eigenvalue_before_projection",
    "projection_applied",
    "frobenius_norm_of_correction",
]
RATIO_COMPARISON_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "design_based_ratio",
    "design_family_grouped_lower_95",
    "design_family_grouped_upper_95",
    "knn_corpus_hard_label_rate",
    "knn_hard_label_gap_to_design",
    "knn_corpus_mean_probability",
    "knn_mean_probability_gap_to_design",
    "gp_model_based_ratio",
    "gp_credible_lower_95",
    "gp_credible_upper_95",
    "gp_gap_to_design",
    "gp_narrows_hard_label_gap",
    "gp_narrows_mean_probability_gap",
    "calibration_gate_passed",
]


def load_uq_preregistration(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(payload.get("artifact_id") == PREREGISTRATION_ID, "wrong ML-8D prereg")
    _require(
        payload.get("frozen_before_any_estimator_fit") is True,
        "ML-8D preregistration is not frozen",
    )
    _require(payload.get("supersedes") is None, "ML-8D must supersede nothing")
    _require(payload["gate"]["satisfied"] is True, "ML-8D gate is not satisfied")
    return payload


def verify_uq_inputs(
    root: Path, preregistration: Mapping[str, Any]
) -> dict[str, dict[str, str]]:
    resolved: dict[str, dict[str, str]] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path = root / str(specification["path"])
        _require(path.is_file(), f"missing ML-8D input: {name}")
        digest = sha256_file(path)
        _require(
            digest == str(specification["sha256"]),
            f"ML-8D input hash drift: {name} -> {digest}",
        )
        resolved[name] = {"path": str(specification["path"]), "sha256": digest}
    return resolved


# ---------------------------------------------------------------- design track


def _resampled_ratio(
    weights: np.ndarray, success: np.ndarray, counts: np.ndarray
) -> float | None:
    total = float(weights @ counts)
    if total <= 0.0:
        return None
    return float((weights * success) @ counts / total)


def design_based_interval(
    weights: np.ndarray,
    success: np.ndarray,
    families: Sequence[str],
    *,
    grouping: str,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    """Percentile bootstrap for the selection-weighted population rate."""
    rng = np.random.default_rng(seed)
    samples: list[float] = []
    attempted = 0
    if grouping == "family_grouped":
        names = sorted(set(map(str, families)))
        membership = np.asarray(
            [[1.0 if str(family) == name else 0.0 for name in names] for family in families]
        )
        while len(samples) < draws:
            attempted += 1
            _require(attempted <= draws * 100, "unable to obtain nonzero family draws")
            multiplicity = rng.multinomial(len(names), [1.0 / len(names)] * len(names))
            counts = membership @ multiplicity.astype(float)
            value = _resampled_ratio(weights, success, counts)
            if value is not None:
                samples.append(value)
    elif grouping == "center_level":
        size = len(weights)
        while len(samples) < draws:
            attempted += 1
            _require(attempted <= draws * 100, "unable to obtain nonzero center draws")
            counts = rng.multinomial(size, [1.0 / size] * size).astype(float)
            value = _resampled_ratio(weights, success, counts)
            if value is not None:
                samples.append(value)
    else:  # pragma: no cover - guarded by the preregistration
        raise ValueError(f"unknown grouping: {grouping}")
    ordered = np.sort(np.asarray(samples, dtype=float))
    return {
        "lower_95": float(np.quantile(ordered, 0.025, method="linear")),
        "upper_95": float(np.quantile(ordered, 0.975, method="linear")),
        "accepted_draws": len(samples),
        "attempted_draws": attempted,
    }


# ----------------------------------------------------------------- GP machinery


def project_to_psd(
    matrix: np.ndarray, *, tolerance: float, jitter: float
) -> tuple[np.ndarray, dict[str, Any]]:
    """Clip negative eigenvalues; report the correction rather than hide it."""
    symmetric = 0.5 * (matrix + matrix.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    minimum = float(eigenvalues.min())
    applied = minimum < tolerance
    if applied:
        clipped = np.clip(eigenvalues, 0.0, None)
        corrected = (eigenvectors * clipped) @ eigenvectors.T
        correction = float(np.linalg.norm(corrected - symmetric, ord="fro"))
        symmetric = 0.5 * (corrected + corrected.T)
    else:
        correction = 0.0
    symmetric = symmetric + jitter * np.eye(len(symmetric))
    return symmetric, {
        "min_eigenvalue_before_projection": minimum,
        "projection_applied": bool(applied),
        "frobenius_norm_of_correction": correction,
    }


def laplace_gp_fit(
    kernel: np.ndarray, y: np.ndarray, *, max_iterations: int, tolerance: float
) -> dict[str, Any]:
    """Laplace approximation for GP classification (Rasmussen & Williams 3.1)."""
    size = len(y)
    _require(kernel.shape == (size, size), "kernel/label shape mismatch")
    latent = np.zeros(size, dtype=float)
    previous = -np.inf
    for iteration in range(1, max_iterations + 1):
        probability = expit(latent)
        weight = np.clip(probability * (1.0 - probability), 1.0e-12, None)
        root = np.sqrt(weight)
        inner = np.eye(size) + root[:, None] * kernel * root[None, :]
        factor = cholesky(inner, lower=True)
        b = weight * latent + (y - probability)
        adjustment = cho_solve((factor, True), root * (kernel @ b))
        a = b - root * adjustment
        latent = kernel @ a
        probability = expit(latent)
        log_likelihood = float(
            np.sum(
                y * np.log(np.clip(probability, 1.0e-300, None))
                + (1.0 - y) * np.log(np.clip(1.0 - probability, 1.0e-300, None))
            )
        )
        objective = (
            -0.5 * float(a @ latent)
            + log_likelihood
            - float(np.sum(np.log(np.diag(factor))))
        )
        if abs(objective - previous) < tolerance:
            probability = expit(latent)
            weight = np.clip(probability * (1.0 - probability), 1.0e-12, None)
            root = np.sqrt(weight)
            inner = np.eye(size) + root[:, None] * kernel * root[None, :]
            factor = cholesky(inner, lower=True)
            return {
                "latent": latent,
                "gradient": y - probability,
                "sqrt_weight": root,
                "cholesky": factor,
                "log_marginal_likelihood": objective,
                "iterations": iteration,
                "converged": True,
            }
        previous = objective
    raise ValueError("Laplace GP did not converge within the frozen iteration budget")


def laplace_gp_predict(
    fit: Mapping[str, Any], cross_kernel: np.ndarray, query_kernel: np.ndarray
) -> dict[str, np.ndarray]:
    """Joint latent predictive mean and covariance for a query block."""
    mean = cross_kernel.T @ fit["gradient"]
    scaled = fit["sqrt_weight"][:, None] * cross_kernel
    solved = cho_solve((fit["cholesky"], True), scaled, check_finite=False)
    covariance = query_kernel - scaled.T @ solved
    covariance = 0.5 * (covariance + covariance.T)
    variance = np.clip(np.diag(covariance).copy(), 0.0, None)
    return {"mean": mean, "covariance": covariance, "variance": variance}


def mackay_probability(mean: np.ndarray, variance: np.ndarray) -> np.ndarray:
    kappa = 1.0 / np.sqrt(1.0 + math.pi * variance / 8.0)
    return expit(kappa * mean)


def joint_latent_samples(
    mean: np.ndarray, covariance: np.ndarray, *, draws: int, seed: int, jitter: float
) -> np.ndarray:
    size = len(mean)
    padded = covariance + jitter * np.eye(size)
    eigenvalues, eigenvectors = np.linalg.eigh(0.5 * (padded + padded.T))
    root = eigenvectors * np.sqrt(np.clip(eigenvalues, 0.0, None))
    rng = np.random.default_rng(seed)
    normal = rng.standard_normal((draws, size))
    return mean[None, :] + normal @ root.T


# -------------------------------------------------------------- calibration


def reliability_bins(
    probability: np.ndarray, y: np.ndarray, *, bins: int
) -> list[dict[str, Any]]:
    """Equal-count (quantile) bins, ties kept together, deterministic order."""
    order = np.lexsort((np.arange(len(probability)), probability))
    groups = np.array_split(order, bins)
    rows: list[dict[str, Any]] = []
    for index, group in enumerate(groups):
        if not len(group):
            continue
        mean_predicted = float(np.mean(probability[group]))
        observed = float(np.mean(y[group]))
        rows.append(
            {
                "bin_index": index,
                "n_tasks": int(len(group)),
                "mean_predicted": mean_predicted,
                "observed_frequency": observed,
                "absolute_gap": abs(mean_predicted - observed),
            }
        )
    return rows


def expected_calibration_error(
    probability: np.ndarray, y: np.ndarray, *, bins: int
) -> float:
    rows = reliability_bins(probability, y, bins=bins)
    total = float(sum(row["n_tasks"] for row in rows))
    return float(
        sum(row["n_tasks"] / total * row["absolute_gap"] for row in rows)
    )


def calibration_slope_intercept(
    probability: np.ndarray, y: np.ndarray, *, clip: float
) -> tuple[float | None, float | None]:
    if np.unique(y).size < 2:
        return None, None
    logit = np.log(
        np.clip(probability, clip, 1.0 - clip) / (1.0 - np.clip(probability, clip, 1.0 - clip))
    )
    if float(np.ptp(logit)) <= 0.0:
        return None, None
    model = LogisticRegression(
        penalty=None, max_iter=10000, solver="lbfgs", random_state=0
    )
    model.fit(logit.reshape(-1, 1), y)
    return float(model.coef_[0][0]), float(model.intercept_[0])


def brier_decomposition(
    probability: np.ndarray, y: np.ndarray, *, bins: int
) -> dict[str, float]:
    total = len(y)
    base = float(np.mean(y))
    rows = reliability_bins(probability, y, bins=bins)
    reliability = float(
        sum(
            row["n_tasks"] / total * (row["mean_predicted"] - row["observed_frequency"]) ** 2
            for row in rows
        )
    )
    resolution = float(
        sum(
            row["n_tasks"] / total * (row["observed_frequency"] - base) ** 2
            for row in rows
        )
    )
    return {
        "brier": float(np.mean((probability - y) ** 2)),
        "brier_reliability": reliability,
        "brier_resolution": resolution,
        "brier_uncertainty": base * (1.0 - base),
    }


def family_grouped_calibration_intervals(
    probability: np.ndarray,
    y: np.ndarray,
    families: Sequence[str],
    *,
    bins: int,
    clip: float,
    draws: int,
    seed: int,
) -> dict[str, Any]:
    names = sorted(set(map(str, families)))
    index_by_family = {name: np.flatnonzero(np.asarray(families) == name) for name in names}
    rng = np.random.default_rng(seed)
    ece_samples: list[float] = []
    slope_samples: list[float] = []
    attempted = 0
    while attempted < draws:
        attempted += 1
        drawn = rng.integers(0, len(names), size=len(names))
        indices = np.concatenate([index_by_family[names[position]] for position in drawn])
        sample_y = y[indices]
        if np.unique(sample_y).size < 2:
            continue
        sample_probability = probability[indices]
        ece_samples.append(
            expected_calibration_error(sample_probability, sample_y, bins=bins)
        )
        slope, _ = calibration_slope_intercept(sample_probability, sample_y, clip=clip)
        if slope is not None and math.isfinite(slope):
            slope_samples.append(slope)
    result: dict[str, Any] = {
        "ece_lower_95": None,
        "ece_upper_95": None,
        "slope_lower_95": None,
        "slope_upper_95": None,
        "accepted_ece_draws": len(ece_samples),
        "accepted_slope_draws": len(slope_samples),
        "attempted_draws": attempted,
    }
    if ece_samples:
        ordered = np.sort(np.asarray(ece_samples, dtype=float))
        result["ece_lower_95"] = float(np.quantile(ordered, 0.025, method="linear"))
        result["ece_upper_95"] = float(np.quantile(ordered, 0.975, method="linear"))
    if slope_samples:
        ordered = np.sort(np.asarray(slope_samples, dtype=float))
        result["slope_lower_95"] = float(np.quantile(ordered, 0.025, method="linear"))
        result["slope_upper_95"] = float(np.quantile(ordered, 0.975, method="linear"))
    return result


def evaluate_calibration_gate(
    *,
    ece: float,
    slope_lower: float | None,
    slope_upper: float | None,
    ece_threshold: float,
) -> dict[str, Any]:
    ece_met = bool(ece <= ece_threshold)
    contains_one = bool(
        slope_lower is not None
        and slope_upper is not None
        and slope_lower <= 1.0 <= slope_upper
    )
    return {
        "ece_condition_met": ece_met,
        "slope_interval_contains_one": contains_one,
        "calibration_gate_passed": bool(ece_met and contains_one),
    }


def isotonic_fallback_probabilities(
    train_probability: np.ndarray, train_y: np.ndarray, query_probability: np.ndarray
) -> np.ndarray:
    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    model.fit(train_probability, train_y)
    return np.clip(model.predict(query_probability), 0.0, 1.0)


# ------------------------------------------------------------- orchestration


def _report_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://qb-gsee-benchmark/analysis/ml_solvability_uq/report.schema.json",
        "title": "ML-8D UQ solvability estimator report",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "artifact_id",
            "status",
            "effective",
            "supersedes",
            "ratio_of_record",
            "validated_predictor_claim",
            "family_used_as_model_input",
            "every_model_output_labelled_estimate",
            "scope",
            "panel",
            "design_track",
            "model_track",
            "calibration_gate",
            "stop_at",
            "kernel_psd_summary",
            "inputs",
            "preregistration",
        ],
        "properties": {
            "artifact_id": {"const": ARTIFACT_ID},
            "status": {"const": "held_pending_pi_review"},
            "effective": {"const": False},
            "supersedes": {"type": "null"},
            "ratio_of_record": {"const": "design_based"},
            "validated_predictor_claim": {"const": False},
            "family_used_as_model_input": {"const": False},
            "every_model_output_labelled_estimate": {"const": True},
            "scope": {"const": "gradeable_tasks_only"},
            "panel": {"type": "object"},
            "design_track": {"type": "object"},
            "model_track": {"type": "object"},
            "calibration_gate": {"type": "object"},
            "stop_at": {"type": "object"},
            "kernel_psd_summary": {"type": "object"},
            "inputs": {"type": "object"},
            "preregistration": {"type": "object"},
        },
    }


def _fit_gp_variant(
    *,
    distance: np.ndarray,
    families: np.ndarray,
    task_index: Mapping[str, int],
    panel_tasks: Sequence[str],
    labels: Mapping[str, int],
    multiplier: float,
    psd_sink: list[dict[str, Any]] | None,
    solver_family: str,
    lengthscale_variant: str,
    settings: Mapping[str, Any],
    sample_draws: int,
    seed: int,
) -> dict[str, Any]:
    """One leave-one-canonical-family-out GP pass over the whole corpus."""
    guard = settings["psd_guard"]
    newton = settings["newton"]
    panel_indices = np.asarray([task_index[task] for task in panel_tasks], dtype=int)
    y = np.asarray([labels[task] for task in panel_tasks], dtype=float)
    n_corpus = len(families)
    posterior_mean = np.full(n_corpus, np.nan)
    posterior_sd = np.full(n_corpus, np.nan)
    probability = np.full(n_corpus, np.nan)
    mackay = np.full(n_corpus, np.nan)
    lower = np.full(n_corpus, np.nan)
    upper = np.full(n_corpus, np.nan)
    fold_samples: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    panel_families = families[panel_indices]

    for offset, query_family in enumerate(sorted(set(map(str, families)))):
        query_indices = np.flatnonzero(families == query_family)
        keep = panel_families != query_family
        train_indices = panel_indices[keep]
        train_y = y[keep]
        _require(len(train_indices) > 0, f"empty GP training fold: {query_family}")
        _require(
            np.unique(train_y).size == 2,
            f"single-class GP training fold: {query_family}",
        )
        train_distance = distance[np.ix_(train_indices, train_indices)]
        positive = train_distance[train_distance > 0.0]
        _require(positive.size > 0, f"degenerate training distances: {query_family}")
        lengthscale = float(np.median(positive)) * multiplier
        _require(lengthscale > 0.0, f"nonpositive lengthscale: {query_family}")

        raw = np.exp(-(train_distance**2) / (2.0 * lengthscale**2))
        kernel, diagnostics = project_to_psd(
            raw,
            tolerance=float(guard["min_eigenvalue_tolerance"]),
            jitter=float(guard["jitter"]),
        )
        if psd_sink is not None:
            psd_sink.append(
                {
                    "solver_family_id": solver_family,
                    "query_canonical_family": query_family,
                    "lengthscale_variant": lengthscale_variant,
                    "n_training": int(len(train_indices)),
                    "lengthscale": lengthscale,
                    **diagnostics,
                }
            )
        fit = laplace_gp_fit(
            kernel,
            train_y,
            max_iterations=int(newton["max_iterations"]),
            tolerance=float(newton["log_marginal_tolerance"]),
        )
        cross = np.exp(
            -(distance[np.ix_(train_indices, query_indices)] ** 2)
            / (2.0 * lengthscale**2)
        )
        query_kernel = np.exp(
            -(distance[np.ix_(query_indices, query_indices)] ** 2)
            / (2.0 * lengthscale**2)
        )
        predicted = laplace_gp_predict(fit, cross, query_kernel)
        samples = joint_latent_samples(
            predicted["mean"],
            predicted["covariance"],
            draws=sample_draws,
            seed=seed + offset,
            jitter=float(guard["jitter"]),
        )
        transformed = expit(samples)
        posterior_mean[query_indices] = predicted["mean"]
        posterior_sd[query_indices] = np.sqrt(predicted["variance"])
        probability[query_indices] = transformed.mean(axis=0)
        mackay[query_indices] = mackay_probability(
            predicted["mean"], predicted["variance"]
        )
        lower[query_indices] = np.quantile(transformed, 0.025, axis=0, method="linear")
        upper[query_indices] = np.quantile(transformed, 0.975, axis=0, method="linear")
        fold_samples[query_family] = (query_indices, transformed)

    _require(bool(np.isfinite(probability).all()), "GP left a corpus task unpredicted")
    return {
        "probability": probability,
        "mackay": mackay,
        "latent_mean": posterior_mean,
        "latent_sd": posterior_sd,
        "lower": lower,
        "upper": upper,
        "fold_samples": fold_samples,
    }


def _corpus_ratio_interval(
    fold_samples: Mapping[str, tuple[np.ndarray, np.ndarray]],
    gradeable_mask: np.ndarray,
) -> dict[str, Any]:
    """Combine per-fold joint samples into a corpus-ratio credible interval."""
    total = None
    count = 0
    for _, (indices, transformed) in sorted(fold_samples.items()):
        selected = gradeable_mask[indices]
        if not selected.any():
            continue
        contribution = transformed[:, selected].sum(axis=1)
        total = contribution if total is None else total + contribution
        count += int(selected.sum())
    _require(total is not None and count > 0, "no gradeable task entered the ratio")
    ratios = np.sort(total / float(count))
    return {
        "n_gradeable_corpus_tasks": count,
        "credible_lower_95": float(np.quantile(ratios, 0.025, method="linear")),
        "credible_upper_95": float(np.quantile(ratios, 0.975, method="linear")),
    }


def _markdown_report(
    report: Mapping[str, Any],
    design: Sequence[Mapping[str, Any]],
    gate: Sequence[Mapping[str, Any]],
    comparison: Sequence[Mapping[str, Any]],
) -> str:
    panel = report["panel"]
    calibration = report["calibration_gate"]
    lines = [
        "# ML-8D UQ solvability estimator + solvability-ratio v2 — HELD",
        "",
        "Two-track estimator over **gradeable tasks only**. The design-based",
        "selection-weighted rate is the **ratio of record**; the model-based track",
        "is a calibration-gated estimate. Every model output here is an estimate:",
        "the ML-6 no-validated-predictor rule stands.",
        "",
        "## Scope",
        "",
        f"- gradeable corpus population: {panel['gradeable_corpus_tasks']}",
        f"- design-track covered subpopulation: {panel['design_covered']} "
        f"(orphaned {panel['design_orphaned']}, disclosed never reassigned)",
        f"- training labels: {panel['training_panel_tasks']} retained gradeable "
        f"panel tasks in {panel['training_canonical_families']} canonical families",
        f"- variants: {panel['variants']}; LOFO folds: {panel['lofo_folds']}",
        f"- per-task posterior rows: {panel['posterior_rows']}",
        "",
        "## Track 1 — design-based ratio (ratio of record)",
        "",
        "| variant | successes/centers | ratio | family-grouped 95% (PRIMARY) "
        "| center-level 95% (sensitivity) |",
        "|---|---|---|---|---|",
    ]
    for row in design:
        lines.append(
            f"| `{row['solver_short_name']}` | "
            f"{row['n_success_centers']}/{row['n_centers']} | "
            f"{float(row['design_based_ratio']):.6f} | "
            f"[{float(row['family_grouped_lower_95']):.6f}, "
            f"{float(row['family_grouped_upper_95']):.6f}] | "
            f"[{float(row['center_level_lower_95']):.6f}, "
            f"{float(row['center_level_upper_95']):.6f}] |"
        )
    lines += [
        "",
        "## Track 2 — calibration gate (the validation gate)",
        "",
        f"Frozen thresholds: ECE ≤ {calibration['ece_threshold']} AND the "
        f"family-grouped 95% calibration-slope interval contains 1.0. Bins: "
        f"{calibration['reliability_bins']} equal-count.",
        "",
        f"**Variants passing the gate: {calibration['passed_count']} of "
        f"{calibration['assessed_count']}.**",
        "",
        "| variant | ECE | ECE ≤ threshold | slope | slope 95% | contains 1 | gate |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in gate:
        def _fmt(value: Any) -> str:
            return "—" if value is None else f"{float(value):.4f}"

        interval = (
            "—"
            if row["slope_lower_95"] is None
            else f"[{float(row['slope_lower_95']):.4f}, {float(row['slope_upper_95']):.4f}]"
        )
        lines.append(
            f"| `{row['solver_short_name']}` | {_fmt(row['expected_calibration_error'])} "
            f"| {str(row['ece_condition_met']).lower()} | {_fmt(row['calibration_slope'])} "
            f"| {interval} | {str(row['slope_interval_contains_one']).lower()} "
            f"| **{'PASS' if row['calibration_gate_passed'] else 'fail'}** |"
        )
    if report["stop_at"]["triggered"]:
        lines += [
            "",
            "> **STOP-AT TRIGGERED — FLAG FOR PI.** At least one variant passes the",
            "> frozen calibration gate. That is a claim-language decision, not an ML",
            "> agent conclusion: the numbers are reported plainly and no",
            "> interpretation, paper framing, or predictor claim is offered. Matt acks",
            "> claim language; the PI reviews first.",
        ]
    else:
        lines += [
            "",
            "STOP-AT not triggered: no variant passes the frozen calibration gate.",
            "The model track therefore remains an uncalibrated estimate and the",
            "design-based ratio remains the sole ratio of record.",
        ]
    lines += [
        "",
        "## Ratio comparison — design vs kNN vs GP",
        "",
        "The kNN column of record is reported **twice**: as the argmax hard-label",
        "rate (the quantity behind the quoted 0.150) and as the mean predicted",
        "probability of the same predictions. The design-based ratio is a",
        "probability-scale quantity, so both are shown to keep a thresholding",
        "effect distinguishable from probability miscalibration.",
        "",
        "| variant | design | kNN hard-label | kNN mean prob | GP | GP 95% credible |",
        "|---|---|---|---|---|---|",
    ]
    for row in comparison:
        lines.append(
            f"| `{row['solver_short_name']}` | "
            f"{float(row['design_based_ratio']):.6f} | "
            f"{float(row['knn_corpus_hard_label_rate']):.6f} | "
            f"{float(row['knn_corpus_mean_probability']):.6f} | "
            f"{float(row['gp_model_based_ratio']):.6f} | "
            f"[{float(row['gp_credible_lower_95']):.6f}, "
            f"{float(row['gp_credible_upper_95']):.6f}] |"
        )
    psd = report["kernel_psd_summary"]
    lines += [
        "",
        "## Kernel PSD diagnostics (disclosed, never silent)",
        "",
        f"- kernels fitted: {psd['kernels']}",
        f"- nearest-PSD projections applied: {psd['projections_applied']}",
        f"- most negative eigenvalue seen before projection: "
        f"{psd['min_eigenvalue_overall']:.3e}",
        f"- largest Frobenius correction: {psd['max_frobenius_correction']:.3e}",
        "",
        "The block-averaged metric is not guaranteed Euclidean, so the Gram matrix",
        "is not guaranteed positive semidefinite; every correction is recorded",
        "per kernel in `kernel_psd_diagnostics.csv`.",
        "",
        "## Fences honoured",
        "",
        "- supersedes nothing; the census, ML-8C annex, and `final_v4` are read-only",
        "- no new label, feature, variant, solver run, or reselection",
        "- no family, mask, reason, or provenance column enters any model",
        "- design-based ratio is the ratio of record; no model output displaces it",
        "- internal analysis only: no public or dashboard placement",
        "",
    ]
    return "\n".join(lines)


def run_solvability_uq(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Execute one complete deterministic ML-8D run."""
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    settings = load_uq_preregistration(preregistration_path)
    inputs = verify_uq_inputs(root, settings)

    parent_directory = root / "analysis/ml_g50_solver_families"
    parent_path = parent_directory / "preregistration.json"
    parent = load_parent_preregistration(parent_path)
    verify_inputs(root, parent)

    features = pd.read_csv(
        resolve_input_path(root, parent["inputs"]["feature_table"]), low_memory=False
    )
    metadata = pd.read_csv(
        resolve_input_path(root, parent["inputs"]["feature_metadata"])
    )
    taxonomy = json.loads(
        resolve_input_path(root, parent["inputs"]["canonical_families"]).read_text(
            encoding="utf-8"
        )
    )
    identifiers = json.loads(
        resolve_input_path(root, parent["inputs"]["identifier_screen"]).read_text(
            encoding="utf-8"
        )
    )["identifier_columns"]
    canonical = canonical_family_map(taxonomy)
    tasks = list(map(str, features["task_uuid"]))
    _require(
        len(tasks) == len(set(tasks)) == EXPECTED_CORPUS_TASKS,
        "feature task census changed",
    )
    families = np.asarray([canonical[task] for task in tasks], dtype=object)
    task_index = {task: index for index, task in enumerate(tasks)}
    policy = derive_feature_policy(metadata, identifiers)

    census = pd.read_csv(root / str(settings["inputs"]["gradeability_census"]["path"]))
    gradeable = {
        str(row.task_uuid): bool(row.gradeable_for_campaign_scoring)
        for row in census.itertuples(index=False)
    }
    gradeable_mask = np.asarray([gradeable[task] for task in tasks], dtype=bool)
    _require(
        int(gradeable_mask.sum()) == GRADEABLE_CORPUS_TASKS,
        f"gradeable corpus census changed: {int(gradeable_mask.sum())}",
    )

    observations = pd.read_csv(
        root / str(settings["inputs"]["masked_observations"]["path"])
    )
    panel_tasks = sorted(set(map(str, observations["task_uuid"])))
    _require(
        len(panel_tasks) == RETAINED_PANEL_TASKS,
        f"retained panel census changed: {len(panel_tasks)}",
    )
    _require(
        all(gradeable[task] for task in panel_tasks),
        "a non-gradeable task reached the ML-8D training panel",
    )
    weight_frame = pd.read_csv(
        root / str(settings["inputs"]["gradeable_selection_weights"]["path"])
    )
    weights = {
        str(row.task_uuid): int(row.gradeable_selection_weight)
        for row in weight_frame.itertuples(index=False)
    }
    _require(set(weights) == set(panel_tasks), "weight/panel task mismatch")
    ml8c_report = json.loads(
        (root / str(settings["inputs"]["ml8c_report"]["path"])).read_text(
            encoding="utf-8"
        )
    )
    population = ml8c_report["gradeable_population"]
    _require(
        int(population["restated_weight_sum"]) == sum(weights.values()),
        "weight sum disagrees with the ML-8C report",
    )

    knn = pd.read_csv(root / str(settings["inputs"]["knn_predictions"]["path"]))
    knn = knn.loc[knn["feature_arm"].astype(str) == MODEL_ARM]

    variants = g50_variant_rows(
        resolve_input_path(root, parent["inputs"]["solver_family_catalog"])
    )
    labelled_uuids = set(map(str, observations["solver_uuid"]))
    variants = [
        variant for variant in variants if str(variant["solver_uuid"]) in labelled_uuids
    ]
    _require(bool(variants), "no labelled variant available")

    distances: dict[str, np.ndarray] = {}
    for solver_family, columns in sorted(policy["solver_family_columns"].items()):
        models = build_block_models(
            features,
            metadata,
            columns,
            scaling=str(parent["feature_policy"]["scaling"]),
            variance_threshold=float(
                parent["feature_policy"]["pca_variance_threshold"]
            ),
            universal_only=False,
        )
        distances[solver_family] = block_aware_distance(len(features), models)[0]

    design_settings = settings["design_based_track"]["bootstrap"]
    model_settings = settings["model_based_track"]
    gate_settings = settings["calibration_gate"]
    ratio_settings = settings["model_based_ratio"]["credible_interval"]
    ece_threshold = 0.10
    for condition in gate_settings["pass_conditions_all_required"]:
        if condition.startswith("expected_calibration_error <="):
            ece_threshold = float(condition.split("<=")[1])

    lengthscale_variants: list[tuple[str, float]] = [("median", 1.0)]
    for multiplier in model_settings["lengthscale_sensitivity_multipliers"]:
        lengthscale_variants.append((f"median_x{multiplier:g}", float(multiplier)))

    design_rows: list[dict[str, Any]] = []
    model_ratio_rows: list[dict[str, Any]] = []
    posterior_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    reliability_rows: list[dict[str, Any]] = []
    gate_rows: list[dict[str, Any]] = []
    lengthscale_rows: list[dict[str, Any]] = []
    psd_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    psd_seen: set[tuple[str, str]] = set()

    for variant in sorted(variants, key=lambda row: (row["solver_family_id"], row["solver_short_name"])):
        uuid = str(variant["solver_uuid"])
        solver_family = str(variant["solver_family_id"])
        data = observations.loc[observations["solver_uuid"].astype(str) == uuid]
        labels = {
            str(row.task_uuid): int(str(row.observed_outcome) == "success")
            for row in data.itertuples(index=False)
        }
        _require(set(labels) == set(panel_tasks), f"label/panel mismatch: {uuid}")

        # ---- Track 1: design-based ratio of record
        weight_vector = np.asarray(
            [float(weights[task]) for task in panel_tasks], dtype=float
        )
        success_vector = np.asarray(
            [float(labels[task]) for task in panel_tasks], dtype=float
        )
        center_families = [canonical[task] for task in panel_tasks]
        ratio = float((weight_vector * success_vector).sum() / weight_vector.sum())
        grouped = design_based_interval(
            weight_vector,
            success_vector,
            center_families,
            grouping="family_grouped",
            draws=int(design_settings["draws"]),
            seed=int(design_settings["seed"]),
        )
        center_level = design_based_interval(
            weight_vector,
            success_vector,
            center_families,
            grouping="center_level",
            draws=int(design_settings["draws"]),
            seed=int(design_settings["seed"]),
        )
        design_rows.append(
            {
                "solver_family_id": solver_family,
                "solver_short_name": variant["solver_short_name"],
                "solver_uuid": uuid,
                "solver_variant_id": variant["solver_variant_id"],
                "resource_ladder_id": variant["resource_ladder_id"],
                "resource_value": variant["resource_value"],
                "n_centers": len(panel_tasks),
                "n_canonical_families": len(set(center_families)),
                "weight_sum": int(weight_vector.sum()),
                "n_success_centers": int(success_vector.sum()),
                "design_based_ratio": ratio,
                "family_grouped_lower_95": grouped["lower_95"],
                "family_grouped_upper_95": grouped["upper_95"],
                "family_grouped_accepted_draws": grouped["accepted_draws"],
                "family_grouped_attempted_draws": grouped["attempted_draws"],
                "center_level_lower_95": center_level["lower_95"],
                "center_level_upper_95": center_level["upper_95"],
                "center_level_accepted_draws": center_level["accepted_draws"],
                "center_level_attempted_draws": center_level["attempted_draws"],
                "primary_interval": "family_grouped",
                "estimand": "covered_gradeable_subpopulation",
                "role": "ratio_of_record",
            }
        )

        # ---- Track 2: GP over each lengthscale variant
        primary: dict[str, Any] | None = None
        primary_gate: dict[str, Any] | None = None
        for lengthscale_variant, multiplier in lengthscale_variants:
            sink = None
            key = (solver_family, lengthscale_variant)
            if key not in psd_seen:
                psd_seen.add(key)
                sink = psd_rows
            fitted = _fit_gp_variant(
                distance=distances[solver_family],
                families=families,
                task_index=task_index,
                panel_tasks=panel_tasks,
                labels=labels,
                multiplier=multiplier,
                psd_sink=sink,
                solver_family=solver_family,
                lengthscale_variant=lengthscale_variant,
                settings=model_settings,
                sample_draws=int(ratio_settings["joint_latent_samples_per_fold"]),
                seed=int(ratio_settings["seed"]),
            )
            interval = _corpus_ratio_interval(fitted["fold_samples"], gradeable_mask)
            model_ratio = float(fitted["probability"][gradeable_mask].mean())

            panel_positions = np.asarray(
                [task_index[task] for task in panel_tasks], dtype=int
            )
            out_of_fold = fitted["probability"][panel_positions]
            labelled_y = np.asarray(
                [labels[task] for task in panel_tasks], dtype=float
            )
            panel_families = [canonical[task] for task in panel_tasks]
            ece = expected_calibration_error(
                out_of_fold, labelled_y, bins=int(gate_settings["reliability_bins"])
            )
            slope, intercept = calibration_slope_intercept(
                out_of_fold, labelled_y, clip=float(gate_settings["logit_clip"])
            )
            bounds = family_grouped_calibration_intervals(
                out_of_fold,
                labelled_y,
                panel_families,
                bins=int(gate_settings["reliability_bins"]),
                clip=float(gate_settings["logit_clip"]),
                draws=int(gate_settings["bootstrap"]["draws"]),
                seed=int(gate_settings["bootstrap"]["seed"]),
            )
            lengthscale_rows.append(
                {
                    "solver_family_id": solver_family,
                    "solver_short_name": variant["solver_short_name"],
                    "solver_uuid": uuid,
                    "lengthscale_variant": lengthscale_variant,
                    "lengthscale_multiplier": multiplier,
                    "model_based_ratio": model_ratio,
                    "expected_calibration_error": ece,
                    "calibration_slope": slope,
                }
            )
            model_ratio_rows.append(
                {
                    "solver_family_id": solver_family,
                    "solver_short_name": variant["solver_short_name"],
                    "solver_uuid": uuid,
                    "estimator": "gp_laplace_block_aware",
                    "lengthscale_variant": lengthscale_variant,
                    "n_gradeable_corpus_tasks": interval["n_gradeable_corpus_tasks"],
                    "model_based_ratio": model_ratio,
                    "credible_lower_95": interval["credible_lower_95"],
                    "credible_upper_95": interval["credible_upper_95"],
                    "cross_fold_correlation_treatment": str(
                        ratio_settings["cross_fold_posterior_correlation"]
                    ),
                    "output_kind": "estimate",
                }
            )
            if lengthscale_variant != "median":
                continue

            primary = {
                "fitted": fitted,
                "interval": interval,
                "model_ratio": model_ratio,
                "out_of_fold": out_of_fold,
                "labelled_y": labelled_y,
            }
            decomposition = brier_decomposition(
                out_of_fold, labelled_y, bins=int(gate_settings["reliability_bins"])
            )
            calibration_rows.append(
                {
                    "solver_family_id": solver_family,
                    "solver_short_name": variant["solver_short_name"],
                    "solver_uuid": uuid,
                    "estimator": "gp_laplace_block_aware",
                    "n_labelled": len(panel_tasks),
                    "expected_calibration_error": ece,
                    "ece_lower_95": bounds["ece_lower_95"],
                    "ece_upper_95": bounds["ece_upper_95"],
                    "calibration_slope": slope,
                    "slope_lower_95": bounds["slope_lower_95"],
                    "slope_upper_95": bounds["slope_upper_95"],
                    "calibration_intercept": intercept,
                    **decomposition,
                    "mean_predicted": float(out_of_fold.mean()),
                    "observed_frequency": float(labelled_y.mean()),
                }
            )
            for row in reliability_bins(
                out_of_fold, labelled_y, bins=int(gate_settings["reliability_bins"])
            ):
                reliability_rows.append(
                    {
                        "solver_family_id": solver_family,
                        "solver_short_name": variant["solver_short_name"],
                        "solver_uuid": uuid,
                        "estimator": "gp_laplace_block_aware",
                        **row,
                    }
                )
            verdict = evaluate_calibration_gate(
                ece=ece,
                slope_lower=bounds["slope_lower_95"],
                slope_upper=bounds["slope_upper_95"],
                ece_threshold=ece_threshold,
            )
            primary_gate = verdict
            gate_rows.append(
                {
                    "solver_family_id": solver_family,
                    "solver_short_name": variant["solver_short_name"],
                    "solver_uuid": uuid,
                    "estimator": "gp_laplace_block_aware",
                    "expected_calibration_error": ece,
                    "ece_threshold": ece_threshold,
                    "calibration_slope": slope,
                    "slope_lower_95": bounds["slope_lower_95"],
                    "slope_upper_95": bounds["slope_upper_95"],
                    **verdict,
                }
            )
            for position, task in enumerate(tasks):
                posterior_rows.append(
                    {
                        "task_uuid": task,
                        "canonical_family": canonical[task],
                        "solver_family_id": solver_family,
                        "solver_short_name": variant["solver_short_name"],
                        "solver_uuid": uuid,
                        "gradeable_for_campaign_scoring": bool(gradeable_mask[position]),
                        "in_training_panel": task in labels,
                        "probability_success": float(fitted["probability"][position]),
                        "probability_success_mackay": float(fitted["mackay"][position]),
                        "latent_mean": float(fitted["latent_mean"][position]),
                        "latent_sd": float(fitted["latent_sd"][position]),
                        "credible_lower_95": float(fitted["lower"][position]),
                        "credible_upper_95": float(fitted["upper"][position]),
                        "estimator": "gp_laplace_block_aware",
                        "family_used_as_model_input": False,
                        "output_kind": "estimate",
                    }
                )

        _require(primary is not None and primary_gate is not None, "primary GP missing")
        variant_knn = knn.loc[knn["solver_uuid"].astype(str) == uuid]
        _require(len(variant_knn) == EXPECTED_CORPUS_TASKS, f"kNN census: {uuid}")
        knn_gradeable = variant_knn.loc[
            variant_knn["task_uuid"].astype(str).map(gradeable)
        ]
        hard_rate = float(
            (knn_gradeable["predicted_outcome"].astype(str) == "success").mean()
        )
        mean_probability = float(knn_gradeable["probability_success"].astype(float).mean())
        gp_gap = abs(primary["model_ratio"] - ratio)
        comparison_rows.append(
            {
                "solver_family_id": solver_family,
                "solver_short_name": variant["solver_short_name"],
                "solver_uuid": uuid,
                "design_based_ratio": ratio,
                "design_family_grouped_lower_95": grouped["lower_95"],
                "design_family_grouped_upper_95": grouped["upper_95"],
                "knn_corpus_hard_label_rate": hard_rate,
                "knn_hard_label_gap_to_design": abs(hard_rate - ratio),
                "knn_corpus_mean_probability": mean_probability,
                "knn_mean_probability_gap_to_design": abs(mean_probability - ratio),
                "gp_model_based_ratio": primary["model_ratio"],
                "gp_credible_lower_95": primary["interval"]["credible_lower_95"],
                "gp_credible_upper_95": primary["interval"]["credible_upper_95"],
                "gp_gap_to_design": gp_gap,
                "gp_narrows_hard_label_gap": bool(gp_gap < abs(hard_rate - ratio)),
                "gp_narrows_mean_probability_gap": bool(
                    gp_gap < abs(mean_probability - ratio)
                ),
                "calibration_gate_passed": primary_gate["calibration_gate_passed"],
            }
        )

    passed = sum(1 for row in gate_rows if row["calibration_gate_passed"])
    minimum_eigenvalue = min(
        float(row["min_eigenvalue_before_projection"]) for row in psd_rows
    )
    report = {
        "artifact_id": ARTIFACT_ID,
        "status": "held_pending_pi_review",
        "effective": False,
        "supersedes": None,
        "ratio_of_record": "design_based",
        "validated_predictor_claim": False,
        "family_used_as_model_input": False,
        "every_model_output_labelled_estimate": True,
        "scope": "gradeable_tasks_only",
        "panel": {
            "corpus_tasks": EXPECTED_CORPUS_TASKS,
            "gradeable_corpus_tasks": int(gradeable_mask.sum()),
            "design_covered": int(population["gradeable_population_covered"]),
            "design_orphaned": int(population["gradeable_population_orphaned"]),
            "training_panel_tasks": len(panel_tasks),
            "training_canonical_families": len(
                {canonical[task] for task in panel_tasks}
            ),
            "variants": len(variants),
            "lofo_folds": len(set(map(str, families))),
            "posterior_rows": len(posterior_rows),
            "lengthscale_variants": [name for name, _ in lengthscale_variants],
        },
        "design_track": {
            "role": "ratio_of_record",
            "estimand": "covered_gradeable_subpopulation",
            "primary_interval": "family_grouped",
            "sensitivity_interval": "center_level",
            "bootstrap_draws": int(design_settings["draws"]),
            "bootstrap_seed": int(design_settings["seed"]),
            "ratio_range": [
                min(float(row["design_based_ratio"]) for row in design_rows),
                max(float(row["design_based_ratio"]) for row in design_rows),
            ],
            "displaced_by_model_output": False,
        },
        "model_track": {
            "estimator": "gp_laplace_block_aware",
            "kernel": str(model_settings["kernel"]),
            "lengthscale_rule": str(model_settings["lengthscale_rule"]),
            "lengthscale_optimised": False,
            "geometry_re_derived": False,
            "fallback_used_for_variants": [],
            "ratio_range": [
                min(
                    float(row["model_based_ratio"])
                    for row in model_ratio_rows
                    if row["lengthscale_variant"] == "median"
                ),
                max(
                    float(row["model_based_ratio"])
                    for row in model_ratio_rows
                    if row["lengthscale_variant"] == "median"
                ),
            ],
            "cross_fold_posterior_correlation": str(
                ratio_settings["cross_fold_posterior_correlation"]
            ),
            "cross_fold_assumption_is_declared_approximation": True,
            "output_kind": "estimate",
        },
        "calibration_gate": {
            "nature": "calibration_not_discrimination",
            "reliability_bins": int(gate_settings["reliability_bins"]),
            "ece_threshold": ece_threshold,
            "slope_condition": "family-grouped 95% interval contains 1.0",
            "assessed_count": len(gate_rows),
            "passed_count": passed,
            "passed_variants": [
                str(row["solver_short_name"])
                for row in gate_rows
                if row["calibration_gate_passed"]
            ],
            "pooling_across_variants": False,
            "multiplicity_claim": False,
        },
        "stop_at": {
            "triggered": bool(passed > 0),
            "rule": "any variant passing the frozen calibration gate is a claim-language decision requiring PI review and Matt's ack",
            "interpretation_offered": False,
            "no_validated_predictor_rule_stands": True,
        },
        "kernel_psd_summary": {
            "kernels": len(psd_rows),
            "projections_applied": sum(
                1 for row in psd_rows if row["projection_applied"]
            ),
            "min_eigenvalue_overall": minimum_eigenvalue,
            "max_frobenius_correction": max(
                float(row["frobenius_norm_of_correction"]) for row in psd_rows
            ),
            "silent_correction": False,
        },
        "inputs": inputs,
        "preregistration": {
            "artifact_id": settings["artifact_id"],
            "path": str(preregistration_path.relative_to(root)),
            "sha256": sha256_file(preregistration_path),
        },
    }
    Draft202012Validator(_report_schema()).validate(report)

    output_directory.mkdir(parents=True, exist_ok=False)
    stable_csv_dump(
        design_rows, DESIGN_COLUMNS, output_directory / "design_based_ratios.csv"
    )
    stable_csv_dump(
        model_ratio_rows, MODEL_RATIO_COLUMNS, output_directory / "model_based_ratios.csv"
    )
    stable_csv_dump(
        posterior_rows, POSTERIOR_COLUMNS, output_directory / "per_task_posterior.csv"
    )
    stable_csv_dump(
        calibration_rows, CALIBRATION_COLUMNS, output_directory / "calibration.csv"
    )
    stable_csv_dump(
        reliability_rows, RELIABILITY_COLUMNS, output_directory / "reliability_bins.csv"
    )
    stable_csv_dump(gate_rows, GATE_COLUMNS, output_directory / "calibration_gate.csv")
    stable_csv_dump(
        lengthscale_rows,
        LENGTHSCALE_COLUMNS,
        output_directory / "lengthscale_sensitivity.csv",
    )
    stable_csv_dump(
        psd_rows, PSD_COLUMNS, output_directory / "kernel_psd_diagnostics.csv"
    )
    stable_csv_dump(
        comparison_rows, RATIO_COMPARISON_COLUMNS, output_directory / "ratio_comparison.csv"
    )
    stable_json_dump(report, output_directory / "report.json")
    stable_json_dump(_report_schema(), output_directory / "schemas/report.schema.json")
    (output_directory / "REPORT.md").write_text(
        _markdown_report(report, design_rows, gate_rows, comparison_rows),
        encoding="utf-8",
    )

    manifest_files = sorted(
        path
        for path in output_directory.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    manifest = {
        "artifact_id": "ml8d_solvability_uq_manifest_v1",
        "status": "held_pending_pi_review",
        "effective": False,
        "supersedes": None,
        "ratio_of_record": "design_based",
        "files": [
            {
                "path": str(path.relative_to(output_directory)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in manifest_files
        ],
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return {"report": report, "manifest": manifest, "comparison": comparison_rows}
