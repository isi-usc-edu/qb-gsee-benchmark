# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Deterministic numerical primitives for G40 MFPROTO-v1."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MFPROTO_VERSION = "g40_p2_mfproto_v1"
DEGENERACY_ATOL = 1.0e-10
FERMI_RESIDUAL_TOL = 1.0e-13
FERMI_BRACKET_TOL = 1.0e-13
THERMAL_KT_GRID = (0.025, 0.1, 0.25)
DOS_ETA_GRID = (0.05, 0.2)
IPR_WINDOW_GRID = (0.1, 0.5)


@dataclass(frozen=True)
class CanonicalSpectrum:
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    minimum_adjacent_split: float | None
    degenerate_subspace_count: int


@dataclass(frozen=True)
class ParticleSector:
    norb: int
    nelec: int
    ms2: int
    nalpha: int
    nbeta: int


def particle_sector(norb: int, nelec: int, ms2: int) -> ParticleSector:
    """Validate and resolve spatial-orbital alpha/beta particle counts."""
    values = (norb, nelec, ms2)
    if any(not isinstance(value, (int, np.integer)) for value in values):
        raise TypeError("NORB, NELEC, and MS2 must be integers")
    if norb < 0 or nelec < 0:
        raise ValueError("NORB and NELEC must be nonnegative")
    if (nelec + ms2) % 2:
        raise ValueError("NELEC and MS2 have inconsistent parity")
    nalpha = (nelec + ms2) // 2
    nbeta = nelec - nalpha
    if not 0 <= nalpha <= norb or not 0 <= nbeta <= norb:
        raise ValueError("electron sector does not fit NORB")
    return ParticleSector(norb, nelec, ms2, nalpha, nbeta)


def _degenerate_groups(values: np.ndarray, atol: float) -> list[slice]:
    groups = []
    start = 0
    for stop in range(1, values.size + 1):
        if stop == values.size or abs(values[stop] - values[stop - 1]) > atol:
            groups.append(slice(start, stop))
            start = stop
    return groups


def _fix_column_signs(vectors: np.ndarray) -> np.ndarray:
    result = np.array(vectors, dtype=float, copy=True)
    for column in range(result.shape[1]):
        absolute = np.abs(result[:, column])
        pivot = int(np.flatnonzero(absolute == absolute.max())[0])
        if result[pivot, column] < 0:
            result[:, column] *= -1.0
    return result


