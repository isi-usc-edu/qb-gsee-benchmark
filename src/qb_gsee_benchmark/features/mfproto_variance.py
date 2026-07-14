# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Exact selected-determinant variance for G40 MFPROTO-v3."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from qb_gsee_benchmark.features.mfproto_features import MeanFieldBranch, ParticleSector


@dataclass(frozen=True)
class HFVariance:
    total: float
    per_electron: float
    singles_alpha: float
    singles_beta: float
    doubles_same_spin_alpha: float
    doubles_same_spin_beta: float
    doubles_opposite_spin: float


def _same_spin_doubles_squared(block: np.ndarray) -> float:
    nvir, nocc = block.shape[:2]
    total = 0.0
    for a in range(nvir):
        for b in range(a + 1, nvir):
            for i in range(nocc):
                for j in range(i + 1, nocc):
                    coupling = block[a, i, b, j] - block[a, j, b, i]
                    total += float(coupling * coupling)
    return total


def _transform_ovov(
    eri: np.ndarray,
    virtual_left: np.ndarray,
    occupied_left: np.ndarray,
    virtual_right: np.ndarray,
    occupied_right: np.ndarray,
) -> np.ndarray:
    dimensions = (
        virtual_left.shape[1],
        occupied_left.shape[1],
        virtual_right.shape[1],
        occupied_right.shape[1],
    )
    if 0 in dimensions:
        return np.zeros(dimensions)
    return np.einsum(
        "pqrs,pa,qi,rb,sj->aibj",
        eri,
        virtual_left,
        occupied_left,
        virtual_right,
        occupied_right,
        optimize=True,
    )


def exact_hf_variance(
    eri: np.ndarray, branch: MeanFieldBranch, sector: ParticleSector
) -> HFVariance:
    """Sum squared Hamiltonian couplings to every single and double excitation."""
    if not branch.converged:
        raise ValueError("HF variance requires a converged selected branch")
    required = (
        branch.fock_alpha,
        branch.fock_beta,
        branch.orbitals_alpha,
        branch.orbitals_beta,
    )
    if any(value is None for value in required):
        raise ValueError("selected branch is missing canonical Fock/orbital data")
    eri = np.asarray(eri, dtype=float)
    if eri.shape != (sector.norb,) * 4:
        raise ValueError("ERI shape does not match the particle sector")

    ca = branch.orbitals_alpha
    cb = branch.orbitals_beta
    ca_occ, ca_vir = ca[:, : sector.nalpha], ca[:, sector.nalpha :]
    cb_occ, cb_vir = cb[:, : sector.nbeta], cb[:, sector.nbeta :]
    fock_ov_alpha = ca_vir.T @ branch.fock_alpha @ ca_occ
    fock_ov_beta = cb_vir.T @ branch.fock_beta @ cb_occ
    singles_alpha = float(np.sum(fock_ov_alpha**2))
    singles_beta = float(np.sum(fock_ov_beta**2))

    alpha_block = _transform_ovov(eri, ca_vir, ca_occ, ca_vir, ca_occ)
    beta_block = _transform_ovov(eri, cb_vir, cb_occ, cb_vir, cb_occ)
    opposite_block = _transform_ovov(eri, ca_vir, ca_occ, cb_vir, cb_occ)
    same_alpha = _same_spin_doubles_squared(alpha_block)
    same_beta = _same_spin_doubles_squared(beta_block)
    opposite = float(np.sum(opposite_block**2))
    total = singles_alpha + singles_beta + same_alpha + same_beta + opposite
    return HFVariance(
        total=total,
        per_electron=total / sector.nelec,
        singles_alpha=singles_alpha,
        singles_beta=singles_beta,
        doubles_same_spin_alpha=same_alpha,
        doubles_same_spin_beta=same_beta,
        doubles_opposite_spin=opposite,
    )


def hf_variance_feature_values(variance: HFVariance) -> dict[str, float]:
    return {
        "mf_hf_variance_hartree_squared": variance.total,
        "mf_hf_variance_per_electron_hartree_squared": variance.per_electron,
        "mf_hf_variance_singles_alpha": variance.singles_alpha,
        "mf_hf_variance_singles_beta": variance.singles_beta,
        "mf_hf_variance_doubles_same_spin_alpha": variance.doubles_same_spin_alpha,
        "mf_hf_variance_doubles_same_spin_beta": variance.doubles_same_spin_beta,
        "mf_hf_variance_doubles_opposite_spin": variance.doubles_opposite_spin,
    }
