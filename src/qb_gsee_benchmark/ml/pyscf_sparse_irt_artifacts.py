"""Deterministic artifacts for the frozen ML-10C sparse Bayesian analysis."""

from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from qb_gsee_benchmark.ml.bayesian_irt_run import _deterministic_npz, _posterior_array
from qb_gsee_benchmark.ml.core_set import _require, sha256_file, stable_csv_dump, stable_json_dump
from qb_gsee_benchmark.ml.pyscf_sparse_irt import MODEL_NAMES, SECOND_MARKER, SparseFit, SparseIrtData, prepare_sparse_irt_data
from qb_gsee_benchmark.ml.pyscf_sparse_irt_fit import _comparison, _difficulty_shift, _response_records, _summary, fit_sparse_models


REQUIRED_FILES = (
    "REPORT.md",
    "artifact_manifest.json",
    "cross_validation_diagnostics.csv",
    "cross_validation_folds.csv",
    "cross_validation_log_predictive_density.npz",
    "cross_validation_pointwise.csv",
    "difficulty_shift.csv",
    "dimensionality_comparison.csv",
    "environment.json",
    "factor_loadings.csv",
    "factor_preprocessing.csv",
    "item_parameters.csv",
    "posterior_diagnostics.csv",
    "posterior_samples.npz",
    "report.json",
    "response_matrix.csv",
    "task_difficulty.csv",
)


