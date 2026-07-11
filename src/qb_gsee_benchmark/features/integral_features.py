# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Representation-aware integral feature definitions for G-40."""

from __future__ import annotations

import math

import numpy as np


def log10_fci_dimension(num_orbitals: int, num_electrons: int, ms2: int) -> float:
    """Return log10 of the determinant-space dimension in a fixed MS2 sector.

    ``ms2`` is the FCIDUMP convention N_alpha - N_beta.  The legacy
    implementation divided MS2 by two before deriving alpha/beta counts.
    """
    norb = int(num_orbitals)
    nelec = int(num_electrons)
    spin_projection = int(ms2)
    if norb < 0 or nelec < 0:
        raise ValueError("orbital and electron counts must be nonnegative")
    if (nelec + spin_projection) % 2:
        raise ValueError("NELEC and MS2 must have the same parity")
    nalpha = (nelec + spin_projection) // 2
    nbeta = (nelec - spin_projection) // 2
    if not 0 <= nalpha <= norb or not 0 <= nbeta <= norb:
        raise ValueError("NELEC/MS2 sector does not fit the spatial-orbital count")

    def log10_binomial(n: int, k: int) -> float:
        return (
            math.lgamma(n + 1)
            - math.lgamma(k + 1)
            - math.lgamma(n - k + 1)
        ) / math.log(10.0)

    return log10_binomial(norb, nalpha) + log10_binomial(norb, nbeta)


def effective_one_body(h1: np.ndarray, eri: np.ndarray) -> np.ndarray:
    """Return h_tilde[p,q] = h[p,q] - 1/2 sum_r (p r | r q).

    Integrals use the real spatial-orbital chemist convention emitted by
    FCIDUMP/PySCF.  This convention is frozen by the G-40 feature appendix.
    """
    one_body = np.asarray(h1, dtype=float)
    two_body = np.asarray(eri, dtype=float)
    if one_body.ndim != 2 or one_body.shape[0] != one_body.shape[1]:
        raise ValueError("h1 must be a square spatial-orbital matrix")
    norb = one_body.shape[0]
    if two_body.shape != (norb, norb, norb, norb):
        raise ValueError("eri must have shape (norb, norb, norb, norb)")
    contraction = np.einsum("prrq->pq", two_body, optimize=True)
    return one_body - 0.5 * contraction


def fermionic_coefficient_l1_norm(h1: np.ndarray, eri: np.ndarray) -> float:
    """Return sum_pq |h_tilde_pq| + 1/2 sum_pqrs |(pq|rs)|.

    This is an entrywise spatial-fermionic coefficient norm.  It is tagged BAS:
    it is ordering-independent but generally changes under orbital rotations.
    It is deliberately distinct from the archived Jordan-Wigner ``one_norm``.
    """
    h_tilde = effective_one_body(h1, eri)
    two_body = np.asarray(eri, dtype=float)
    return float(np.sum(np.abs(h_tilde)) + 0.5 * np.sum(np.abs(two_body)))
