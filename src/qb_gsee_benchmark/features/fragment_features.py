# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Fragment-partition and inter-fragment coupling detector features."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np

FRAGMENT_FEATURES_VERSION = "g22_fragment_coupling_detector_v1"
FRAGMENT_FEATURE_COLUMNS = (
    "fragment_count",
    "h2_bond_length_angstrom",
    "fragment_center_separation_angstrom",
    "lambda_interfragment",
    "fragment_partition_tracks",
    "fragment_ml_default_track",
    "fragment_oracle_permission",
    "fragment_partition_assignments_agree",
    "fragment_oracle_one_body_inter_intra_ratio",
    "fragment_oracle_two_body_inter_intra_ratio",
    "fragment_inferred_one_body_inter_intra_ratio",
    "fragment_inferred_two_body_inter_intra_ratio",
    "fragment_detector_version",
    "fragment_calibration_role",
)


def infer_equal_size_fragment_partition(
    orbital_centers: Sequence[float], fragment_count: int
) -> list[int]:
    """Infer equal-sized 1D fragments by sorting orbital centers."""
    centers = np.asarray(orbital_centers, dtype=float)
    if fragment_count <= 0 or len(centers) % fragment_count:
        raise ValueError("orbitals must divide evenly among positive fragment_count")
    assignments = np.zeros(len(centers), dtype=int)
    for fragment_id, indices in enumerate(
        np.array_split(np.argsort(centers), fragment_count)
    ):
        assignments[indices] = fragment_id
    return assignments.tolist()


def split_coupling_norms(
    h1: np.ndarray,
    eri: np.ndarray,
    assignment: Sequence[int],
    *,
    coupling: float = 1.0,
) -> dict[str, float]:
    """Return Frobenius inter/intra ratios for one partition."""
    h1 = np.asarray(h1, dtype=float)
    eri = np.asarray(eri, dtype=float)
    fragments = np.asarray(assignment, dtype=int)
    norb = len(fragments)
    if h1.shape != (norb, norb) or eri.shape != (norb,) * 4:
        raise ValueError("integral dimensions must match partition length")
    one_intra_mask = fragments[:, None] == fragments[None, :]
    four_intra_mask = (
        (fragments[:, None, None, None] == fragments[None, :, None, None])
        & (fragments[:, None, None, None] == fragments[None, None, :, None])
        & (fragments[:, None, None, None] == fragments[None, None, None, :])
    )
    h1_intra = np.where(one_intra_mask, h1, 0.0)
    eri_intra = np.where(four_intra_mask, eri, 0.0)
    one_intra = float(np.linalg.norm(h1_intra))
    two_intra = float(np.linalg.norm(eri_intra))
    if one_intra == 0.0 or two_intra == 0.0:
        raise ValueError("intra-fragment norms must be nonzero")
    one_inter = float(np.linalg.norm(h1 - h1_intra)) * coupling
    two_inter = float(np.linalg.norm(eri - eri_intra)) * coupling
    return {
        "one_body_intra_frobenius": one_intra,
        "one_body_inter_frobenius": one_inter,
        "one_body_inter_intra_ratio": one_inter / one_intra,
        "two_body_intra_frobenius": two_intra,
        "two_body_inter_frobenius": two_inter,
        "two_body_inter_intra_ratio": two_inter / two_intra,
    }


def compute_fragment_features(
    h1: np.ndarray,
    eri: np.ndarray,
    *,
    oracle_assignment: Sequence[int],
    inferred_assignment: Sequence[int],
    fragment_count: int,
    h2_bond_length_angstrom: float,
    fragment_center_separation_angstrom: float,
    lambda_interfragment: float,
    calibration_role: str,
) -> dict[str, Any]:
    """Compute the paired oracle and ML-facing G-22 detector tracks."""
    oracle = split_coupling_norms(
        h1, eri, oracle_assignment, coupling=lambda_interfragment
    )
    inferred = split_coupling_norms(
        h1, eri, inferred_assignment, coupling=lambda_interfragment
    )
    return {
        "fragment_count": int(fragment_count),
        "h2_bond_length_angstrom": float(h2_bond_length_angstrom),
        "fragment_center_separation_angstrom": float(
            fragment_center_separation_angstrom
        ),
        "lambda_interfragment": float(lambda_interfragment),
        "fragment_partition_tracks": ["oracle_geometry", "inferred_orbital_centers"],
        "fragment_ml_default_track": "inferred_orbital_centers",
        "fragment_oracle_permission": "calibration_and_audit_only",
        "fragment_partition_assignments_agree": list(oracle_assignment)
        == list(inferred_assignment),
        "fragment_oracle_one_body_inter_intra_ratio": oracle[
            "one_body_inter_intra_ratio"
        ],
        "fragment_oracle_two_body_inter_intra_ratio": oracle[
            "two_body_inter_intra_ratio"
        ],
        "fragment_inferred_one_body_inter_intra_ratio": inferred[
            "one_body_inter_intra_ratio"
        ],
        "fragment_inferred_two_body_inter_intra_ratio": inferred[
            "two_body_inter_intra_ratio"
        ],
        "fragment_detector_version": FRAGMENT_FEATURES_VERSION,
        "fragment_calibration_role": calibration_role,
    }
