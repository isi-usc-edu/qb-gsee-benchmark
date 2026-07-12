# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Determinant-coupling compressibility features for G40 P1-B."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from qb_gsee_benchmark.features.fcidump_sparse import (
    SparseFcidump,
    read_sparse_fcidump,
)
from qb_gsee_benchmark.features.universal_t0_features import (
    RELATIVE_THRESHOLD_GRID,
    _threshold_suffix,
)

DETERMINANT_COUPLING_VERSION = "g40_p1b_determinant_coupling_v1"
DEFAULT_RANDOM_SEED = 40040
DEFAULT_RANDOM_DETERMINANTS = 32
DEFAULT_EXCITATION_SAMPLES = 2048
TOP_K_GRID = (1, 10, 100)


@dataclass(frozen=True)
class Occupation:
    alpha: tuple[int, ...]
    beta: tuple[int, ...]


def _virtuals(norb: int, occupied: Iterable[int]) -> tuple[int, ...]:
    occupied_set = set(occupied)
    return tuple(index for index in range(norb) if index not in occupied_set)


def diagonal_one_body_reference(data: SparseFcidump) -> Occupation:
    """Choose a permutation-equivariant T0 reference from diagonal h1 values."""
    order = sorted(range(data.norb), key=lambda index: (data.h1[index, index], index))
    return Occupation(
        alpha=tuple(sorted(order[: data.nalpha])),
        beta=tuple(sorted(order[: data.nbeta])),
    )


def _single_coupling(
    data: SparseFcidump,
    occupied: Occupation,
    spin: str,
    hole: int,
    particle: int,
) -> float:
    same_spin = occupied.alpha if spin == "alpha" else occupied.beta
    value = float(data.h1[particle, hole])
    for orbital in occupied.alpha:
        value += data.eri_value(particle, hole, orbital, orbital)
    for orbital in occupied.beta:
        value += data.eri_value(particle, hole, orbital, orbital)
    for orbital in same_spin:
        value -= data.eri_value(particle, orbital, orbital, hole)
    return value


def _same_spin_double_coupling(
    data: SparseFcidump,
    holes: tuple[int, int],
    particles: tuple[int, int],
) -> float:
    i, j = holes
    a, b = particles
    return data.eri_value(a, i, b, j) - data.eri_value(a, j, b, i)


def _opposite_spin_double_coupling(
    data: SparseFcidump,
    alpha_hole: int,
    alpha_particle: int,
    beta_hole: int,
    beta_particle: int,
) -> float:
    return data.eri_value(alpha_particle, alpha_hole, beta_particle, beta_hole)


def reference_coupling_magnitudes(
    data: SparseFcidump, occupied: Occupation
) -> np.ndarray:
    """Return every nonzero one-hop coupling from ``occupied`` exactly once."""
    alpha_occ = set(occupied.alpha)
    beta_occ = set(occupied.beta)
    alpha_virt = set(_virtuals(data.norb, alpha_occ))
    beta_virt = set(_virtuals(data.norb, beta_occ))
    values: list[float] = []

    for spin, holes, particles in (
        ("alpha", occupied.alpha, sorted(alpha_virt)),
        ("beta", occupied.beta, sorted(beta_virt)),
    ):
        for hole in holes:
            for particle in particles:
                value = abs(_single_coupling(data, occupied, spin, hole, particle))
                if value:
                    values.append(value)

    same_alpha: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    same_beta: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    opposite: set[tuple[int, int, int, int]] = set()
    for (a, i, b, j), _ in data.iter_eri_entries():
        if a in alpha_virt and b in alpha_virt and i in alpha_occ and j in alpha_occ:
            if a != b and i != j:
                same_alpha.add((tuple(sorted((i, j))), tuple(sorted((a, b)))))
        if a in beta_virt and b in beta_virt and i in beta_occ and j in beta_occ:
            if a != b and i != j:
                same_beta.add((tuple(sorted((i, j))), tuple(sorted((a, b)))))
        if a in alpha_virt and i in alpha_occ and b in beta_virt and j in beta_occ:
            opposite.add((i, a, j, b))

    for candidates in (same_alpha, same_beta):
        for holes, particles in candidates:
            value = abs(_same_spin_double_coupling(data, holes, particles))
            if value:
                values.append(value)
    for alpha_hole, alpha_particle, beta_hole, beta_particle in opposite:
        value = abs(
            _opposite_spin_double_coupling(
                data,
                alpha_hole,
                alpha_particle,
                beta_hole,
                beta_particle,
            )
        )
        if value:
            values.append(value)
    return np.asarray(values, dtype=float)


