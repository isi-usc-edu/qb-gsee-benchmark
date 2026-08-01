"""Frozen ML-9C Bayesian inverted-IRT execution and artifact construction."""

from __future__ import annotations

import io
import json
import math
import os
import platform
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)


DMRG_FACTOR_ANCHOR = "g50_bond_dimension_256"
IPIE_FACTOR_ANCHOR = "uhf_trial_512_walkers_1000_blocks"
MODEL_NAMES = ("binary_rasch", "continuous_beta", "one_factor", "two_factor")
DIFFICULTY_LIMIT_OFFSET = -math.log(0.10 / 0.90)


@dataclass(frozen=True)
class IrtData:
    task_ids: tuple[str, ...]
    task_families: tuple[str, ...]
    canonical_families: tuple[str, ...]
    variant_ids: tuple[str, ...]
    variant_names: tuple[str, ...]
    solver_families: tuple[str, ...]
    task_family_index: np.ndarray
    variant_solver_family_index: np.ndarray
    binary: np.ndarray
    clipped_residual: np.ndarray
    quality: np.ndarray
    logit_quality: np.ndarray


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_inputs(root: Path, preregistration: dict[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path = root / specification["path"]
        _require(path.is_file(), f"missing ML-9C input {name}: {path}")
        _require(
            sha256_file(path) == specification["sha256"],
            f"changed ML-9C input {name}: {path}",
        )
        paths[name] = path
    return paths


def prepare_irt_data(root: Path, preregistration_path: Path) -> IrtData:
    """Construct the frozen complete response matrices after preregistration."""

    preregistration = _read_json(preregistration_path)
    _require(
        preregistration["artifact_id"]
        == "ml9c_bayesian_inverted_irt_preregistration_v1",
        "wrong ML-9C preregistration",
    )
    paths = _verify_inputs(root, preregistration)

    panel = pd.read_csv(
        paths["panel_of_record"], usecols=["task_uuid", "canonical_family"]
    )
    panel = panel.astype({"task_uuid": str, "canonical_family": str}).sort_values(
        "task_uuid", kind="mergesort"
    )
    _require(len(panel) == 96 and panel["task_uuid"].is_unique, "panel changed")

    variants_payload = _read_json(paths["solver_variants"])
    variants = pd.DataFrame(variants_payload)[
        ["solver_family_id", "solver_variant_id", "solver_short_name"]
    ].astype(str)
    variants = variants.sort_values(
        ["solver_family_id", "solver_variant_id"], kind="mergesort"
    ).reset_index(drop=True)
    _require(len(variants) == 18, "variant census changed")
    _require(variants["solver_variant_id"].is_unique, "duplicate variant")

    observations = pd.read_csv(paths["normalized_observations"])
    required = {
        "task_uuid",
        "canonical_family",
        "solver_family_id",
        "solver_variant_id",
        "observed_outcome",
        "graded_residual",
    }
    _require(required <= set(observations), "response schema changed")
    observations = observations[list(sorted(required))].copy()
    for column in [
        "task_uuid",
        "canonical_family",
        "solver_family_id",
        "solver_variant_id",
    ]:
        observations[column] = observations[column].astype(str)
    observations = observations.sort_values(
        ["task_uuid", "solver_family_id", "solver_variant_id"], kind="mergesort"
    ).reset_index(drop=True)
    _require(len(observations) == 96 * 18, "response row count changed")
    _require(
        not observations.duplicated(["task_uuid", "solver_variant_id"]).any(),
        "duplicate task-variant response",
    )

    task_ids = tuple(panel["task_uuid"])
    task_family_by_id = dict(zip(panel["task_uuid"], panel["canonical_family"]))
    variant_ids = tuple(variants["solver_variant_id"])
    variant_name_by_id = dict(
        zip(variants["solver_variant_id"], variants["solver_short_name"])
    )
    variant_family_by_id = dict(
        zip(variants["solver_variant_id"], variants["solver_family_id"])
    )
    expected_pairs = {(task, variant) for task in task_ids for variant in variant_ids}
    observed_pairs = set(
        zip(observations["task_uuid"], observations["solver_variant_id"])
    )
    _require(observed_pairs == expected_pairs, "response grid changed")
    _require(
        all(
            row.canonical_family == task_family_by_id[row.task_uuid]
            for row in observations.itertuples()
        ),
        "task-family binding changed",
    )
    _require(
        all(
            row.solver_family_id == variant_family_by_id[row.solver_variant_id]
            for row in observations.itertuples()
        ),
        "variant-family binding changed",
    )

    task_index = {name: index for index, name in enumerate(task_ids)}
    variant_index = {name: index for index, name in enumerate(variant_ids)}
    binary = np.empty((len(task_ids), len(variant_ids)), dtype=np.int8)
    residual = np.empty_like(binary, dtype=np.float64)
    for row in observations.itertuples():
        task = task_index[row.task_uuid]
        variant = variant_index[row.solver_variant_id]
        binary[task, variant] = int(str(row.observed_outcome) == "success")
        value = pd.to_numeric(row.graded_residual, errors="coerce")
        residual[task, variant] = (
            float(np.clip(value, 0.0, 4.0)) if np.isfinite(value) else 4.0
        )

    quality = 1.0 / (1.0 + residual + 1.0e-6)
    _require(np.all((quality > 0.0) & (quality < 1.0)), "quality link left (0,1)")
    logit_quality = np.log(quality) - np.log1p(-quality)
    canonical_families = tuple(sorted(set(panel["canonical_family"])))
    solver_families = tuple(sorted(set(variants["solver_family_id"])))
    canonical_index = {name: index for index, name in enumerate(canonical_families)}
    solver_index = {name: index for index, name in enumerate(solver_families)}
    return IrtData(
        task_ids=task_ids,
        task_families=tuple(task_family_by_id[name] for name in task_ids),
        canonical_families=canonical_families,
        variant_ids=variant_ids,
        variant_names=tuple(variant_name_by_id[name] for name in variant_ids),
        solver_families=solver_families,
        task_family_index=np.asarray(
            [canonical_index[task_family_by_id[name]] for name in task_ids], dtype=int
        ),
        variant_solver_family_index=np.asarray(
            [solver_index[variant_family_by_id[name]] for name in variant_ids],
            dtype=int,
        ),
        binary=binary,
        clipped_residual=residual,
        quality=quality,
        logit_quality=logit_quality,
    )


def _response_model(data: IrtData, continuous: bool):
    import pymc as pm
    import pytensor.tensor as pt

    coords = {
        "task": data.task_ids,
        "variant": data.variant_ids,
        "solver_family": data.solver_families,
        "canonical_family": data.canonical_families,
        "cell": np.arange(data.binary.size),
    }
    task_index = np.repeat(np.arange(len(data.task_ids)), len(data.variant_ids))
    variant_index = np.tile(np.arange(len(data.variant_ids)), len(data.task_ids))
    cell_solver_family = data.variant_solver_family_index[variant_index]
    with pm.Model(coords=coords) as model:
        solver_family_ability_mean = pm.Normal(
            "solver_family_ability_mean", 0.0, 0.75, dims="solver_family"
        )
        solver_family_variant_sd = pm.HalfNormal(
            "solver_family_variant_sd", 0.5, dims="solver_family"
        )
        variant_ability_offset_raw = pm.Normal(
            "variant_ability_offset_raw", 0.0, 1.0, dims="variant"
        )
        variant_ability = pm.Deterministic(
            "variant_ability",
            solver_family_ability_mean[data.variant_solver_family_index]
            + variant_ability_offset_raw
            * solver_family_variant_sd[data.variant_solver_family_index],
            dims="variant",
        )

        canonical_family_difficulty_mean = pm.Normal(
            "canonical_family_difficulty_mean",
            0.0,
            0.5,
            dims="canonical_family",
        )
        task_sd = pm.HalfNormal("task_sd", 1.0)
        task_difficulty_offset_raw = pm.Normal(
            "task_difficulty_offset_raw", 0.0, 1.0, dims="task"
        )
        task_difficulty_uncentered = (
            canonical_family_difficulty_mean[data.task_family_index]
            + task_difficulty_offset_raw * task_sd
        )
        task_difficulty = pm.Deterministic(
            "task_difficulty",
            task_difficulty_uncentered - pt.mean(task_difficulty_uncentered),
            dims="task",
        )

        testlet_sd = pm.HalfNormal("testlet_sd", 0.5, dims="solver_family")
        testlet_raw = pm.Normal(
            "testlet_raw",
            0.0,
            1.0,
            dims=("task", "solver_family"),
        )
        testlet_scaled = testlet_raw * testlet_sd[None, :]
        testlet_effect = pm.Deterministic(
            "testlet_effect",
            testlet_scaled - pt.mean(testlet_scaled, axis=1, keepdims=True),
            dims=("task", "solver_family"),
        )
        linear_predictor = (
            variant_ability[variant_index]
            - task_difficulty[task_index]
            + testlet_effect[task_index, cell_solver_family]
        )

        if continuous:
            solver_family_log_precision_mean = pm.Normal(
                "solver_family_log_precision_mean",
                math.log(20.0),
                0.5,
                dims="solver_family",
            )
            solver_family_log_precision_sd = pm.HalfNormal(
                "solver_family_log_precision_sd", 0.35, dims="solver_family"
            )
            variant_log_precision_offset_raw = pm.Normal(
                "variant_log_precision_offset_raw", 0.0, 1.0, dims="variant"
            )
            variant_precision = pm.Deterministic(
                "variant_precision",
                pt.exp(
                    solver_family_log_precision_mean[data.variant_solver_family_index]
                    + variant_log_precision_offset_raw
                    * solver_family_log_precision_sd[data.variant_solver_family_index]
                ),
                dims="variant",
            )
            variant_consistency = pm.Deterministic(
                "variant_consistency",
                variant_precision / (variant_precision + 1.0),
                dims="variant",
            )
            mean = pm.math.sigmoid(linear_predictor)
            pm.Beta(
                "response",
                alpha=mean * variant_precision[variant_index],
                beta=(1.0 - mean) * variant_precision[variant_index],
                observed=data.quality.reshape(-1),
                dims="cell",
            )
        else:
            pm.Deterministic(
                "difficulty_limit_10pct",
                variant_ability + DIFFICULTY_LIMIT_OFFSET,
                dims="variant",
            )
            pm.Bernoulli(
                "response",
                logit_p=linear_predictor,
                observed=data.binary.reshape(-1),
                dims="cell",
            )
    return model


def _factor_model(data: IrtData, factors: int):
    import pymc as pm
    import pytensor.tensor as pt

    _require(factors in {1, 2}, "factor count must be one or two")
    dmrg_anchor = data.variant_ids.index(DMRG_FACTOR_ANCHOR)
    ipie_anchor = data.variant_ids.index(IPIE_FACTOR_ANCHOR)
    coords: dict[str, Any] = {"task": data.task_ids, "variant": data.variant_ids}
    if factors == 2:
        coords["factor"] = ("cpu_axis", "ipie_axis")
    with pm.Model(coords=coords) as model:
        item_intercept = pm.Normal("item_intercept", 0.0, 2.0, dims="variant")
        item_residual_sd = pm.HalfNormal("item_residual_sd", 1.0, dims="variant")
        factor1_anchor = pm.HalfNormal("factor1_anchor", 1.0)
        nonanchor1 = np.asarray(
            [i for i in range(len(data.variant_ids)) if i != dmrg_anchor], dtype=int
        )
        factor1_free = pm.Normal("factor1_free", 0.0, 0.75, shape=len(nonanchor1))
        loading1 = pt.zeros(len(data.variant_ids))
        loading1 = pt.set_subtensor(loading1[dmrg_anchor], factor1_anchor)
        loading1 = pt.set_subtensor(loading1[nonanchor1], factor1_free)
        if factors == 1:
            loading = pm.Deterministic("factor_loading", loading1, dims="variant")
            covariance = pt.outer(loading, loading) + pt.diag(item_residual_sd**2)
        else:
            factor2_anchor = pm.HalfNormal("factor2_anchor", 1.0)
            nonanchor2 = np.asarray(
                [
                    i
                    for i in range(len(data.variant_ids))
                    if i not in {dmrg_anchor, ipie_anchor}
                ],
                dtype=int,
            )
            factor2_free = pm.Normal("factor2_free", 0.0, 0.75, shape=len(nonanchor2))
            loading2 = pt.zeros(len(data.variant_ids))
            loading2 = pt.set_subtensor(loading2[ipie_anchor], factor2_anchor)
            loading2 = pt.set_subtensor(loading2[nonanchor2], factor2_free)
            loading = pm.Deterministic(
                "factor_loading",
                pt.stack([loading1, loading2], axis=1),
                dims=("variant", "factor"),
            )
            covariance = loading @ loading.T + pt.diag(item_residual_sd**2)
        pm.MvNormal(
            "response",
            mu=item_intercept,
            cov=covariance,
            observed=data.logit_quality,
            dims=("task", "variant"),
        )
    return model


def _sample_model(
    model,
    *,
    tune: int,
    draws: int,
    target_accept: float,
    seeds: list[int],
    retain_log_likelihood: bool,
):
    import pymc as pm

    with model:
        return pm.sample(
            tune=tune,
            draws=draws,
            chains=len(seeds),
            cores=1,
            random_seed=seeds,
            target_accept=target_accept,
            progressbar=False,
            compute_convergence_checks=True,
            discard_tuned_samples=True,
            idata_kwargs={"log_likelihood": retain_log_likelihood},
        )


def _diagnostics(idata, variables: Iterable[str]) -> dict[str, Any]:
    import arviz as az

    names = list(variables)
    rhat = np.asarray(az.rhat(idata, var_names=names).ds.to_array()).astype(float)
    bulk = np.asarray(
        az.ess(idata, var_names=names, method="bulk").ds.to_array()
    ).astype(float)
    tail = np.asarray(
        az.ess(idata, var_names=names, method="tail").ds.to_array()
    ).astype(float)
    divergences = int(np.asarray(idata.sample_stats["diverging"]).sum())
    maximum_rhat = float(np.nanmax(rhat))
    minimum_bulk_ess = float(np.nanmin(bulk))
    minimum_tail_ess = float(np.nanmin(tail))
    passed = (
        divergences == 0
        and maximum_rhat <= 1.01
        and minimum_bulk_ess >= 400.0
        and minimum_tail_ess >= 400.0
    )
    return {
        "divergences": divergences,
        "maximum_rhat": maximum_rhat,
        "minimum_bulk_ess": minimum_bulk_ess,
        "minimum_tail_ess": minimum_tail_ess,
        "passed": bool(passed),
    }


def fit_all_models(data: IrtData, preregistration: dict[str, Any]):
    sampling = preregistration["sampling"]
    seeds = list(map(int, sampling["chain_seeds"]))

    def execute(tune: int, target_accept: float):
        models = {
            "binary_rasch": _response_model(data, continuous=False),
            "continuous_beta": _response_model(data, continuous=True),
            "one_factor": _factor_model(data, factors=1),
            "two_factor": _factor_model(data, factors=2),
        }
        traces = {}
        for name in MODEL_NAMES:
            traces[name] = _sample_model(
                models[name],
                tune=tune,
                draws=int(sampling["draws"]),
                target_accept=target_accept,
                seeds=seeds,
                retain_log_likelihood=name in {"one_factor", "two_factor"},
            )
        diagnostics = {
            "binary_rasch": _diagnostics(
                traces["binary_rasch"],
                ["task_difficulty", "variant_ability", "difficulty_limit_10pct"],
            ),
            "continuous_beta": _diagnostics(
                traces["continuous_beta"],
                [
                    "task_difficulty",
                    "variant_ability",
                    "variant_precision",
                    "variant_consistency",
                ],
            ),
            "one_factor": _diagnostics(
                traces["one_factor"],
                ["factor_loading", "item_intercept", "item_residual_sd"],
            ),
            "two_factor": _diagnostics(
                traces["two_factor"],
                ["factor_loading", "item_intercept", "item_residual_sd"],
            ),
        }
        return traces, diagnostics

    traces, diagnostics = execute(
        int(sampling["tune"]), float(sampling["target_accept"])
    )
    escalated = not all(row["passed"] for row in diagnostics.values())
    if escalated:
        escalation = sampling["diagnostic_escalation"]
        traces, diagnostics = execute(
            int(escalation["tune"]), float(escalation["target_accept"])
        )
    return traces, diagnostics, escalated


def _posterior_array(idata, name: str) -> np.ndarray:
    return np.asarray(idata.posterior[name], dtype=np.float64)


def _shortest_hdi(
    samples: np.ndarray, probability: float = 0.95
) -> tuple[float, float]:
    values = np.sort(np.asarray(samples, dtype=float).reshape(-1))
    interval = max(1, int(math.floor(probability * len(values))))
    if interval >= len(values):
        return float(values[0]), float(values[-1])
    widths = values[interval:] - values[: len(values) - interval]
    start = int(np.argmin(widths))
    return float(values[start]), float(values[start + interval])


def _summary_columns(samples: np.ndarray, index: int) -> dict[str, float]:
    values = np.asarray(samples[..., index], dtype=float).reshape(-1)
    low, high = _shortest_hdi(values)
    return {
        "mean": float(np.mean(values)),
        "sd": float(np.std(values, ddof=1)),
        "hdi_2_5pct": low,
        "hdi_97_5pct": high,
    }


def _deterministic_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.lib.format.write_array(
                buffer, np.asarray(arrays[name]), allow_pickle=False
            )
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, buffer.getvalue())


def _taskwise_log_likelihood(idata) -> np.ndarray:
    values = np.asarray(idata.log_likelihood["response"], dtype=np.float64)
    _require(values.ndim == 3 and values.shape[-1] == 96, "factor loglik changed")
    return values


def _loo_comparison(
    one_factor, two_factor
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import arviz as az

    loo_one = az.loo(one_factor, var_name="response", pointwise=True)
    loo_two = az.loo(two_factor, var_name="response", pointwise=True)
    point_one = np.asarray(loo_one.elpd_i, dtype=float)
    point_two = np.asarray(loo_two.elpd_i, dtype=float)
    differences = point_two - point_one
    delta = float(np.sum(differences))
    standard_error = float(np.sqrt(len(differences) * np.var(differences, ddof=1)))
    if delta > standard_error:
        decision = "favor_two_factors"
    elif -delta > standard_error:
        decision = "favor_one_factor"
    else:
        decision = "equivocal"
    rows = []
    for name, result in [("one_factor", loo_one), ("two_factor", loo_two)]:
        pareto = np.asarray(result.pareto_k, dtype=float)
        rows.append(
            {
                "model": name,
                "elpd_loo": float(result.elpd),
                "se": float(result.se),
                "p_loo": float(result.p),
                "pareto_k_over_0_7": int(np.sum(pareto > 0.7)),
                "pareto_k_over_1": int(np.sum(pareto > 1.0)),
                "pointwise_unit": "task",
                "output_kind": "posterior_estimate_exploratory",
            }
        )
    comparison = {
        "delta_elpd_two_minus_one": delta,
        "delta_standard_error": standard_error,
        "decision": decision,
        "reliable": all(row["pareto_k_over_1"] == 0 for row in rows),
    }
    return rows, comparison


def _posterior_predictive_rows(data: IrtData, traces) -> list[dict[str, Any]]:
    rng = np.random.default_rng(2026073199)
    task_index = np.repeat(np.arange(len(data.task_ids)), len(data.variant_ids))
    variant_index = np.tile(np.arange(len(data.variant_ids)), len(data.task_ids))
    family_index = data.variant_solver_family_index[variant_index]

    binary_ability = _posterior_array(traces["binary_rasch"], "variant_ability")
    binary_difficulty = _posterior_array(traces["binary_rasch"], "task_difficulty")
    binary_testlet = _posterior_array(traces["binary_rasch"], "testlet_effect")
    shape = binary_ability.shape[:2]
    probability = 1.0 / (
        1.0
        + np.exp(
            -(
                binary_ability[..., variant_index]
                - binary_difficulty[..., task_index]
                + binary_testlet[..., task_index, family_index]
            )
        )
    )
    predictive_binary = rng.binomial(1, probability).astype(np.int8)

    beta_ability = _posterior_array(traces["continuous_beta"], "variant_ability")
    beta_difficulty = _posterior_array(traces["continuous_beta"], "task_difficulty")
    beta_testlet = _posterior_array(traces["continuous_beta"], "testlet_effect")
    beta_precision = _posterior_array(traces["continuous_beta"], "variant_precision")
    beta_mean = 1.0 / (
        1.0
        + np.exp(
            -(
                beta_ability[..., variant_index]
                - beta_difficulty[..., task_index]
                + beta_testlet[..., task_index, family_index]
            )
        )
    )
    predictive_quality = rng.beta(
        beta_mean * beta_precision[..., variant_index],
        (1.0 - beta_mean) * beta_precision[..., variant_index],
    )

    rows: list[dict[str, Any]] = []
    for family_position, family in enumerate(data.solver_families):
        mask = family_index == family_position
        observed_binary = data.binary.reshape(-1)[mask]
        observed_quality = data.quality.reshape(-1)[mask]
        for track, observed, predictive in [
            ("binary", observed_binary, predictive_binary[..., mask]),
            ("continuous_quality", observed_quality, predictive_quality[..., mask]),
        ]:
            predictive_flat = predictive.reshape(-1)
            rows.append(
                {
                    "track": track,
                    "scope": "solver_family",
                    "scope_id": family,
                    "statistic": "mean",
                    "observed": float(np.mean(observed)),
                    "predictive_mean": float(np.mean(predictive_flat)),
                    "predictive_q10": float(np.quantile(predictive_flat, 0.1)),
                    "predictive_q50": float(np.quantile(predictive_flat, 0.5)),
                    "predictive_q90": float(np.quantile(predictive_flat, 0.9)),
                    "output_kind": "posterior_predictive_check",
                }
            )
    observed_totals = data.binary.sum(axis=1)
    predictive_totals = predictive_binary.reshape(*shape, len(data.task_ids), -1).sum(
        axis=-1
    )
    rows.append(
        {
            "track": "binary",
            "scope": "all_tasks",
            "scope_id": "task_total_score",
            "statistic": "mean",
            "observed": float(np.mean(observed_totals)),
            "predictive_mean": float(np.mean(predictive_totals)),
            "predictive_q10": float(np.quantile(predictive_totals, 0.1)),
            "predictive_q50": float(np.quantile(predictive_totals, 0.5)),
            "predictive_q90": float(np.quantile(predictive_totals, 0.9)),
            "output_kind": "posterior_predictive_check",
        }
    )
    return rows


def write_final_artifacts(
    root: Path,
    preregistration_path: Path,
    output_directory: Path,
    data: IrtData,
    traces,
    diagnostics: dict[str, dict[str, Any]],
    escalated: bool,
) -> dict[str, Any]:
    preregistration = _read_json(preregistration_path)
    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)

    response_rows = []
    for task, task_id in enumerate(data.task_ids):
        for variant, variant_id in enumerate(data.variant_ids):
            response_rows.append(
                {
                    "task_uuid": task_id,
                    "canonical_family": data.task_families[task],
                    "solver_family_id": data.solver_families[
                        data.variant_solver_family_index[variant]
                    ],
                    "solver_variant_id": variant_id,
                    "binary_response": int(data.binary[task, variant]),
                    "clipped_graded_residual": data.clipped_residual[task, variant],
                    "continuous_quality": data.quality[task, variant],
                    "label_of_record_mutated": False,
                    "output_kind": "derived_response",
                }
            )
    stable_csv_dump(
        response_rows, list(response_rows[0]), output_directory / "response_matrix.csv"
    )

    binary_difficulty = _posterior_array(traces["binary_rasch"], "task_difficulty")
    beta_difficulty = _posterior_array(traces["continuous_beta"], "task_difficulty")
    task_rows = []
    for index, task_id in enumerate(data.task_ids):
        row: dict[str, Any] = {
            "task_uuid": task_id,
            "canonical_family": data.task_families[index],
            "primary_hardness_track": "binary_rasch",
            "output_kind": "posterior_estimate",
        }
        for prefix, samples in [
            ("binary_difficulty", binary_difficulty),
            ("continuous_difficulty", beta_difficulty),
        ]:
            row.update(
                {
                    f"{prefix}_{name}": value
                    for name, value in _summary_columns(samples, index).items()
                }
            )
        task_rows.append(row)
    stable_csv_dump(
        task_rows, list(task_rows[0]), output_directory / "task_difficulty.csv"
    )
    handoff_fields = [
        "task_uuid",
        "canonical_family",
        "binary_difficulty_mean",
        "binary_difficulty_sd",
        "binary_difficulty_hdi_2_5pct",
        "binary_difficulty_hdi_97_5pct",
        "output_kind",
    ]
    stable_csv_dump(
        [{name: row[name] for name in handoff_fields} for row in task_rows],
        handoff_fields,
        output_directory / "difficulty_handoff_ml9d.csv",
    )

    binary_ability = _posterior_array(traces["binary_rasch"], "variant_ability")
    beta_ability = _posterior_array(traces["continuous_beta"], "variant_ability")
    consistency = _posterior_array(traces["continuous_beta"], "variant_consistency")
    difficulty_limit = _posterior_array(
        traces["binary_rasch"], "difficulty_limit_10pct"
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
        for prefix, samples in [
            ("binary_ability", binary_ability),
            ("continuous_ability", beta_ability),
            ("consistency", consistency),
            ("difficulty_limit_10pct", difficulty_limit),
        ]:
            row.update(
                {
                    f"{prefix}_{name}": value
                    for name, value in _summary_columns(samples, index).items()
                }
            )
        variant_rows.append(row)
    stable_csv_dump(
        variant_rows,
        list(variant_rows[0]),
        output_directory / "variant_parameters.csv",
    )

    factor1 = _posterior_array(traces["one_factor"], "factor_loading")
    factor2 = _posterior_array(traces["two_factor"], "factor_loading")
    loading_rows = []
    for index, variant_id in enumerate(data.variant_ids):
        for model, factor, samples in [
            ("one_factor", "cpu_axis", factor1),
            ("two_factor", "cpu_axis", factor2[..., 0]),
            ("two_factor", "ipie_axis", factor2[..., 1]),
        ]:
            loading_rows.append(
                {
                    "model": model,
                    "factor": factor,
                    "solver_family_id": data.solver_families[
                        data.variant_solver_family_index[index]
                    ],
                    "solver_variant_id": variant_id,
                    **_summary_columns(samples, index),
                    "output_kind": "posterior_estimate_exploratory",
                }
            )
    stable_csv_dump(
        loading_rows,
        list(loading_rows[0]),
        output_directory / "factor_loadings.csv",
    )

    loo_rows, loo_comparison = _loo_comparison(
        traces["one_factor"], traces["two_factor"]
    )
    ipie_index = data.variant_ids.index(IPIE_FACTOR_ANCHOR)
    cpu_indices = np.asarray(
        [index for index in range(len(data.variant_ids)) if index != ipie_index]
    )
    contrast = np.abs(factor2[..., ipie_index, 1]) / np.median(
        np.abs(factor2[..., cpu_indices, 1]), axis=-1
    )
    contrast_probability = float(np.mean(contrast > 1.0))
    named_hypothesis_supported = bool(
        loo_comparison["decision"] == "favor_two_factors"
        and loo_comparison["reliable"]
        and contrast_probability >= 0.95
    )
    for row in loo_rows:
        row.update(
            {
                "delta_elpd_two_minus_one": loo_comparison["delta_elpd_two_minus_one"],
                "delta_standard_error": loo_comparison["delta_standard_error"],
                "comparison_decision": loo_comparison["decision"],
                "comparison_reliable": loo_comparison["reliable"],
                "ipie_axis_loading_contrast_probability_gt_one": contrast_probability,
                "named_hypothesis_supported": named_hypothesis_supported,
            }
        )
    stable_csv_dump(
        loo_rows,
        list(loo_rows[0]),
        output_directory / "dimensionality_comparison.csv",
    )

    diagnostic_rows = []
    for model in MODEL_NAMES:
        diagnostic_rows.append(
            {
                "model": model,
                **diagnostics[model],
                "diagnostic_escalation_used": escalated,
                "output_kind": "posterior_diagnostic",
            }
        )
    stable_csv_dump(
        diagnostic_rows,
        list(diagnostic_rows[0]),
        output_directory / "posterior_diagnostics.csv",
    )
    predictive_rows = _posterior_predictive_rows(data, traces)
    stable_csv_dump(
        predictive_rows,
        list(predictive_rows[0]),
        output_directory / "posterior_predictive_checks.csv",
    )

    posterior_arrays = {
        "binary_task_difficulty": binary_difficulty,
        "binary_variant_ability": binary_ability,
        "binary_variant_difficulty_limit_10pct": difficulty_limit,
        "continuous_task_difficulty": beta_difficulty,
        "continuous_variant_ability": beta_ability,
        "continuous_variant_consistency": consistency,
        "continuous_variant_precision": _posterior_array(
            traces["continuous_beta"], "variant_precision"
        ),
        "one_factor_loading": factor1,
        "two_factor_loading": factor2,
    }
    _deterministic_npz(output_directory / "posterior_samples.npz", posterior_arrays)
    pointwise_arrays = {
        "one_factor_task_log_likelihood": _taskwise_log_likelihood(
            traces["one_factor"]
        ),
        "two_factor_task_log_likelihood": _taskwise_log_likelihood(
            traces["two_factor"]
        ),
    }
    _deterministic_npz(
        output_directory / "pointwise_log_likelihood.npz", pointwise_arrays
    )

    all_diagnostics_pass = all(row["passed"] for row in diagnostics.values())
    report = {
        "artifact_id": "ml9c_bayesian_inverted_irt_report_v1",
        "status": (
            "complete_internal_posterior_estimate"
            if all_diagnostics_pass
            else "retained_internal_nonconverged"
        ),
        "panel_tasks": len(data.task_ids),
        "solver_variants": len(data.variant_ids),
        "response_cells": int(data.binary.size),
        "binary_success_cells": int(data.binary.sum()),
        "primary_hardness_track": "binary_rasch",
        "family_dependence": "task_by_solver_family_testlet_random_effect",
        "free_item_discrimination": False,
        "diagnostic_escalation_used": escalated,
        "all_sampler_diagnostics_pass": all_diagnostics_pass,
        "loo_comparison": loo_comparison,
        "ipie_axis_loading_contrast_probability_gt_one": contrast_probability,
        "named_ipie_axis_hypothesis_supported": named_hypothesis_supported,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "public_or_dashboard_placement": False,
        "outputs_are_estimates": True,
    }
    stable_json_dump(report, output_directory / "report.json")
    environment = {
        "artifact_id": "ml9c_bayesian_inverted_irt_environment_v1",
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "pymc": __import__("pymc").__version__,
        "arviz": __import__("arviz").__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "thread_limits": {
            name: os.environ.get(name)
            for name in [
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            ]
        },
        "preregistration_sha256": sha256_file(preregistration_path),
        "preflight_manifest_sha256": sha256_file(
            root / "analysis/ml9_bayesian_irt/preflight_v1/artifact_manifest.json"
        ),
        "chain_seeds": preregistration["sampling"]["chain_seeds"],
        "raw_sampler_files_retained": False,
        "deterministic_posterior_arrays_retained": True,
    }
    stable_json_dump(environment, output_directory / "environment.json")

    report_lines = [
        "# ML-9C Bayesian inverted-IRT report",
        "",
        "Status: internal posterior estimates; no public or dashboard placement.",
        "",
        f"The frozen 96 by 18 panel contains {int(data.binary.sum())} binary success cells. "
        "The primary hardness number is the centered task-difficulty posterior from the "
        "hierarchical binary Rasch model. The beta-response track is a graded corroboration.",
        "",
        "Task-by-solver-family testlet effects are included in both tracks. Item "
        "discrimination remains fixed at one. Every task and variant estimate is reported "
        "with a 95% highest-density interval; point rankings are not reported.",
        "",
        f"All sampler health gates pass: {str(all_diagnostics_pass).lower()}. "
        f"Diagnostic escalation used: {str(escalated).lower()}.",
        "",
        f"The exploratory two-minus-one-factor PSIS-LOO delta is "
        f"{loo_comparison['delta_elpd_two_minus_one']:.10g} with standard error "
        f"{loo_comparison['delta_standard_error']:.10g}; decision: "
        f"{loo_comparison['decision']}. The comparison is labeled reliable: "
        f"{str(loo_comparison['reliable']).lower()}.",
        "",
        f"The posterior probability that the absolute iPIE factor-2 loading exceeds "
        f"the median absolute CPU loading is {contrast_probability:.10g}. The named "
        f"iPIE-axis hypothesis is supported: {str(named_hypothesis_supported).lower()}.",
        "",
        "The difficulty handoff is an estimate table for ML-9D. It does not alter any "
        "stored label, task selection, design-based ratio, or solver record.",
        "",
    ]
    (output_directory / "REPORT.md").write_text(
        "\n".join(report_lines), encoding="utf-8", newline="\n"
    )

    required = set(preregistration["outputs"]["required_files"])
    current_without_manifest = {
        path.name for path in output_directory.iterdir() if path.is_file()
    }
    _require(
        current_without_manifest == required - {"artifact_manifest.json"},
        "ML-9C output contract changed",
    )
    files = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(output_directory.iterdir())
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    manifest = {
        "artifact_id": "ml9c_bayesian_inverted_irt_manifest_v1",
        "status": report["status"],
        "files": files,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "free_item_discrimination": False,
        "public_or_dashboard_placement": False,
        "outputs_are_estimates": True,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    _require(all_diagnostics_pass, "ML-9C sampler diagnostics failed after escalation")
    return report


def run_finalization(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    preregistration = _read_json(preregistration_path)
    data = prepare_irt_data(root, preregistration_path)
    traces, diagnostics, escalated = fit_all_models(data, preregistration)
    return write_final_artifacts(
        root,
        preregistration_path,
        output_directory,
        data,
        traces,
        diagnostics,
        escalated,
    )
