"""Nonnegative factor graph frozen for the ML-9C v3 recovery."""

from __future__ import annotations

from typing import Any

import numpy as np

from qb_gsee_benchmark.ml.bayesian_irt_recovery import CPU_FACTOR_ANCHOR
from qb_gsee_benchmark.ml.bayesian_irt_run import IPIE_FACTOR_ANCHOR
from qb_gsee_benchmark.ml.core_set import _require


def nonnegative_factor_model(
    values: np.ndarray,
    variant_ids: tuple[str, ...],
    task_ids: tuple[str, ...],
    factors: int,
):
    """Construct the frozen v3 nonnegative-loading factor model."""

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
        if factors == 1:
            loading = pm.HalfNormal("nonnegative_loadings", 0.75, dims="variant")
            factor_loading = pm.Deterministic("factor_loading", loading, dims="variant")
            covariance = pt.outer(factor_loading, factor_loading)
        else:
            cpu_anchor_loading = pm.HalfNormal("cpu_anchor_loading", 1.0)
            ipie_anchor_loading = pm.HalfNormal("ipie_anchor_loading", 1.0)
            free_indices = np.asarray(
                [
                    index
                    for index in range(len(variant_ids))
                    if index not in {cpu_anchor, ipie_anchor}
                ],
                dtype=int,
            )
            free_loadings = pm.HalfNormal(
                "nonnegative_loadings", 0.75, shape=(len(free_indices), 2)
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
