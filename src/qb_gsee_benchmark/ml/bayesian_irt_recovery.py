"""Post-diagnostic, identified-factor recovery for ML-9C."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from scipy.special import logsumexp

from qb_gsee_benchmark.ml.bayesian_irt_run import (
    IPIE_FACTOR_ANCHOR,
    IrtData,
    _deterministic_npz,
    _diagnostics,
    _posterior_array,
    _response_model,
    _sample_model,
    _shortest_hdi,
    prepare_irt_data,
)
from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)


CPU_FACTOR_ANCHOR = "g50_bond_dimension_2048"
RECOVERY_MODEL_NAMES = ("continuous_beta", "one_factor", "two_factor")


@dataclass(frozen=True)
class FactorTransform:
    mean: np.ndarray
    scale: np.ndarray
    standardized: np.ndarray


@dataclass(frozen=True)
class RecoveryFit:
    continuous_trace: Any
    factor_traces: dict[str, Any]
    diagnostics: dict[str, dict[str, Any]]
    full_transform: FactorTransform
    folds: np.ndarray
    cross_validation_diagnostics: list[dict[str, Any]]
    cross_validation_log_predictive_density: dict[str, np.ndarray]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_specification(
    root: Path, specification: Mapping[str, Any], label: str
) -> Path:
    path = root / str(specification["path"])
    _require(path.is_file(), f"missing ML-9C recovery input {label}: {path}")
    _require(
        sha256_file(path) == str(specification["sha256"]),
        f"changed ML-9C recovery input {label}: {path}",
    )
    return path


def verify_recovery_preregistration(
    root: Path, recovery_preregistration_path: Path
) -> dict[str, Any]:
    preregistration = _read_json(recovery_preregistration_path)
    _require(
        preregistration.get("artifact_id")
        == "ml9c_identified_recovery_preregistration_v2",
        "wrong ML-9C recovery preregistration",
    )
    _require(
        preregistration.get("frozen_before_recovery_fit") is True,
        "ML-9C recovery was not frozen before fitting",
    )
    order = preregistration["order"]
    for path_key, hash_key in (
        ("ml_goals_external_path", "ml_goals_sha256"),
        ("pi_literature_memo_external_path", "pi_literature_memo_sha256"),
    ):
        path = Path(str(order[path_key]))
        _require(path.is_file(), f"missing ML-9C recovery order source: {path}")
        _require(
            sha256_file(path) == str(order[hash_key]),
            f"changed ML-9C recovery order source: {path}",
        )
    _verify_specification(
        root, preregistration["original_preregistration"], "original_preregistration"
    )
    for section in ("retained_v1_evidence", "unchanged_inputs"):
        for label, specification in sorted(preregistration[section].items()):
            if isinstance(specification, dict) and "path" in specification:
                _verify_specification(root, specification, f"{section}.{label}")
    _require(
        preregistration["retained_v1_evidence"]["diagnostics"]["binary_rasch"]["passed"]
        is True,
        "retained binary Rasch source is not healthy",
    )
    return preregistration


def factor_transform(
    values: np.ndarray, training_indices: np.ndarray
) -> FactorTransform:
    """Fit the frozen item-wise affine transform on training tasks only."""

    training = np.asarray(values[training_indices], dtype=float)
    mean = np.mean(training, axis=0)
    scale = np.std(training, axis=0, ddof=1)
    scale = np.where(np.isfinite(scale) & (scale > 0.0), scale, 1.0)
    standardized = (np.asarray(values, dtype=float) - mean) / scale
    _require(bool(np.isfinite(standardized).all()), "non-finite factor transform")
    return FactorTransform(mean=mean, scale=scale, standardized=standardized)


def identified_factor_model(
    values: np.ndarray,
    variant_ids: tuple[str, ...],
    task_ids: tuple[str, ...],
    factors: int,
):
    """Construct the frozen positive pure-marker factor model."""

    import pymc as pm
    import pytensor.tensor as pt

    _require(factors in {1, 2}, "factor count must be one or two")
    _require(values.shape == (len(task_ids), len(variant_ids)), "factor shape changed")
    cpu_anchor = variant_ids.index(CPU_FACTOR_ANCHOR)
    ipie_anchor = variant_ids.index(IPIE_FACTOR_ANCHOR)
    coords: dict[str, Any] = {"task": task_ids, "variant": variant_ids}
    if factors == 2:
        coords["factor"] = ("cpu_axis", "ipie_axis")
    with pm.Model(coords=coords) as model:
        item_intercept = pm.Normal("item_intercept", 0.0, 0.25, dims="variant")
        item_residual_sd = pm.HalfNormal("item_residual_sd", 0.75, dims="variant")
        cpu_anchor_loading = pm.HalfNormal("cpu_anchor_loading", 1.0)
        if factors == 1:
            free_indices = np.asarray(
                [index for index in range(len(variant_ids)) if index != cpu_anchor],
                dtype=int,
            )
            free_loadings = pm.Normal(
                "free_loadings", 0.0, 0.75, shape=len(free_indices)
            )
            loading = pt.zeros(len(variant_ids))
            loading = pt.set_subtensor(loading[cpu_anchor], cpu_anchor_loading)
            loading = pt.set_subtensor(loading[free_indices], free_loadings)
            factor_loading = pm.Deterministic("factor_loading", loading, dims="variant")
            covariance = pt.outer(factor_loading, factor_loading)
        else:
            ipie_anchor_loading = pm.HalfNormal("ipie_anchor_loading", 1.0)
            free_indices = np.asarray(
                [
                    index
                    for index in range(len(variant_ids))
                    if index not in {cpu_anchor, ipie_anchor}
                ],
                dtype=int,
            )
            free_loadings = pm.Normal(
                "free_loadings", 0.0, 0.75, shape=(len(free_indices), 2)
            )
            loading = pt.zeros((len(variant_ids), 2))
            loading = pt.set_subtensor(loading[cpu_anchor, 0], cpu_anchor_loading)
            loading = pt.set_subtensor(loading[cpu_anchor, 1], 0.0)
            loading = pt.set_subtensor(loading[ipie_anchor, 0], 0.0)
            loading = pt.set_subtensor(loading[ipie_anchor, 1], ipie_anchor_loading)
            loading = pt.set_subtensor(loading[free_indices, :], free_loadings)
            factor_loading = pm.Deterministic(
                "factor_loading", loading, dims=("variant", "factor")
            )
            covariance = factor_loading @ factor_loading.T
        covariance = covariance + pt.diag(item_residual_sd**2)
        pm.MvNormal(
            "response",
            mu=item_intercept,
            cov=covariance,
            observed=values,
            dims=("task", "variant"),
        )
    return model


def canonical_family_folds(data: IrtData, fold_count: int, seed: int) -> np.ndarray:
    """Assign intact canonical families to deterministic balanced folds."""

    members: dict[str, list[int]] = {}
    for index, family in enumerate(data.task_families):
        members.setdefault(family, []).append(index)

    def tie_break(family: str) -> str:
        return hashlib.sha256(f"{seed}:{family}".encode()).hexdigest()

    ordered = sorted(
        members, key=lambda family: (-len(members[family]), tie_break(family))
    )
    loads = [0] * fold_count
    family_fold: dict[str, int] = {}
    for family in ordered:
        fold = min(range(fold_count), key=lambda index: (loads[index], index))
        family_fold[family] = fold
        loads[fold] += len(members[family])
    folds = np.asarray(
        [family_fold[family] for family in data.task_families], dtype=int
    )
    _require(set(folds) == set(range(fold_count)), "empty ML-9C recovery fold")
    for family in members:
        positions = [
            index for index, value in enumerate(data.task_families) if value == family
        ]
        _require(len(set(folds[positions])) == 1, "canonical family split across folds")
    _require(
        max(loads) - min(loads) <= max(map(len, members.values())),
        "fold imbalance changed",
    )
    return folds


def posterior_log_predictive_density(idata, heldout: np.ndarray) -> np.ndarray:
    """Integrate held-out multivariate-normal density over posterior draws."""

    intercept = _posterior_array(idata, "item_intercept").reshape(-1, heldout.shape[1])
    residual = _posterior_array(idata, "item_residual_sd").reshape(-1, heldout.shape[1])
    loading = _posterior_array(idata, "factor_loading")
    if loading.ndim == 3:
        loading = loading.reshape(-1, heldout.shape[1], 1)
    else:
        loading = loading.reshape(-1, heldout.shape[1], loading.shape[-1])
    _require(
        len(intercept) == len(residual) == len(loading),
        "posterior draw counts changed",
    )
    draw_count = len(intercept)
    log_density = np.empty((draw_count, len(heldout)), dtype=float)
    constant = heldout.shape[1] * math.log(2.0 * math.pi)
    block_size = 256
    for start in range(0, draw_count, block_size):
        stop = min(start + block_size, draw_count)
        load = loading[start:stop]
        covariance = load @ np.swapaxes(load, -1, -2)
        diagonal = np.arange(heldout.shape[1])
        covariance[:, diagonal, diagonal] += residual[start:stop] ** 2
        sign, log_determinant = np.linalg.slogdet(covariance)
        _require(bool(np.all(sign > 0)), "non-positive factor covariance")
        inverse = np.linalg.inv(covariance)
        difference = heldout[None, :, :] - intercept[start:stop, None, :]
        quadratic = np.einsum(
            "sni,sij,snj->sn", difference, inverse, difference, optimize=True
        )
        log_density[start:stop] = -0.5 * (
            constant + log_determinant[:, None] + quadratic
        )
    integrated = logsumexp(log_density, axis=0) - math.log(draw_count)
    _require(bool(np.isfinite(integrated).all()), "non-finite held-out density")
    return integrated


def _factor_diagnostics(idata) -> dict[str, Any]:
    return _diagnostics(idata, ["factor_loading", "item_intercept", "item_residual_sd"])


def fit_recovery_models(
    data: IrtData, recovery_preregistration: dict[str, Any]
) -> RecoveryFit:
    """Fit the frozen recovery and exact blocked cross-validation models."""

    continuous_sampling = recovery_preregistration["continuous_beta"]["sampling"]
    print("ML9C_RECOVERY_FIT_START model=continuous_beta", flush=True)
    continuous_trace = _sample_model(
        _response_model(data, continuous=True),
        tune=int(continuous_sampling["tune"]),
        draws=int(continuous_sampling["draws"]),
        target_accept=float(continuous_sampling["target_accept"]),
        seeds=list(map(int, continuous_sampling["chain_seeds"])),
        retain_log_likelihood=False,
    )
    diagnostics = {
        "continuous_beta": _diagnostics(
            continuous_trace,
            [
                "task_difficulty",
                "variant_ability",
                "variant_precision",
                "variant_consistency",
            ],
        )
    }
    print(
        f"ML9C_RECOVERY_FIT_DONE model=continuous_beta pass={diagnostics['continuous_beta']['passed']}",
        flush=True,
    )

    full_transform = factor_transform(
        data.logit_quality, np.arange(len(data.task_ids), dtype=int)
    )
    factor_sampling = recovery_preregistration["identified_factor_models"][
        "full_data_sampling"
    ]
    factor_traces: dict[str, Any] = {}
    for factors, name in ((1, "one_factor"), (2, "two_factor")):
        print(f"ML9C_RECOVERY_FIT_START model={name}", flush=True)
        model = identified_factor_model(
            full_transform.standardized,
            data.variant_ids,
            data.task_ids,
            factors,
        )
        trace = _sample_model(
            model,
            tune=int(factor_sampling["tune"]),
            draws=int(factor_sampling["draws"]),
            target_accept=float(factor_sampling["target_accept"]),
            seeds=list(map(int, factor_sampling["chain_seeds"])),
            retain_log_likelihood=False,
        )
        factor_traces[name] = trace
        diagnostics[name] = _factor_diagnostics(trace)
        print(
            f"ML9C_RECOVERY_FIT_DONE model={name} pass={diagnostics[name]['passed']}",
            flush=True,
        )

    cross_validation = recovery_preregistration["exact_cross_validation"]
    fold_count = int(cross_validation["fold_count"])
    folds = canonical_family_folds(data, fold_count, int(cross_validation["fold_seed"]))
    cv_sampling = cross_validation["fit_sampling"]
    pointwise = {
        "one_factor": np.full(len(data.task_ids), np.nan, dtype=float),
        "two_factor": np.full(len(data.task_ids), np.nan, dtype=float),
    }
    cv_diagnostics: list[dict[str, Any]] = []
    for factors, name in ((1, "one_factor"), (2, "two_factor")):
        for fold in range(fold_count):
            test_indices = np.flatnonzero(folds == fold)
            train_indices = np.flatnonzero(folds != fold)
            transform = factor_transform(data.logit_quality, train_indices)
            train_ids = tuple(data.task_ids[index] for index in train_indices)
            model = identified_factor_model(
                transform.standardized[train_indices],
                data.variant_ids,
                train_ids,
                factors,
            )
            seed_base = 2026081000 + 100 * factors + 10 * (fold + 1)
            seeds = [seed_base + index for index in range(1, 5)]
            print(f"ML9C_RECOVERY_CV_START model={name} fold={fold + 1}", flush=True)
            trace = _sample_model(
                model,
                tune=int(cv_sampling["tune"]),
                draws=int(cv_sampling["draws"]),
                target_accept=float(cv_sampling["target_accept"]),
                seeds=seeds,
                retain_log_likelihood=False,
            )
            diagnostic = _factor_diagnostics(trace)
            pointwise[name][test_indices] = posterior_log_predictive_density(
                trace, transform.standardized[test_indices]
            )
            cv_diagnostics.append(
                {
                    "model": name,
                    "fold": fold + 1,
                    "training_tasks": len(train_indices),
                    "heldout_tasks": len(test_indices),
                    **diagnostic,
                    "chain_seeds": ";".join(map(str, seeds)),
                    "output_kind": "posterior_diagnostic",
                }
            )
            print(
                f"ML9C_RECOVERY_CV_DONE model={name} fold={fold + 1} pass={diagnostic['passed']}",
                flush=True,
            )
    _require(
        all(np.isfinite(values).all() for values in pointwise.values()),
        "incomplete cross-validation predictions",
    )
    return RecoveryFit(
        continuous_trace=continuous_trace,
        factor_traces=factor_traces,
        diagnostics=diagnostics,
        full_transform=full_transform,
        folds=folds,
        cross_validation_diagnostics=cv_diagnostics,
        cross_validation_log_predictive_density=pointwise,
    )


def _summary(samples: np.ndarray, index: int) -> dict[str, float]:
    values = np.asarray(samples[..., index], dtype=float).reshape(-1)
    low, high = _shortest_hdi(values)
    return {
        "mean": float(np.mean(values)),
        "sd": float(np.std(values, ddof=1)),
        "hdi_2_5pct": low,
        "hdi_97_5pct": high,
    }


def _load_retained_arrays(
    root: Path, preregistration: Mapping[str, Any]
) -> dict[str, np.ndarray]:
    specification = preregistration["retained_v1_evidence"]["posterior_samples"]
    path = _verify_specification(root, specification, "retained_posterior_samples")
    required = set(preregistration["binary_rasch"]["required_arrays"])
    with np.load(path) as archive:
        _require(required <= set(archive.files), "retained binary arrays missing")
        return {name: np.array(archive[name], copy=True) for name in required}


def _continuous_predictive_rows(data: IrtData, trace) -> list[dict[str, Any]]:
    rng = np.random.default_rng(2026080199)
    task_index = np.repeat(np.arange(len(data.task_ids)), len(data.variant_ids))
    variant_index = np.tile(np.arange(len(data.variant_ids)), len(data.task_ids))
    family_index = data.variant_solver_family_index[variant_index]
    ability = _posterior_array(trace, "variant_ability")
    difficulty = _posterior_array(trace, "task_difficulty")
    testlet = _posterior_array(trace, "testlet_effect")
    precision = _posterior_array(trace, "variant_precision")
    mean = 1.0 / (
        1.0
        + np.exp(
            -(
                ability[..., variant_index]
                - difficulty[..., task_index]
                + testlet[..., task_index, family_index]
            )
        )
    )
    predictive = rng.beta(
        mean * precision[..., variant_index],
        (1.0 - mean) * precision[..., variant_index],
    )
    rows = []
    for family_position, family in enumerate(data.solver_families):
        mask = family_index == family_position
        values = predictive[..., mask].reshape(-1)
        rows.append(
            {
                "track": "continuous_quality",
                "scope": "solver_family",
                "scope_id": family,
                "statistic": "mean",
                "observed": float(np.mean(data.quality.reshape(-1)[mask])),
                "predictive_mean": float(np.mean(values)),
                "predictive_q10": float(np.quantile(values, 0.1)),
                "predictive_q50": float(np.quantile(values, 0.5)),
                "predictive_q90": float(np.quantile(values, 0.9)),
                "output_kind": "posterior_predictive_check",
            }
        )
    return rows


def _comparison(fit: RecoveryFit) -> dict[str, Any]:
    one = fit.cross_validation_log_predictive_density["one_factor"]
    two = fit.cross_validation_log_predictive_density["two_factor"]
    differences = two - one
    delta = float(np.sum(differences))
    standard_error = float(np.sqrt(len(differences) * np.var(differences, ddof=1)))
    if delta > standard_error:
        decision = "favor_two_factors"
    elif -delta > standard_error:
        decision = "favor_one_factor"
    else:
        decision = "equivocal"
    return {
        "delta_elpd_two_minus_one": delta,
        "delta_standard_error": standard_error,
        "decision": decision,
        "method": "exact_five_fold_canonical_family_blocked",
        "reliable": bool(
            all(row["passed"] for row in fit.cross_validation_diagnostics)
        ),
    }


def write_recovery_artifacts(
    root: Path,
    recovery_preregistration_path: Path,
    output_directory: Path,
    data: IrtData,
    fit: RecoveryFit,
) -> dict[str, Any]:
    preregistration = verify_recovery_preregistration(
        root, recovery_preregistration_path
    )
    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)
    retained_root = root / "analysis/ml9_bayesian_irt/raw_runs/run_1"
    shutil.copyfile(
        retained_root / "response_matrix.csv", output_directory / "response_matrix.csv"
    )
    shutil.copyfile(
        retained_root / "difficulty_handoff_ml9d.csv",
        output_directory / "difficulty_handoff_ml9d.csv",
    )
    _require(
        sha256_file(output_directory / "difficulty_handoff_ml9d.csv")
        == preregistration["binary_rasch"]["required_handoff_sha256"],
        "binary ML-9D handoff changed",
    )

    retained = _load_retained_arrays(root, preregistration)
    binary_difficulty = retained["binary_task_difficulty"]
    binary_ability = retained["binary_variant_ability"]
    binary_limit = retained["binary_variant_difficulty_limit_10pct"]
    continuous_difficulty = _posterior_array(fit.continuous_trace, "task_difficulty")
    continuous_ability = _posterior_array(fit.continuous_trace, "variant_ability")
    continuous_precision = _posterior_array(fit.continuous_trace, "variant_precision")
    continuous_consistency = _posterior_array(
        fit.continuous_trace, "variant_consistency"
    )

    task_rows = []
    for index, task_id in enumerate(data.task_ids):
        row: dict[str, Any] = {
            "task_uuid": task_id,
            "canonical_family": data.task_families[index],
            "primary_hardness_track": "binary_rasch",
            "output_kind": "posterior_estimate",
        }
        for prefix, samples in (
            ("binary_difficulty", binary_difficulty),
            ("continuous_difficulty", continuous_difficulty),
        ):
            row.update(
                {
                    f"{prefix}_{name}": value
                    for name, value in _summary(samples, index).items()
                }
            )
        task_rows.append(row)
    stable_csv_dump(
        task_rows, list(task_rows[0]), output_directory / "task_difficulty.csv"
    )

    variant_rows = []
    for index, variant_id in enumerate(data.variant_ids):
        row = {
            "solver_family_id": data.solver_families[
                data.variant_solver_family_index[index]
            ],
            "solver_variant_id": variant_id,
            "solver_short_name": data.variant_names[index],
            "difficulty_limit_probability": 0.1,
            "output_kind": "posterior_estimate",
        }
        for prefix, samples in (
            ("binary_ability", binary_ability),
            ("continuous_ability", continuous_ability),
            ("consistency", continuous_consistency),
            ("difficulty_limit_10pct", binary_limit),
        ):
            row.update(
                {
                    f"{prefix}_{name}": value
                    for name, value in _summary(samples, index).items()
                }
            )
        variant_rows.append(row)
    stable_csv_dump(
        variant_rows, list(variant_rows[0]), output_directory / "variant_parameters.csv"
    )

    preprocessing_rows = [
        {
            "solver_family_id": data.solver_families[
                data.variant_solver_family_index[index]
            ],
            "solver_variant_id": variant_id,
            "training_scope": "full_96_task_panel",
            "logit_quality_mean": fit.full_transform.mean[index],
            "logit_quality_sample_sd": fit.full_transform.scale[index],
            "output_kind": "factor_preprocessing_parameter",
        }
        for index, variant_id in enumerate(data.variant_ids)
    ]
    stable_csv_dump(
        preprocessing_rows,
        list(preprocessing_rows[0]),
        output_directory / "factor_preprocessing.csv",
    )

    one_loading = _posterior_array(fit.factor_traces["one_factor"], "factor_loading")
    two_loading = _posterior_array(fit.factor_traces["two_factor"], "factor_loading")
    loading_rows = []
    for index, variant_id in enumerate(data.variant_ids):
        for model, factor, samples in (
            ("one_factor", "cpu_axis", one_loading),
            ("two_factor", "cpu_axis", two_loading[..., 0]),
            ("two_factor", "ipie_axis", two_loading[..., 1]),
        ):
            loading_rows.append(
                {
                    "model": model,
                    "factor": factor,
                    "solver_family_id": data.solver_families[
                        data.variant_solver_family_index[index]
                    ],
                    "solver_variant_id": variant_id,
                    **_summary(samples, index),
                    "output_kind": "posterior_estimate_exploratory",
                }
            )
    stable_csv_dump(
        loading_rows, list(loading_rows[0]), output_directory / "factor_loadings.csv"
    )

    comparison = _comparison(fit)
    ipie_index = data.variant_ids.index(IPIE_FACTOR_ANCHOR)
    cpu_indices = np.asarray(
        [index for index in range(len(data.variant_ids)) if index != ipie_index]
    )
    contrast = np.abs(two_loading[..., ipie_index, 1]) / np.median(
        np.abs(two_loading[..., cpu_indices, 1]), axis=-1
    )
    contrast_probability = float(np.mean(contrast > 1.0))
    hypothesis_supported = bool(
        comparison["decision"] == "favor_two_factors"
        and comparison["reliable"]
        and contrast_probability >= 0.95
    )
    dimensionality_rows = []
    for name in ("one_factor", "two_factor"):
        values = fit.cross_validation_log_predictive_density[name]
        dimensionality_rows.append(
            {
                "model": name,
                "elpd_exact_5fold": float(np.sum(values)),
                "se": float(np.sqrt(len(values) * np.var(values, ddof=1))),
                "pointwise_unit": "task",
                "canonical_family_blocked": True,
                "output_kind": "posterior_estimate_exploratory",
                **comparison,
                "ipie_axis_loading_contrast_probability_gt_one": contrast_probability,
                "marker_constraint_caveat": True,
                "named_hypothesis_supported": hypothesis_supported,
            }
        )
    stable_csv_dump(
        dimensionality_rows,
        list(dimensionality_rows[0]),
        output_directory / "dimensionality_comparison.csv",
    )

    fold_rows = [
        {
            "task_uuid": task_id,
            "canonical_family": data.task_families[index],
            "fold": int(fit.folds[index]) + 1,
            "output_kind": "cross_validation_assignment",
        }
        for index, task_id in enumerate(data.task_ids)
    ]
    stable_csv_dump(
        fold_rows, list(fold_rows[0]), output_directory / "cross_validation_folds.csv"
    )
    stable_csv_dump(
        fit.cross_validation_diagnostics,
        list(fit.cross_validation_diagnostics[0]),
        output_directory / "cross_validation_diagnostics.csv",
    )
    pointwise_rows = [
        {
            "task_uuid": task_id,
            "canonical_family": data.task_families[index],
            "fold": int(fit.folds[index]) + 1,
            "one_factor_log_predictive_density": fit.cross_validation_log_predictive_density[
                "one_factor"
            ][
                index
            ],
            "two_factor_log_predictive_density": fit.cross_validation_log_predictive_density[
                "two_factor"
            ][
                index
            ],
            "two_minus_one": fit.cross_validation_log_predictive_density["two_factor"][
                index
            ]
            - fit.cross_validation_log_predictive_density["one_factor"][index],
            "output_kind": "heldout_posterior_predictive_estimate",
        }
        for index, task_id in enumerate(data.task_ids)
    ]
    stable_csv_dump(
        pointwise_rows,
        list(pointwise_rows[0]),
        output_directory / "cross_validation_pointwise.csv",
    )

    binary_diagnostic = preregistration["retained_v1_evidence"]["diagnostics"][
        "binary_rasch"
    ]
    diagnostic_rows = [
        {
            "model": "binary_rasch",
            **binary_diagnostic,
            "source": "retained_v1_healthy_posterior",
            "output_kind": "posterior_diagnostic",
        }
    ]
    for name in RECOVERY_MODEL_NAMES:
        diagnostic_rows.append(
            {
                "model": name,
                **fit.diagnostics[name],
                "source": "identified_recovery_v2",
                "output_kind": "posterior_diagnostic",
            }
        )
    stable_csv_dump(
        diagnostic_rows,
        list(diagnostic_rows[0]),
        output_directory / "posterior_diagnostics.csv",
    )

    retained_predictive = pd.read_csv(retained_root / "posterior_predictive_checks.csv")
    predictive_rows = retained_predictive.loc[
        retained_predictive["track"].eq("binary")
    ].to_dict(orient="records")
    predictive_rows.extend(_continuous_predictive_rows(data, fit.continuous_trace))
    stable_csv_dump(
        predictive_rows,
        list(predictive_rows[0]),
        output_directory / "posterior_predictive_checks.csv",
    )

    posterior_arrays = {
        **retained,
        "continuous_task_difficulty": continuous_difficulty,
        "continuous_variant_ability": continuous_ability,
        "continuous_variant_consistency": continuous_consistency,
        "continuous_variant_precision": continuous_precision,
        "one_factor_loading": one_loading,
        "two_factor_loading": two_loading,
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

    all_recovery_diagnostics_pass = bool(
        all(row["passed"] for row in fit.diagnostics.values())
        and all(row["passed"] for row in fit.cross_validation_diagnostics)
    )
    report = {
        "artifact_id": "ml9c_identified_recovery_report_v2",
        "status": (
            "complete_internal_posterior_estimate"
            if all_recovery_diagnostics_pass
            else "retained_internal_recovery_diagnostic_failure"
        ),
        "panel_tasks": len(data.task_ids),
        "solver_variants": len(data.variant_ids),
        "response_cells": int(data.binary.size),
        "primary_hardness_track": "binary_rasch_retained_v1_unchanged",
        "binary_handoff_sha256": sha256_file(
            output_directory / "difficulty_handoff_ml9d.csv"
        ),
        "continuous_model_changed": False,
        "factor_identification": "positive_pure_markers_on_standardized_item_responses",
        "dimensionality_comparison": comparison,
        "ipie_axis_loading_contrast_probability_gt_one": contrast_probability,
        "named_ipie_axis_hypothesis_supported": hypothesis_supported,
        "all_recovery_diagnostics_pass": all_recovery_diagnostics_pass,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "public_or_dashboard_placement": False,
        "outputs_are_estimates": True,
    }
    stable_json_dump(report, output_directory / "report.json")
    environment = {
        "artifact_id": "ml9c_identified_recovery_environment_v2",
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "pymc": __import__("pymc").__version__,
        "arviz": __import__("arviz").__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "recovery_preregistration_sha256": sha256_file(recovery_preregistration_path),
        "retained_v1_identity_sha256": preregistration["retained_v1_evidence"][
            "two_run_identity"
        ]["sha256"],
        "thread_limits": {
            name: os.environ.get(name)
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "continuous_chain_seeds": preregistration["continuous_beta"]["sampling"][
            "chain_seeds"
        ],
        "factor_chain_seeds": preregistration["identified_factor_models"][
            "full_data_sampling"
        ]["chain_seeds"],
        "deterministic_posterior_arrays_retained": True,
    }
    stable_json_dump(environment, output_directory / "environment.json")

    report_lines = [
        "# ML-9C identified Bayesian recovery report",
        "",
        "Status: internal posterior estimates; no public or dashboard placement.",
        "",
        "The primary binary Rasch hardness posterior and ML-9D handoff are carried "
        "forward byte-for-byte from the healthy retained v1 fit. The unchanged beta "
        "model is refit with additional retained draws.",
        "",
        "The exploratory factor models use standardized item responses and positive "
        "pure markers to identify the CPU and iPIE axes. Model comparison uses exact "
        "five-fold refits blocked by canonical task family.",
        "",
        f"All recovery sampler health gates pass: {str(all_recovery_diagnostics_pass).lower()}.",
        "",
        f"The two-minus-one-factor exact-CV ELPD delta is "
        f"{comparison['delta_elpd_two_minus_one']:.10g} with standard error "
        f"{comparison['delta_standard_error']:.10g}; decision: {comparison['decision']}.",
        "",
        f"The marker-aware iPIE-axis loading contrast probability is "
        f"{contrast_probability:.10g}. The named hypothesis is supported: "
        f"{str(hypothesis_supported).lower()}. This interpretation is conditional on "
        "the frozen pure-marker identification.",
        "",
        "Every scientific value is an internal estimate. No stored label, task "
        "selection, design-based ratio, or solver record is changed.",
    ]
    (output_directory / "REPORT.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8", newline="\n"
    )

    required = set(preregistration["outputs"]["required_files"])
    current = {path.name for path in output_directory.iterdir() if path.is_file()}
    _require(
        current == required - {"artifact_manifest.json"},
        "recovery output contract changed",
    )
    files = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(output_directory.iterdir())
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    manifest = {
        "artifact_id": "ml9c_identified_recovery_manifest_v2",
        "status": report["status"],
        "files": files,
        "binary_handoff_unchanged": True,
        "all_recovery_diagnostics_pass": all_recovery_diagnostics_pass,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "free_item_discrimination": False,
        "public_or_dashboard_placement": False,
        "outputs_are_estimates": True,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    _require(all_recovery_diagnostics_pass, "ML-9C recovery diagnostics failed")
    return report


def run_recovery_finalization(
    root: Path, recovery_preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    preregistration = verify_recovery_preregistration(
        root, recovery_preregistration_path
    )
    original_path = root / preregistration["original_preregistration"]["path"]
    data = prepare_irt_data(root, original_path)
    fit = fit_recovery_models(data, preregistration)
    return write_recovery_artifacts(
        root, recovery_preregistration_path, output_directory, data, fit
    )