def _hamiltonian_scale(data: SparseFcidump) -> float:
    return max(
        float(np.max(np.abs(data.h1), initial=0.0)),
        max((abs(value) for value in data.eri_records.values()), default=0.0),
    )


def _excitation_counts(data: SparseFcidump) -> tuple[int, int, int, int]:
    nva = data.norb - data.nalpha
    nvb = data.norb - data.nbeta
    singles = data.nalpha * nva + data.nbeta * nvb
    alpha_doubles = math.comb(data.nalpha, 2) * math.comb(nva, 2)
    beta_doubles = math.comb(data.nbeta, 2) * math.comb(nvb, 2)
    opposite_doubles = data.nalpha * nva * data.nbeta * nvb
    return singles, alpha_doubles, beta_doubles, opposite_doubles


def _draw_occupation(data: SparseFcidump, rng: np.random.Generator) -> Occupation:
    return Occupation(
        alpha=tuple(sorted(rng.choice(data.norb, data.nalpha, replace=False).tolist())),
        beta=tuple(sorted(rng.choice(data.norb, data.nbeta, replace=False).tolist())),
    )


def _sample_excitation_magnitudes(
    data: SparseFcidump,
    occupied: Occupation,
    samples: int,
    rng: np.random.Generator,
) -> np.ndarray:
    alpha_virt = _virtuals(data.norb, occupied.alpha)
    beta_virt = _virtuals(data.norb, occupied.beta)
    counts = _excitation_counts(data)
    cumulative = np.cumsum(counts)
    total = int(cumulative[-1])
    if total == 0:
        return np.zeros(samples, dtype=float)

    values = np.empty(samples, dtype=float)
    for sample in range(samples):
        draw = int(rng.integers(total))
        if draw < cumulative[0]:
            alpha_count = data.nalpha * len(alpha_virt)
            if draw < alpha_count:
                hole = int(rng.choice(occupied.alpha))
                particle = int(rng.choice(alpha_virt))
                value = _single_coupling(data, occupied, "alpha", hole, particle)
            else:
                hole = int(rng.choice(occupied.beta))
                particle = int(rng.choice(beta_virt))
                value = _single_coupling(data, occupied, "beta", hole, particle)
        elif draw < cumulative[1]:
            holes = tuple(sorted(rng.choice(occupied.alpha, 2, replace=False).tolist()))
            particles = tuple(sorted(rng.choice(alpha_virt, 2, replace=False).tolist()))
            value = _same_spin_double_coupling(data, holes, particles)
        elif draw < cumulative[2]:
            holes = tuple(sorted(rng.choice(occupied.beta, 2, replace=False).tolist()))
            particles = tuple(sorted(rng.choice(beta_virt, 2, replace=False).tolist()))
            value = _same_spin_double_coupling(data, holes, particles)
        else:
            value = _opposite_spin_double_coupling(
                data,
                int(rng.choice(occupied.alpha)),
                int(rng.choice(alpha_virt)),
                int(rng.choice(occupied.beta)),
                int(rng.choice(beta_virt)),
            )
        values[sample] = abs(value)
    return values


