# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Universal linear-memory T0 features from a spatial FCIDUMP."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np

from qb_gsee_benchmark.features.fcidump_sparse import (
    DEFAULT_DUPLICATE_ATOL,
    DEFAULT_DUPLICATE_RTOL,
    SparseFcidump,
    eri_symmetry_permutations,
    read_sparse_fcidump,
)
from qb_gsee_benchmark.features.integral_features import log10_fci_dimension


UNIVERSAL_T0_LINEAR_VERSION = "g40_p1_linear_v4"
RELATIVE_THRESHOLD_GRID = (
    1.0e-12,
    1.0e-10,
    1.0e-8,
    1.0e-6,
    1.0e-4,
    1.0e-2,
)


def _threshold_suffix(threshold: float) -> str:
    exponent = int(round(-math.log10(threshold)))
    return f"1e_{exponent}"


def _fraction_above(
    absolute_values: np.ndarray, threshold: float, denominator: int
) -> float:
    if absolute_values.size == 0 or denominator <= 0:
        return 0.0
    scale = float(np.max(absolute_values, initial=0.0))
    if scale == 0.0:
        return 0.0
    return float(
        np.count_nonzero(absolute_values > threshold * scale) / denominator
    )


def effective_one_body_from_sparse(data: SparseFcidump) -> np.ndarray:
    """Return h_tilde[p,q] without allocating the full ERI tensor."""
    effective = data.h1.copy()
    for (p, r, repeated_r, q), value in data.iter_eri_entries():
        if r == repeated_r:
            effective[p, q] -= 0.5 * value
    return effective


def _bare_gap(eigenvalues: np.ndarray, occupation: int) -> float | None:
    if occupation <= 0 or occupation >= len(eigenvalues):
        return None
    return float(eigenvalues[occupation] - eigenvalues[occupation - 1])


def compute_universal_t0_linear_features(
    source: str | Path | SparseFcidump,
    *,
    ms2_override: int | None = None,
) -> dict[str, Any]:
    """Compute G40 P1 header, coefficient, sparsity, and bare-gap features.

    Only symmetry-unique nonzero ERI records and an N**2 one-body matrix are
    stored. Sparsity denominators count the full spatial tensors, including
    mathematical zeros.
    """
    data = (
        source
        if isinstance(source, SparseFcidump)
        else read_sparse_fcidump(source, ms2_override=ms2_override)
    )
    effective_h1 = effective_one_body_from_sparse(data)
    effective_abs = np.abs(effective_h1)
    effective_l1 = float(np.sum(effective_abs))
    effective_frobenius = float(np.linalg.norm(effective_h1))

    eri_l1 = 0.0
    eri_square = 0.0
    eri_max = 0.0
    eri_multiplicities: dict[tuple[int, int, int, int], int] = {}
    for key, value in data.eri_records.items():
        multiplicity = len(eri_symmetry_permutations(*key))
        eri_multiplicities[key] = multiplicity
        absolute = abs(value)
        eri_max = max(eri_max, absolute)
        eri_l1 += multiplicity * absolute
        eri_square += multiplicity * value * value
    eri_frobenius = math.sqrt(eri_square)

    diagonal_l1 = float(np.sum(np.abs(np.diag(effective_h1))))
    rho_offdiag = (
        0.0
        if effective_l1 == 0.0
        else (effective_l1 - diagonal_l1) / effective_l1
    )
    one_body_eigenvalues = np.linalg.eigvalsh(data.h1)
    bandwidth = float(one_body_eigenvalues[-1] - one_body_eigenvalues[0])
    onsite = np.asarray(
        [abs(data.eri_value(p, p, p, p)) for p in range(data.norb)],
        dtype=float,
    )
    u_eff = float(np.mean(onsite))
    u_over_w = None if bandwidth <= 1.0e-14 else u_eff / bandwidth

    alpha_gap = _bare_gap(one_body_eigenvalues, data.nalpha)
    beta_gap = _bare_gap(one_body_eigenvalues, data.nbeta)
    finite_gaps = [gap for gap in (alpha_gap, beta_gap) if gap is not None]
    result: dict[str, Any] = {
        "n_orbs": data.norb,
        "n_elec": data.nelec,
        "ms2": data.ms2,
        "log_fci_dim": log10_fci_dimension(
            data.norb, data.nelec, data.ms2
        ),
        "fermionic_coefficient_l1_norm": effective_l1 + 0.5 * eri_l1,
        "effective_h1_entrywise_l1_norm": effective_l1,
        "effective_h1_frobenius_norm": effective_frobenius,
        "effective_h1_l1_over_frobenius": (
            None
            if effective_frobenius == 0.0
            else effective_l1 / effective_frobenius
        ),
        "eri_full_l1_norm": eri_l1,
        "eri_full_l2_norm": eri_frobenius,
        "eri_l1_over_frobenius": (
            None if eri_frobenius == 0.0 else eri_l1 / eri_frobenius
        ),
        "rho_offdiag": rho_offdiag,
        "bare_one_body_bandwidth": bandwidth,
        "bare_one_body_gap_alpha": alpha_gap,
        "bare_one_body_gap_beta": beta_gap,
        "bare_one_body_gap_min": min(finite_gaps) if finite_gaps else None,
        "U_eff_over_W": u_over_w,
        "U_eff_over_W_reason": (
            "zero_one_body_bandwidth" if u_over_w is None else "ok"
        ),
        "one_body_duplicate_orientation_records_skipped": (
            data.one_body_duplicate_orientations
        ),
        "one_body_duplicate_max_abs_difference": (
            data.one_body_duplicate_max_abs_difference
        ),
        "one_body_duplicate_max_rel_difference": (
            data.one_body_duplicate_max_rel_difference
        ),
        "one_body_symmetry_conflict_records": (
            data.one_body_symmetry_conflict_records
        ),
        "two_body_input_record_count": data.two_body_input_records,
        "two_body_unique_record_count": len(data.eri_records),
        "two_body_duplicate_orientation_records_skipped": (
            data.two_body_duplicate_orientations
        ),
        "two_body_duplicate_max_abs_difference": (
            data.two_body_duplicate_max_abs_difference
        ),
        "two_body_duplicate_max_rel_difference": (
            data.two_body_duplicate_max_rel_difference
        ),
        "two_body_symmetry_conflict_records": (
            data.two_body_symmetry_conflict_records
        ),
        "fcidump_symmetry_status": (
            "conflict_above_tolerance"
            if data.one_body_symmetry_conflict_records
            or data.two_body_symmetry_conflict_records
            else "ok"
        ),
        "fcidump_symmetry_atol": DEFAULT_DUPLICATE_ATOL,
        "fcidump_symmetry_rtol": DEFAULT_DUPLICATE_RTOL,
        "fcidump_container_format": data.container_format,
        "fcidump_container_member": data.container_member,
        "fcidump_ms2_source": data.ms2_source,
        "universal_t0_linear_features_version": (
            UNIVERSAL_T0_LINEAR_VERSION
        ),
    }
    for threshold in RELATIVE_THRESHOLD_GRID:
        suffix = _threshold_suffix(threshold)
        result[f"effective_h1_fraction_above_rel_{suffix}"] = (
            _fraction_above(
                effective_abs.ravel(), threshold, data.norb**2
            )
        )
        eri_above = sum(
            eri_multiplicities[key]
            for key, value in data.eri_records.items()
            if abs(value) > threshold * eri_max
        )
        result[f"eri_fraction_above_rel_{suffix}"] = (
            eri_above / data.norb**4
        )
    return result
