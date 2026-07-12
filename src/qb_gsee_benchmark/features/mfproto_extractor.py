# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Panel-isolated orchestration for G40 MFPROTO-v1."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from qb_gsee_benchmark.features.fcidump_sparse import read_sparse_fcidump
from qb_gsee_benchmark.features.mfproto_features import (
    MFPROTO_VERSION,
    MeanFieldBranch,
    mean_field_feature_values,
    run_mean_field,
)
from qb_gsee_benchmark.features.mfproto_mp2 import run_mp2
from qb_gsee_benchmark.features.mfproto_stability import (
    run_stability,
    stability_feature_values,
)
from qb_gsee_benchmark.features.mfproto_variance import (
    exact_hf_variance,
    hf_variance_feature_values,
)


@dataclass
class MFPROTOExtraction:
    features: dict[str, Any]
    audit: dict[str, Any]


def _branch_audit(branch: MeanFieldBranch) -> dict[str, Any]:
    return {
        "method": branch.method,
        "guess": branch.guess,
        "converged": branch.converged,
        "fallback_used": branch.fallback_used,
        "engine_converged": branch.engine_converged,
        "energy_hartree": branch.energy,
        "final_delta_energy_hartree": branch.final_delta_energy,
        "maximum_ov_gradient_hartree": branch.maximum_ov_gradient,
        "s2": branch.s2,
        "cycles": branch.cycles,
        "error_type": branch.error_type,
        "error_message": branch.error_message,
    }


def _panel_failure(
    features: dict[str, Any], panel: str, exc: Exception
) -> dict[str, str]:
    features[f"{panel}_applicable"] = False
    features[f"{panel}_reason"] = f"numerical_exception:{type(exc).__name__}"
    return {"error_type": type(exc).__name__, "error_message": str(exc)}


def compute_mfproto_features(
    source: str | Path, *, ms2_override: int | None = None
) -> MFPROTOExtraction:
    started = time.monotonic()
    data = read_sparse_fcidump(source, ms2_override=ms2_override)
    dense_started = time.monotonic()
    eri = data.dense_eri()
    dense_seconds = time.monotonic() - dense_started

    mean_started = time.monotonic()
    mean_field = run_mean_field(data, eri)
    mean_seconds = time.monotonic() - mean_started
    features = mean_field_feature_values(mean_field)
    audit: dict[str, Any] = {
        "branch_outcomes": [_branch_audit(branch) for branch in mean_field.branches],
        "stationary_components": mean_field.components,
        "selected_branch_index": mean_field.selected_branch_index,
        "panel_errors": {},
    }
    features.update(
        {
            "mfproto_features_version": MFPROTO_VERSION,
            "mfproto_dense_eri_seconds": dense_seconds,
            "mfproto_scf_seconds": mean_seconds,
        }
    )
    selected = mean_field.selected
    if selected is None:
        features.update(
            {
                "mf_stability_applicable": False,
                "mf_stability_reason": "no_converged_scf_branch",
                "mf_hf_variance_applicable": False,
                "mf_hf_variance_reason": "no_converged_scf_branch",
                "mp2_applicable": False,
                "mp2_reason": "no_converged_scf_branch",
                "mfproto_total_seconds": time.monotonic() - started,
            }
        )
        return MFPROTOExtraction(features, audit)

    final_branch = selected
    stability_started = time.monotonic()
    try:
        stability = run_stability(data, eri, selected)
        final_branch = stability.final_branch
        features.update(stability_feature_values(stability))
        features["mf_stability_applicable"] = True
        features["mf_stability_reason"] = None
        audit["stability_follow_outcomes"] = stability.follow_outcomes
        audit["stability_final_branch"] = _branch_audit(final_branch)
    except Exception as exc:
        audit["panel_errors"]["mf_stability"] = _panel_failure(
            features, "mf_stability", exc
        )
    features["mfproto_stability_seconds"] = time.monotonic() - stability_started

    variance_started = time.monotonic()
    try:
        variance = exact_hf_variance(eri, final_branch, mean_field.sector)
        features.update(hf_variance_feature_values(variance))
        features["mf_hf_variance_applicable"] = True
        features["mf_hf_variance_reason"] = None
    except Exception as exc:
        audit["panel_errors"]["mf_hf_variance"] = _panel_failure(
            features, "mf_hf_variance", exc
        )
    features["mfproto_hf_variance_seconds"] = time.monotonic() - variance_started

    mp2_started = time.monotonic()
    try:
        mp2_result = run_mp2(data, eri, final_branch, mean_field.sector)
        features.update(mp2_result.features)
        features["mp2_applicable"] = True
        features["mp2_reason"] = None
    except Exception as exc:
        audit["panel_errors"]["mp2"] = _panel_failure(features, "mp2", exc)
    mp2_and_pair_graph_seconds = time.monotonic() - mp2_started
    pair_graph_seconds = float(features.get("mfproto_pair_graph_seconds", 0.0))
    features["mfproto_mp2_seconds"] = max(
        0.0, mp2_and_pair_graph_seconds - pair_graph_seconds
    )
    features["mfproto_total_seconds"] = time.monotonic() - started
    return MFPROTOExtraction(features, audit)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value