def random_determinant_branching_profile(
    data: SparseFcidump,
    scale: float,
    *,
    seed: int = DEFAULT_RANDOM_SEED,
    determinants: int = DEFAULT_RANDOM_DETERMINANTS,
    excitation_samples: int = DEFAULT_EXCITATION_SAMPLES,
) -> dict[str, float]:
    """Estimate sector-uniform expected threshold degree with fixed-seed MC."""
    if determinants <= 1 or excitation_samples <= 0:
        raise ValueError("random branching requires >1 determinants and samples")
    rng = np.random.default_rng(seed)
    total_degree = int(sum(_excitation_counts(data)))
    estimates = {threshold: [] for threshold in RELATIVE_THRESHOLD_GRID}
    for _ in range(determinants):
        occupied = _draw_occupation(data, rng)
        magnitudes = _sample_excitation_magnitudes(
            data, occupied, excitation_samples, rng
        )
        for threshold in RELATIVE_THRESHOLD_GRID:
            probability = float(np.mean(magnitudes > threshold * scale))
            estimates[threshold].append(total_degree * probability)

    result: dict[str, float] = {}
    for threshold, values in estimates.items():
        suffix = _threshold_suffix(threshold)
        array = np.asarray(values, dtype=float)
        result[f"random_det_expected_degree_rel_{suffix}"] = float(np.mean(array))
        result[f"random_det_expected_degree_mc_se_rel_{suffix}"] = float(
            np.std(array, ddof=1) / math.sqrt(determinants)
        )
    return result


def _tail_slope(magnitudes: np.ndarray, scale: float) -> float | None:
    positive = np.sort(magnitudes[magnitudes > 0.0])[::-1]
    if positive.size < 8 or scale == 0.0:
        return None
    start = max(1, int(math.floor(0.2 * positive.size)))
    ranks = np.arange(start + 1, positive.size + 1, dtype=float)
    tail = positive[start:] / scale
    if tail.size < 4:
        return None
    return float(np.polyfit(np.log10(ranks), np.log10(tail), 1)[0])


def compute_determinant_coupling_features(
    source: str | Path | SparseFcidump,
    *,
    ms2_override: int | None = None,
    random_seed: int = DEFAULT_RANDOM_SEED,
    random_determinants: int = DEFAULT_RANDOM_DETERMINANTS,
    excitation_samples: int = DEFAULT_EXCITATION_SAMPLES,
) -> dict[str, Any]:
    """Compute the shared-space G40 P1-B determinant-coupling block."""
    data = (
        source
        if isinstance(source, SparseFcidump)
        else read_sparse_fcidump(source, ms2_override=ms2_override)
    )
    reference = diagonal_one_body_reference(data)
    magnitudes = reference_coupling_magnitudes(data, reference)
    scale = _hamiltonian_scale(data)
    squares = magnitudes * magnitudes
    square_mass = float(np.sum(squares))
    fourth_mass = float(np.sum(squares * squares))
    sorted_squares = np.sort(squares)[::-1]
    result: dict[str, Any] = {
        "det_coupling_reference": "lowest_diagonal_h1_file_orbitals",
        "det_coupling_scale": scale,
        "det_coupling_nonzero_degree": int(magnitudes.size),
        "det_coupling_participation_ratio": (
            0.0 if fourth_mass == 0.0 else square_mass * square_mass / fourth_mass
        ),
        "det_coupling_tail_loglog_slope": _tail_slope(magnitudes, scale),
        "random_det_branching_seed": random_seed,
        "random_det_branching_determinants": random_determinants,
        "random_det_branching_excitation_samples_per_det": excitation_samples,
        "determinant_coupling_features_version": DETERMINANT_COUPLING_VERSION,
    }
    for threshold in RELATIVE_THRESHOLD_GRID:
        suffix = _threshold_suffix(threshold)
        result[f"det_coupling_count_above_rel_{suffix}"] = int(
            np.count_nonzero(magnitudes > threshold * scale)
        )
    for top_k in TOP_K_GRID:
        result[f"det_coupling_top_{top_k}_l2_mass_fraction"] = (
            0.0
            if square_mass == 0.0
            else float(np.sum(sorted_squares[:top_k]) / square_mass)
        )
    result.update(
        random_determinant_branching_profile(
            data,
            scale,
            seed=random_seed,
            determinants=random_determinants,
            excitation_samples=excitation_samples,
        )
    )
    return result