def write_sparse_artifacts(
    root: Path,
    preregistration_path: Path,
    output_directory: Path,
    data: SparseIrtData,
    fit: SparseFit,
) -> dict[str, Any]:
    preregistration = __import__("json").loads(preregistration_path.read_text(encoding="utf-8"))
    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)

    response_rows = _response_records(data)
    stable_csv_dump(response_rows, list(response_rows[0]), output_directory / "response_matrix.csv")

    binary_difficulty = _posterior_array(fit.traces["binary_rasch"], "task_difficulty")
    continuous_difficulty = _posterior_array(fit.traces["continuous_beta"], "task_difficulty")
    binary_ability = _posterior_array(fit.traces["binary_rasch"], "item_ability")
    continuous_ability = _posterior_array(fit.traces["continuous_beta"], "item_ability")
    binary_limit = _posterior_array(fit.traces["binary_rasch"], "difficulty_limit_10pct")
    precision = _posterior_array(fit.traces["continuous_beta"], "item_precision")
    consistency = _posterior_array(fit.traces["continuous_beta"], "item_consistency")
    one_loading = _posterior_array(fit.traces["one_factor"], "factor_loading")
    two_loading = _posterior_array(fit.traces["two_factor"], "factor_loading")

    task_rows = []
    for index, task_id in enumerate(data.task_ids):
        row: dict[str, Any] = {
            "task_uuid": task_id,
            "canonical_family": data.task_families[index],
            "primary_hardness_track": "binary_rasch_23_item_sparse",
            "output_kind": "posterior_estimate",
        }
        for prefix, values in (("binary_difficulty", binary_difficulty), ("continuous_difficulty", continuous_difficulty)):
            row.update({f"{prefix}_{name}": value for name, value in _summary(values, index).items()})
        task_rows.append(row)
    stable_csv_dump(task_rows, list(task_rows[0]), output_directory / "task_difficulty.csv")

    item_rows = []
    for index, item_id in enumerate(data.item_ids):
        row = {
            "solver_group": data.solver_groups[data.item_solver_group_index[index]],
            "item_id": item_id,
            "item_name": data.item_names[index],
            "item_discrimination": 1.0,
            "difficulty_limit_probability": 0.1,
            "output_kind": "posterior_estimate",
        }
        for prefix, values in (
            ("binary_ability", binary_ability),
            ("continuous_ability", continuous_ability),
            ("difficulty_limit_10pct", binary_limit),
            ("continuous_precision", precision),
            ("continuous_consistency", consistency),
        ):
            row.update({f"{prefix}_{name}": value for name, value in _summary(values, index).items()})
        item_rows.append(row)
    stable_csv_dump(item_rows, list(item_rows[0]), output_directory / "item_parameters.csv")

    shift_rows, shift_metrics = _difficulty_shift(root, preregistration, binary_difficulty, data)
    stable_csv_dump(shift_rows, list(shift_rows[0]), output_directory / "difficulty_shift.csv")

    preprocessing_rows = [
        {
            "solver_group": data.solver_groups[data.item_solver_group_index[index]],
            "item_id": item_id,
            "training_scope": "full_96_task_observed_cells",
            "observed_cells": int(np.sum(data.observation_item_index == index)),
            "logit_quality_mean": fit.transform.mean[index],
            "logit_quality_sample_sd": fit.transform.scale[index],
            "output_kind": "factor_preprocessing_parameter",
        }
        for index, item_id in enumerate(data.item_ids)
    ]
    stable_csv_dump(preprocessing_rows, list(preprocessing_rows[0]), output_directory / "factor_preprocessing.csv")

    loading_rows = []
    for index, item_id in enumerate(data.item_ids):
        for model, factor, values in (
            ("one_factor", "ladder_axis", one_loading),
            ("two_factor", "ladder_axis", two_loading[..., 0]),
            ("two_factor", "single_reference_multireference_axis", two_loading[..., 1]),
        ):
            loading_rows.append({
                "model": model,
                "factor": factor,
                "solver_group": data.solver_groups[data.item_solver_group_index[index]],
                "item_id": item_id,
                **_summary(values, index),
                "output_kind": "posterior_estimate_exploratory",
            })
    stable_csv_dump(loading_rows, list(loading_rows[0]), output_directory / "factor_loadings.csv")

    comparison = _comparison(fit)
    pyscf_indices = np.arange(18, 23, dtype=int)
    ladder_indices = np.arange(18, dtype=int)
    numerator = np.median(two_loading[..., pyscf_indices, 1], axis=-1)
    denominator = np.median(two_loading[..., ladder_indices, 1], axis=-1)
    _require(bool(np.all(denominator > 0.0)), "zero ladder loading contrast denominator")
    contrast = numerator / denominator
    contrast_probability = float(np.mean(contrast > 1.0))
    hypothesis_supported = bool(
        comparison["decision"] == "favor_two_factors"
        and comparison["reliable"]
        and contrast_probability >= 0.95
    )
    dimensionality_rows = []
    for name in ("one_factor", "two_factor"):
        values = fit.cross_validation_log_predictive_density[name]
        dimensionality_rows.append({
            "model": name,
            "elpd_exact_5fold": float(np.sum(values)),
            "se": float(np.sqrt(len(values) * np.var(values, ddof=1))),
            "pointwise_unit": "heldout_task_observed_item_subset",
            "canonical_family_blocked": True,
            **comparison,
            "pyscf_second_axis_loading_contrast_probability_gt_one": contrast_probability,
            "marker_constraint_caveat": True,
            "named_hypothesis": "single_reference_multireference_axis",
            "named_hypothesis_supported": hypothesis_supported,
            "output_kind": "posterior_estimate_exploratory",
        })
    stable_csv_dump(dimensionality_rows, list(dimensionality_rows[0]), output_directory / "dimensionality_comparison.csv")

    fold_rows = [
        {
            "task_uuid": task_id,
            "canonical_family": data.task_families[index],
            "fold": int(fit.folds[index]) + 1,
            "output_kind": "cross_validation_assignment",
        }
        for index, task_id in enumerate(data.task_ids)
    ]
    stable_csv_dump(fold_rows, list(fold_rows[0]), output_directory / "cross_validation_folds.csv")
    stable_csv_dump(fit.cross_validation_diagnostics, list(fit.cross_validation_diagnostics[0]), output_directory / "cross_validation_diagnostics.csv")
    pointwise_rows = []
    for index, task_id in enumerate(data.task_ids):
        one = fit.cross_validation_log_predictive_density["one_factor"][index]
        two = fit.cross_validation_log_predictive_density["two_factor"][index]
        pointwise_rows.append({
            "task_uuid": task_id,
            "canonical_family": data.task_families[index],
            "fold": int(fit.folds[index]) + 1,
            "observed_items": int(np.sum(data.observation_task_index == index)),
            "one_factor_log_predictive_density": one,
            "two_factor_log_predictive_density": two,
            "two_minus_one": two - one,
            "output_kind": "heldout_posterior_predictive_estimate",
        })
    stable_csv_dump(pointwise_rows, list(pointwise_rows[0]), output_directory / "cross_validation_pointwise.csv")

    diagnostic_rows = [
        {"model": name, **fit.diagnostics[name], "fit_scope": "full_data", "output_kind": "posterior_diagnostic"}
        for name in MODEL_NAMES
    ]
    stable_csv_dump(diagnostic_rows, list(diagnostic_rows[0]), output_directory / "posterior_diagnostics.csv")

    posterior_arrays = {
        "binary_task_difficulty": binary_difficulty,
        "binary_item_ability": binary_ability,
        "binary_item_difficulty_limit_10pct": binary_limit,
        "continuous_task_difficulty": continuous_difficulty,
        "continuous_item_ability": continuous_ability,
        "continuous_item_precision": precision,
        "continuous_item_consistency": consistency,
        "one_factor_loading": one_loading,
        "two_factor_loading": two_loading,
        "two_factor_loading_contrast": contrast,
    }
    _deterministic_npz(output_directory / "posterior_samples.npz", posterior_arrays)
    _deterministic_npz(
        output_directory / "cross_validation_log_predictive_density.npz",
        {
            "fold": fit.folds,
            "one_factor": fit.cross_validation_log_predictive_density["one_factor"],
            "two_factor": fit.cross_validation_log_predictive_density["two_factor"],
        },
    )

    all_diagnostics_pass = bool(
        all(row["passed"] for row in fit.diagnostics.values())
        and all(row["passed"] for row in fit.cross_validation_diagnostics)
    )
    report = {
        "artifact_id": "ml10c_sparse_bayesian_irt_report_v1",
        "status": "complete_internal_posterior_estimate" if all_diagnostics_pass else "retained_internal_diagnostic_failure",
        "panel_tasks": 96,
        "items": 23,
        "observed_response_cells": len(data.binary),
        "missing_response_cells": 96 * 23 - len(data.binary),
        "primary_model": "fixed_discrimination_sparse_hierarchical_rasch",
        "graded_corroboration": "fixed_discrimination_sparse_hierarchical_beta",
        "dimensionality_comparison": comparison,
        "pyscf_second_axis_loading_contrast_probability_gt_one": contrast_probability,
        "named_single_reference_multireference_hypothesis_supported": hypothesis_supported,
        "marker_constraint_caveat": True,
        "difficulty_shift": shift_metrics,
        "ml9d_target_regated": False,
        "all_sampler_diagnostics_pass": all_diagnostics_pass,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "public_or_dashboard_placement": False,
        "outputs_are_estimates": True,
    }
    stable_json_dump(report, output_directory / "report.json")
    environment = {
        "artifact_id": "ml10c_sparse_bayesian_irt_environment_v1",
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "pymc": __import__("pymc").__version__,
        "arviz": __import__("arviz").__version__,
        "numpy": np.__version__,
        "preregistration_sha256": sha256_file(preregistration_path),
        "chain_seeds": preregistration["ml10c_bayesian_irt"]["sampling"]["fixed_chain_seeds"],
        "thread_limits": {name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
        "deterministic_posterior_arrays_retained": True,
    }
    stable_json_dump(environment, output_directory / "environment.json")
    report_lines = [
        "# ML-10C sparse Bayesian inverted-IRT report",
        "",
        "Status: internal posterior estimates; no public or dashboard placement.",
        "",
        "The primary fixed-discrimination Rasch model contains 18 complete ladder items and five sparse PySCF items. Missing PySCF cells are excluded from both binary and graded likelihoods.",
        "",
        "The exploratory one- and two-factor models use observed-cell, per-item standardized logit quality. Exact five-fold refits keep canonical task families intact and marginalize held-out task scores over each observed item subset.",
        "",
        f"All full-data and cross-validation sampler health gates pass: {str(all_diagnostics_pass).lower()}.",
        "",
        f"The exact-CV two-minus-one-factor ELPD delta is {comparison['delta_elpd_two_minus_one']:.10g} with standard error {comparison['delta_standard_error']:.10g}; decision: {comparison['decision']}.",
        "",
        f"The PySCF-to-ladder second-axis loading contrast probability is {contrast_probability:.10g}. The named single-reference/multireference hypothesis is supported: {str(hypothesis_supported).lower()}. This interpretation is conditional on the frozen marker constraints.",
        "",
        f"Difficulty concordance with ML-9C is Pearson {shift_metrics['pearson_posterior_mean_concordance']:.10g}, Spearman {shift_metrics['spearman_posterior_mean_concordance']:.10g}; median absolute posterior-mean shift is {shift_metrics['median_absolute_posterior_mean_shift']:.10g}.",
        "",
        "ML-9D is not re-gated. No stored label, task selection, design-based ratio, or solver record is changed.",
    ]
    (output_directory / "REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")

    current = {path.name for path in output_directory.iterdir() if path.is_file()}
    _require(current == set(REQUIRED_FILES) - {"artifact_manifest.json"}, "ML-10C output contract changed")
    files = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(output_directory.iterdir())
        if path.is_file()
    ]
    manifest = {
        "artifact_id": "ml10c_sparse_bayesian_irt_manifest_v1",
        "status": report["status"],
        "files": files,
        "all_sampler_diagnostics_pass": all_diagnostics_pass,
        "promotion_eligible": all_diagnostics_pass,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "free_item_discrimination": False,
        "public_or_dashboard_placement": False,
        "outputs_are_estimates": True,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return report


def run_sparse_finalization(
    root: Path,
    preregistration_path: Path,
    output_directory: Path,
    *,
    tune: int | None = None,
    draws: int | None = None,
) -> dict[str, Any]:
    data = prepare_sparse_irt_data(root, preregistration_path)
    preregistration = __import__("json").loads(preregistration_path.read_text(encoding="utf-8"))
    fit = fit_sparse_models(data, preregistration, tune=tune, draws=draws)
    return write_sparse_artifacts(root, preregistration_path, output_directory, data, fit)
