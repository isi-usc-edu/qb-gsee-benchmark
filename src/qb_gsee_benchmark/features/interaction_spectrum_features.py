# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Exact invariant interaction-spectrum features for G40 P1-D."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import linalg

from qb_gsee_benchmark.features.fcidump_sparse import (
    SparseFcidump,
    read_sparse_fcidump,
)

INTERACTION_SPECTRUM_VERSION = "g40_p1d_interaction_spectrum_v1"
RELATIVE_RANK_THRESHOLDS = (1.0e-2, 1.0e-4, 1.0e-6)
EIGENVALUE_ZERO_RTOL = 1.0e-12
EIGENVALUE_ZERO_ATOL = 1.0e-12


def _pair(index1: int, index2: int) -> tuple[int, int]:
    return (max(index1, index2), min(index1, index2))


def symmetric_pair_matrix(data: SparseFcidump) -> tuple[np.ndarray, int]:
    """Return the exact nonzero-support symmetric-pair matrix and full size."""
    full_dimension = data.norb * (data.norb + 1) // 2
    active_pairs = sorted(
        {
            pair
            for indices in data.eri_records
            for pair in (_pair(indices[0], indices[1]), _pair(indices[2], indices[3]))
        }
    )
    if not active_pairs:
        return np.zeros((0, 0), dtype=float), full_dimension
    pair_index = {pair: index for index, pair in enumerate(active_pairs)}
    matrix = np.zeros((len(active_pairs), len(active_pairs)), dtype=float)
    for (p, q, r, s), value in data.eri_records.items():
        left = _pair(p, q)
        right = _pair(r, s)
        left_weight = math.sqrt(2.0) if left[0] != left[1] else 1.0
        right_weight = math.sqrt(2.0) if right[0] != right[1] else 1.0
        weighted = left_weight * right_weight * value
        i, j = pair_index[left], pair_index[right]
        matrix[i, j] = weighted
        matrix[j, i] = weighted
    return matrix, full_dimension


def exact_symmetric_pair_eigenvalues(data: SparseFcidump) -> tuple[np.ndarray, int, int]:
    matrix, full_dimension = symmetric_pair_matrix(data)
    active_dimension = len(matrix)
    if active_dimension == 0:
        return np.zeros(0, dtype=float), full_dimension, active_dimension
    eigenvalues = linalg.eigh(
        matrix,
        eigvals_only=True,
        overwrite_a=True,
        check_finite=False,
        driver="evd",
    )
    scale = float(np.max(np.abs(eigenvalues), initial=0.0))
    zero_tolerance = max(EIGENVALUE_ZERO_ATOL, EIGENVALUE_ZERO_RTOL * scale)
    eigenvalues[np.abs(eigenvalues) <= zero_tolerance] = 0.0
    return eigenvalues, full_dimension, active_dimension


def _threshold_suffix(threshold: float) -> str:
    return f"1e_{abs(int(round(math.log10(threshold))))}"


def compute_interaction_spectrum_features(
    source: str | Path | SparseFcidump,
    *,
    ms2_override: int | None = None,
) -> dict[str, Any]:
    data = (
        source
        if isinstance(source, SparseFcidump)
        else read_sparse_fcidump(source, ms2_override=ms2_override)
    )
    eigenvalues, full_dimension, active_dimension = exact_symmetric_pair_eigenvalues(data)
    magnitudes = np.sort(np.abs(eigenvalues))[::-1]
    scale = float(magnitudes[0]) if magnitudes.size else 0.0
    absolute_sum = float(np.sum(magnitudes))
    square_sum = float(np.dot(magnitudes, magnitudes))
    if absolute_sum == 0.0:
        effective_rank = participation_rank = relative_gap = 0.0
    else:
        probabilities = magnitudes[magnitudes > 0.0] / absolute_sum
        effective_rank = float(np.exp(-np.dot(probabilities, np.log(probabilities))))
        participation_rank = absolute_sum * absolute_sum / square_sum
        second = float(magnitudes[1]) if magnitudes.size > 1 else 0.0
        relative_gap = (scale - second) / scale
    rank_1e_4 = int(np.count_nonzero(magnitudes > 1.0e-4 * scale)) if scale else 0
    if rank_1e_4 >= 2:
        ranks = np.arange(1, rank_1e_4 + 1, dtype=float)
        decay_exponent = float(
            np.polyfit(np.log10(ranks), np.log10(magnitudes[:rank_1e_4]), 1)[0]
        )
    else:
        decay_exponent = None
    negative_mass = float(np.sum(np.abs(eigenvalues[eigenvalues < 0.0])))
    result: dict[str, Any] = {
        "interaction_spectrum_effective_rank": effective_rank,
        "interaction_spectrum_participation_rank": participation_rank,
        "interaction_spectrum_decay_exponent": decay_exponent,
        "interaction_spectrum_relative_gap": relative_gap,
        "interaction_spectrum_negative_mass_fraction": (
            0.0 if absolute_sum == 0.0 else negative_mass / absolute_sum
        ),
        "interaction_spectrum_max_abs_eigenvalue": scale,
        "interaction_spectrum_pair_dimension": full_dimension,
        "interaction_spectrum_active_pair_dimension": active_dimension,
        "interaction_spectrum_zero_rtol": EIGENVALUE_ZERO_RTOL,
        "interaction_spectrum_zero_atol": EIGENVALUE_ZERO_ATOL,
        "interaction_spectrum_features_version": INTERACTION_SPECTRUM_VERSION,
    }
    for threshold in RELATIVE_RANK_THRESHOLDS:
        result[f"interaction_spectrum_rank_rel_{_threshold_suffix(threshold)}"] = (
            int(np.count_nonzero(magnitudes > threshold * scale)) if scale else 0
        )
    return result
