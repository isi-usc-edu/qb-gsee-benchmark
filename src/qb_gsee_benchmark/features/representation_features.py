# Copyright 2026.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0

"""Orbital-representation detector features for spatial-orbital Hamiltonians."""

from __future__ import annotations

from typing import Any

import numpy as np

REPRESENTATION_FEATURES_VERSION = "g21_representation_detector_v1"
REPRESENTATION_INVARIANT_NAMES = (
    "num_orbitals",
    "num_electrons",
    "ms2",
    "ecore_hartree",
    "trace_h1",
    "pair_space_eri_trace",
    "fci_energy_hartree",
)
REPRESENTATION_COVARIANT_NAMES = (
    "h1_offdiag_frobenius",
    "eri_self_repulsion_sum",
    "nonzero_integrals_1e_10",
)
REPRESENTATION_FEATURE_COLUMNS = (
    "equivalence_group_id",
    "ml_split_group_id",
    "orbital_representation",
    "representation_invariant_feature_names",
    "representation_covariant_feature_names",
    *REPRESENTATION_INVARIANT_NAMES,
    *REPRESENTATION_COVARIANT_NAMES,
    "representation_features_version",
)


def compute_representation_features(
    h1: np.ndarray,
    eri: np.ndarray,
    *,
    num_electrons: int,
    ms2: int,
    ecore_hartree: float,
    fci_energy_hartree: float,
    equivalence_group_id: str,
    orbital_representation: str,
    threshold: float = 1.0e-10,
) -> dict[str, Any]:
    """Compute the G-21 invariant/covariant feature split."""
    h1 = np.asarray(h1, dtype=float)
    eri = np.asarray(eri, dtype=float)
    if h1.ndim != 2 or h1.shape[0] != h1.shape[1]:
        raise ValueError("h1 must be a square matrix")
    norb = h1.shape[0]
    if eri.shape != (norb, norb, norb, norb):
        raise ValueError("eri shape must match h1 orbital dimension")
    offdiag = h1 - np.diag(np.diag(h1))
    return {
        "equivalence_group_id": equivalence_group_id,
        "ml_split_group_id": f"representation_pair::{equivalence_group_id}",
        "orbital_representation": orbital_representation,
        "representation_invariant_feature_names": list(REPRESENTATION_INVARIANT_NAMES),
        "representation_covariant_feature_names": list(REPRESENTATION_COVARIANT_NAMES),
        "num_orbitals": norb,
        "num_electrons": int(num_electrons),
        "ms2": int(ms2),
        "ecore_hartree": float(ecore_hartree),
        "trace_h1": float(np.trace(h1)),
        "pair_space_eri_trace": float(np.einsum("ijij->", eri)),
        "fci_energy_hartree": float(fci_energy_hartree),
        "h1_offdiag_frobenius": float(np.linalg.norm(offdiag)),
        "eri_self_repulsion_sum": float(np.einsum("iiii->", eri)),
        "nonzero_integrals_1e_10": int(
            np.count_nonzero(np.abs(h1) > threshold)
            + np.count_nonzero(np.abs(eri) > threshold)
        ),
        "representation_features_version": REPRESENTATION_FEATURES_VERSION,
    }
