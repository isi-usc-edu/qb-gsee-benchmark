# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Canonical MP2 panels for G40 MFPROTO-v1."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pyscf import mp

from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump
from qb_gsee_benchmark.features.mfproto_features import (
    MeanFieldBranch,
    ParticleSector,
    pyscf_solver_for_branch,
)
from qb_gsee_benchmark.features.mfproto_variance import _transform_ovov
from qb_gsee_benchmark.features.orderability_features import (
    PROFILE_METRICS,
    RANDOM_ORDER_SEED,
    cut_profile,
    fiedler_order,
    linear_relaxation_order,
    minimum_degree_order,
    rcm_order,
)

DENOMINATOR_THRESHOLD = 1.0e-6
DENOMINATOR_PERCENTILES = (1, 5, 25, 50)
KAPPA_GRID = (1.45, 1.1)
TOP_K_GRID = (16, 128)
NATURAL_OCCUPATION_TOL = 1.0e-8
NATURAL_ACTIVE_LOW = 0.02
NATURAL_ACTIVE_HIGH = 0.98
PAIR_GRAPH_ORDERINGS = (
    "file",
    "fiedler",
    "linear_relaxation",
    "rcm",
    "minimum_degree",
    "random",
)


@dataclass
class MP2Result:
    features: dict[str, object]
    pair_graph: np.ndarray
    t2: object


def _denominators(
    occupied_left: np.ndarray,
    occupied_right: np.ndarray,
    virtual_left: np.ndarray,
    virtual_right: np.ndarray,
) -> np.ndarray:
    return (
        occupied_left[:, None, None, None]
        + occupied_right[None, :, None, None]
        - virtual_left[None, None, :, None]
        - virtual_right[None, None, None, :]
    )