def canonical_eigh(
    matrix: np.ndarray, *, degeneracy_atol: float = DEGENERACY_ATOL
) -> CanonicalSpectrum:
    """Diagonalize with the MFPROTO projected shipped-index tie rule."""
    matrix = np.asarray(matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("matrix must be square")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("matrix must be finite")
    if not np.allclose(matrix, matrix.T, rtol=0.0, atol=1.0e-12):
        raise ValueError("matrix must be symmetric")

    values, vectors = np.linalg.eigh(matrix)
    groups = _degenerate_groups(values, degeneracy_atol)
    shipped_index = np.arange(matrix.shape[0], dtype=float)
    degenerate_count = 0
    for group in groups:
        if group.stop - group.start < 2:
            continue
        degenerate_count += 1
        subspace = vectors[:, group]
        projected = subspace.T @ (shipped_index[:, None] * subspace)
        _, rotation = np.linalg.eigh(projected)
        vectors[:, group] = subspace @ rotation
    vectors = _fix_column_signs(vectors)
    minimum_split = None if values.size < 2 else float(np.min(np.abs(np.diff(values))))
    return CanonicalSpectrum(
        eigenvalues=values,
        eigenvectors=vectors,
        minimum_adjacent_split=minimum_split,
        degenerate_subspace_count=degenerate_count,
    )


def occupation_density(vectors: np.ndarray, occupations: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=float)
    occupations = np.asarray(occupations, dtype=float)
    if vectors.ndim != 2 or vectors.shape[1] != occupations.size:
        raise ValueError("occupation vector must match orbital columns")
    return (vectors * occupations) @ vectors.T


def fermi_occupations(
    eigenvalues: np.ndarray,
    particles: int,
    kt: float,
    *,
    residual_tol: float = FERMI_RESIDUAL_TOL,
    bracket_tol: float = FERMI_BRACKET_TOL,
) -> tuple[np.ndarray, float]:
    """Solve the frozen MFPROTO Fermi occupation equation by bisection."""
    values = np.asarray(eigenvalues, dtype=float)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("eigenvalues must be a finite vector")
    if not 0 <= particles <= values.size:
        raise ValueError("particle count is outside the spectrum")
    if not np.isfinite(kt) or kt <= 0:
        raise ValueError("kt must be positive and finite")
    if particles == 0:
        return np.zeros(values.size), float(np.min(values) - 64.0 * kt)
    if particles == values.size:
        return np.ones(values.size), float(np.max(values) + 64.0 * kt)

    low = float(np.min(values) - 64.0 * kt)
    high = float(np.max(values) + 64.0 * kt)

    def evaluate(mu: float) -> np.ndarray:
        argument = np.clip((values - mu) / kt, -700.0, 700.0)
        return 1.0 / (1.0 + np.exp(argument))

    occupations = evaluate(0.5 * (low + high))
    for _ in range(512):
        mu = 0.5 * (low + high)
        occupations = evaluate(mu)
        residual = float(np.sum(occupations) - particles)
        if abs(residual) < residual_tol and high - low < bracket_tol:
            return occupations, mu
        if residual < 0:
            low = mu
        else:
            high = mu
    raise RuntimeError("Fermi bisection did not satisfy both stopping criteria")


def initial_spin_density_guesses(
    h1: np.ndarray, nelec: int, ms2: int
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Return G1--G4 alpha/beta densities in shipped-orbital coordinates."""
    h1 = np.asarray(h1, dtype=float)
    sector = particle_sector(h1.shape[0], nelec, ms2)
    core = canonical_eigh(h1)
    identity = np.eye(sector.norb)

    def integer_occupations(order: np.ndarray, count: int) -> np.ndarray:
        result = np.zeros(sector.norb)
        result[np.asarray(order[:count], dtype=int)] = 1.0
        return result

    core_order = np.arange(sector.norb)
    shipped_order = np.arange(sector.norb)
    alpha_alternating = np.array(
        sorted(range(sector.norb), key=lambda index: (index % 2, index))
    )
    beta_alternating = np.array(
        sorted(range(sector.norb), key=lambda index: ((index + 1) % 2, index))
    )
    thermal_alpha, _ = fermi_occupations(
        core.eigenvalues, sector.nalpha, THERMAL_KT_GRID[-1]
    )
    thermal_beta, _ = fermi_occupations(
        core.eigenvalues, sector.nbeta, THERMAL_KT_GRID[-1]
    )
    return {
        "G1": (
            occupation_density(
                core.eigenvectors,
                integer_occupations(core_order, sector.nalpha),
            ),
            occupation_density(
                core.eigenvectors,
                integer_occupations(core_order, sector.nbeta),
            ),
        ),
        "G2": (
            occupation_density(
                identity, integer_occupations(shipped_order, sector.nalpha)
            ),
            occupation_density(
                identity, integer_occupations(shipped_order, sector.nbeta)
            ),
        ),
        "G3": (
            occupation_density(
                identity, integer_occupations(alpha_alternating, sector.nalpha)
            ),
            occupation_density(
                identity, integer_occupations(beta_alternating, sector.nbeta)
            ),
        ),
        "G4": (
            occupation_density(core.eigenvectors, thermal_alpha),
            occupation_density(core.eigenvectors, thermal_beta),
        ),
    }


def occupation_boundary_tie(
    eigenvalues: np.ndarray, particles: int, *, atol: float = DEGENERACY_ATOL
) -> bool:
    values = np.asarray(eigenvalues, dtype=float)
    if particles <= 0 or particles >= values.size:
        return False
    return bool(abs(values[particles] - values[particles - 1]) <= atol)


def spectral_panel(
    eigenvalues: np.ndarray,
    eigenvectors: np.ndarray,
    particles: int,
) -> dict[str, float | bool | None]:
    """Compute one-spin gap, thermal, DOS, and projector-IPR primitives."""
    values = np.asarray(eigenvalues, dtype=float)
    vectors = np.asarray(eigenvectors, dtype=float)
    if vectors.shape != (values.size, values.size):
        raise ValueError("eigenvector dimensions do not match eigenvalues")
    if particles <= 0 or particles >= values.size:
        return {
            "applicable": False,
            "reason": "empty_or_full_spin_sector",
            "gap": None,
            "center": None,
            "edge_degenerate": None,
        }

    homo = float(values[particles - 1])
    lumo = float(values[particles])
    gap = lumo - homo
    edge_degenerate = abs(gap) <= DEGENERACY_ATOL
    center = homo if edge_degenerate else 0.5 * (homo + lumo)
    result: dict[str, float | bool | None] = {
        "applicable": True,
        "reason": None,
        "gap": float(gap),
        "center": float(center),
        "edge_degenerate": edge_degenerate,
    }
    for kt in THERMAL_KT_GRID:
        occupations, _ = fermi_occupations(values, particles, kt)
        result[f"thermal_active_fraction_kt_{kt:g}"] = float(
            np.mean((occupations >= 0.02) & (occupations <= 0.98))
        )
    for eta in DOS_ETA_GRID:
        gaussian = np.exp(-0.5 * ((values - center) / eta) ** 2) / (
            np.sqrt(2.0 * np.pi) * eta
        )
        total = float(np.sum(gaussian))
        result[f"dos_total_eta_{eta:g}"] = total
        result[f"dos_per_orbital_eta_{eta:g}"] = total / values.size
    for width in IPR_WINDOW_GRID:
        selected = np.abs(values - center) <= width
        rank = int(np.count_nonzero(selected))
        result[f"ipr_window_orbital_count_{width:g}"] = rank
        result[f"ipr_window_{width:g}"] = (
            None
            if rank == 0
            else float(np.sum(np.sum(vectors[:, selected] ** 2, axis=1) ** 2) / rank**2)
        )
    return result