def _masked_amplitude(
    integrals: np.ndarray, denominator: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    mask = np.abs(denominator) < DENOMINATOR_THRESHOLD
    amplitude = np.zeros_like(integrals)
    np.divide(integrals, denominator, out=amplitude, where=~mask)
    return amplitude, mask


def _amplitude_summary(values: np.ndarray, prefix: str) -> dict[str, float]:
    absolute = np.abs(np.asarray(values).ravel())
    l1 = float(np.sum(absolute))
    l2_square = float(np.dot(absolute, absolute))
    fourth = float(np.dot(absolute**2, absolute**2))
    result = {
        f"{prefix}_max_abs": float(np.max(absolute, initial=0.0)),
        f"{prefix}_l1_norm": l1,
        f"{prefix}_l2_norm": float(np.sqrt(l2_square)),
        f"{prefix}_participation_ratio": (
            0.0 if fourth == 0.0 else l2_square**2 / fourth
        ),
    }
    ordered_square = np.sort(absolute**2)[::-1]
    for top_k in TOP_K_GRID:
        result[f"{prefix}_top_{top_k}_l2_mass_fraction"] = (
            0.0
            if l2_square == 0.0
            else float(np.sum(ordered_square[:top_k]) / l2_square)
        )
    return result


def _denominator_features(
    denominators: list[np.ndarray], masks: list[np.ndarray]
) -> dict[str, object]:
    magnitudes = np.concatenate([np.abs(values).ravel() for values in denominators])
    mask = np.concatenate([values.ravel() for values in masks])
    unmasked = magnitudes[~mask]
    result: dict[str, object] = {
        "mp2_denominator_term_count": int(magnitudes.size),
        "mp2_denominator_masked_count": int(np.count_nonzero(mask)),
        "mp2_denominator_masked_fraction": float(np.mean(mask)) if mask.size else 0.0,
        "mp2_denominator_partial_mask": bool(np.any(mask)),
        "mp2_denominator_applicable": bool(unmasked.size),
        "mp2_denominator_reason": (
            None if unmasked.size else "all_denominators_below_threshold"
        ),
    }
    for percentile in DENOMINATOR_PERCENTILES:
        result[f"mp2_denominator_p{percentile}_hartree"] = (
            None
            if not unmasked.size
            else float(np.percentile(unmasked, percentile, method="linear"))
        )
    result["mp2_denominator_inverse_first_moment"] = (
        None if not unmasked.size else float(np.mean(1.0 / unmasked))
    )
    result["mp2_denominator_inverse_second_moment"] = (
        None if not unmasked.size else float(np.mean(1.0 / unmasked**2))
    )
    return result


def _natural_occupation_features(mp_solver, t2, nelec: int) -> dict[str, object]:
    density = mp_solver.make_rdm1(t2=t2)
    if isinstance(density, tuple):
        occupations = np.concatenate(
            [np.linalg.eigvalsh(np.asarray(spin_density)) for spin_density in density]
        )
    else:
        spatial = np.linalg.eigvalsh(np.asarray(density) / 2.0)
        occupations = np.repeat(spatial, 2)
    minimum = float(np.min(occupations, initial=np.inf))
    maximum = float(np.max(occupations, initial=-np.inf))
    outside = (
        minimum < -NATURAL_OCCUPATION_TOL or maximum > 1.0 + NATURAL_OCCUPATION_TOL
    )
    result: dict[str, object] = {
        "mp2_natural_occupation_minimum_raw": minimum,
        "mp2_natural_occupation_maximum_raw": maximum,
        "mp2_natural_occupation_applicable": not outside,
        "mp2_natural_occupation_reason": (
            "natural_occupation_out_of_range" if outside else None
        ),
    }
    if outside:
        result.update(
            {
                "mp2_natural_occupation_clipped_count": None,
                "mp2_natural_entropy": None,
                "mp2_natural_entropy_per_electron": None,
                "mp2_natural_active_fraction": None,
            }
        )
        return result
    clipped = np.clip(occupations, 0.0, 1.0)
    clipped_count = int(np.count_nonzero(clipped != occupations))
    positive = clipped[(clipped > 0.0) & (clipped < 1.0)]
    entropy = float(
        -np.sum(positive * np.log(positive) + (1.0 - positive) * np.log(1.0 - positive))
    )
    result.update(
        {
            "mp2_natural_occupation_clipped_count": clipped_count,
            "mp2_natural_entropy": entropy,
            "mp2_natural_entropy_per_electron": entropy / nelec,
            "mp2_natural_active_fraction": float(
                np.mean(
                    (clipped > NATURAL_ACTIVE_LOW) & (clipped < NATURAL_ACTIVE_HIGH)
                )
            ),
        }
    )
    return result


def _pair_graph_features(weights: np.ndarray) -> dict[str, object]:
    orders = {
        "file": np.arange(len(weights), dtype=int),
        "fiedler": fiedler_order(weights),
        "linear_relaxation": linear_relaxation_order(weights),
        "rcm": rcm_order(weights),
        "minimum_degree": minimum_degree_order(weights),
        "random": np.random.default_rng(RANDOM_ORDER_SEED).permutation(len(weights)),
    }
    summaries = {}
    for name, order in orders.items():
        profile = cut_profile(weights, order)
        summaries[name] = {
            "max": float(np.max(profile, initial=0.0)),
            "p95": (
                0.0
                if not profile.size
                else float(np.percentile(profile, 95, method="linear"))
            ),
            "sum": float(np.sum(profile)),
        }
    result: dict[str, object] = {
        "mp2_pair_graph_zero": bool(not np.any(weights)),
        "mp2_pair_graph_edge_count": int(np.count_nonzero(np.triu(weights, 1))),
        "mp2_pair_graph_total_weight": float(np.sum(np.triu(weights, 1))),
        "mp2_pair_graph_random_seed": RANDOM_ORDER_SEED,
    }
    heuristics = ("fiedler", "linear_relaxation", "rcm", "minimum_degree")
    for name in PAIR_GRAPH_ORDERINGS:
        for metric in PROFILE_METRICS:
            result[f"mp2_pair_cut_{name}_{metric}"] = summaries[name][metric]
    for metric in PROFILE_METRICS:
        best_name = min(heuristics, key=lambda name: (summaries[name][metric], name))
        values = [summaries[name][metric] for name in heuristics]
        maximum = max(values)
        result[f"mp2_pair_cut_best_{metric}"] = summaries[best_name][metric]
        result[f"mp2_pair_cut_best_{metric}_heuristic"] = best_name
        result[f"mp2_pair_cut_heuristic_spread_{metric}"] = (
            0.0 if maximum == 0.0 else (maximum - min(values)) / maximum
        )
    return result


def _kappa_features(
    energy_terms: list[np.ndarray], denominators: list[np.ndarray]
) -> dict[str, object]:
    energies = {"inf": float(sum(np.sum(terms) for terms in energy_terms))}
    for kappa in KAPPA_GRID:
        energy = 0.0
        for terms, denominator in zip(energy_terms, denominators):
            damping = 1.0 - np.exp(-kappa * np.abs(denominator))
            energy += float(np.sum(terms * damping**2))
        label = str(kappa).replace(".", "p")
        energies[label] = energy
    result: dict[str, object] = {
        f"mp2_kappa_{label}_correlation_energy_hartree": value
        for label, value in energies.items()
    }
    comparisons = (("1p45", "inf"), ("1p1", "inf"), ("1p1", "1p45"))
    for numerator, denominator in comparisons:
        prefix = f"mp2_kappa_{numerator}_vs_{denominator}"
        result[f"{prefix}_difference_hartree"] = (
            energies[numerator] - energies[denominator]
        )
        applicable = abs(energies[denominator]) >= 1.0e-14
        result[f"{prefix}_ratio_applicable"] = applicable
        result[f"{prefix}_ratio_reason"] = (
            None if applicable else "correlation_energy_denominator_below_1e_14"
        )
        result[f"{prefix}_ratio"] = (
            energies[numerator] / energies[denominator] if applicable else None
        )
    return result


def run_mp2(
    data: SparseFcidump,
    eri: np.ndarray,
    branch: MeanFieldBranch,
    sector: ParticleSector,
) -> MP2Result:
    """Compute masked canonical RMP2/UMP2 panels on the selected state."""
    if not branch.converged:
        raise ValueError("MP2 requires a converged selected branch")
    ca, cb = branch.orbitals_alpha, branch.orbitals_beta
    ea, eb = branch.energies_alpha, branch.energies_beta
    ca_occ, ca_vir = ca[:, : sector.nalpha], ca[:, sector.nalpha :]
    cb_occ, cb_vir = cb[:, : sector.nbeta], cb[:, sector.nbeta :]
    pair_energy = np.zeros((sector.norb, sector.norb))

    if branch.method == "RHF":
        block = _transform_ovov(eri, ca_vir, ca_occ, ca_vir, ca_occ)
        integrals = block.transpose(1, 3, 0, 2)
        denominator = _denominators(
            ea[: sector.nalpha],
            ea[: sector.nalpha],
            ea[sector.nalpha :],
            ea[sector.nalpha :],
        )
        t2, mask = _masked_amplitude(integrals, denominator)
        exchange = integrals.swapaxes(2, 3)
        opposite_terms = t2 * integrals
        same_terms = t2 * integrals - t2 * exchange
        opposite_energy = float(np.sum(opposite_terms))
        same_energy = float(np.sum(same_terms))
        amplitudes = t2.ravel()
        opposite_amplitudes = t2.ravel()
        same_amplitudes = np.concatenate((t2.ravel(), t2.ravel()))
        denominators = [denominator]
        masks = [mask]
        energy_terms = [opposite_terms + same_terms]
        pair_energy[: sector.nalpha, : sector.nalpha] += np.sum(
            opposite_terms + same_terms, axis=(2, 3)
        )
        t2_for_density = t2
    else:
        block_aa = _transform_ovov(eri, ca_vir, ca_occ, ca_vir, ca_occ)
        block_bb = _transform_ovov(eri, cb_vir, cb_occ, cb_vir, cb_occ)
        block_ab = _transform_ovov(eri, ca_vir, ca_occ, cb_vir, cb_occ)
        integral_aa = block_aa.transpose(1, 3, 0, 2)
        integral_bb = block_bb.transpose(1, 3, 0, 2)
        integral_ab = block_ab.transpose(1, 3, 0, 2)
        denominator_aa = _denominators(
            ea[: sector.nalpha],
            ea[: sector.nalpha],
            ea[sector.nalpha :],
            ea[sector.nalpha :],
        )
        denominator_bb = _denominators(
            eb[: sector.nbeta],
            eb[: sector.nbeta],
            eb[sector.nbeta :],
            eb[sector.nbeta :],
        )
        denominator_ab = _denominators(
            ea[: sector.nalpha],
            eb[: sector.nbeta],
            ea[sector.nalpha :],
            eb[sector.nbeta :],
        )
        direct_aa, mask_aa = _masked_amplitude(integral_aa, denominator_aa)
        direct_bb, mask_bb = _masked_amplitude(integral_bb, denominator_bb)
        t2ab, mask_ab = _masked_amplitude(integral_ab, denominator_ab)
        t2aa = direct_aa - direct_aa.swapaxes(2, 3)
        t2bb = direct_bb - direct_bb.swapaxes(2, 3)
        terms_aa = 0.25 * t2aa * integral_aa - 0.25 * t2aa * integral_aa.swapaxes(2, 3)
        terms_bb = 0.25 * t2bb * integral_bb - 0.25 * t2bb * integral_bb.swapaxes(2, 3)
        terms_ab = t2ab * integral_ab
        same_energy = float(np.sum(terms_aa) + np.sum(terms_bb))
        opposite_energy = float(np.sum(terms_ab))
        amplitudes = np.concatenate((t2aa.ravel(), t2ab.ravel(), t2bb.ravel()))
        same_amplitudes = np.concatenate((t2aa.ravel(), t2bb.ravel()))
        opposite_amplitudes = t2ab.ravel()
        denominators = [denominator_aa, denominator_ab, denominator_bb]
        masks = [mask_aa, mask_ab, mask_bb]
        energy_terms = [terms_aa, terms_ab, terms_bb]
        pair_energy[: sector.nalpha, : sector.nalpha] += np.sum(terms_aa, axis=(2, 3))
        pair_energy[: sector.nbeta, : sector.nbeta] += np.sum(terms_bb, axis=(2, 3))
        pair_energy[: sector.nalpha, : sector.nbeta] += np.sum(terms_ab, axis=(2, 3))
        t2_for_density = (t2aa, t2ab, t2bb)

    pair_graph = 0.5 * (np.abs(pair_energy) + np.abs(pair_energy.T))
    np.fill_diagonal(pair_graph, 0.0)
    features: dict[str, object] = {
        "mp2_reference": "RMP2" if branch.method == "RHF" else "UMP2",
        "mp2_correlation_energy_hartree": same_energy + opposite_energy,
        "mp2_same_spin_correlation_energy_hartree": same_energy,
        "mp2_opposite_spin_correlation_energy_hartree": opposite_energy,
    }
    features.update(_denominator_features(denominators, masks))
    features.update(_amplitude_summary(amplitudes, "mp2_amplitude"))
    features.update(_amplitude_summary(same_amplitudes, "mp2_same_spin_amplitude"))
    features.update(
        _amplitude_summary(opposite_amplitudes, "mp2_opposite_spin_amplitude")
    )
    features.update(_kappa_features(energy_terms, denominators))
    solver = pyscf_solver_for_branch(data, eri, branch)
    mp_solver = mp.MP2(solver)
    mp_solver.verbose = 0
    features.update(_natural_occupation_features(mp_solver, t2_for_density, data.nelec))
    features.update(_pair_graph_features(pair_graph))
    return MP2Result(features, pair_graph, t2_for_density)
