# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Deterministic selected-state stability analysis for MFPROTO-v1."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
from pyscf import lib
from pyscf.scf import stability
from pyscf.soscf import newton_ah

from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump
from qb_gsee_benchmark.features.mfproto_features import (
    MeanFieldBranch,
    SOLUTION_DENSITY_TOL,
    particle_sector,
    pyscf_solver_for_branch,
    run_mean_field_from_density,
)

STABILITY_RESIDUAL_TOL = 1.0e-7
STABILITY_MAX_SPACE = 80
STABILITY_MAX_CYCLE = 100
STABILITY_LINDEP = 1.0e-14
INSTABILITY_THRESHOLD = -1.0e-5
MARGINAL_ABS_THRESHOLD = 1.0e-5
MAX_FOLLOW_STEPS = 2
EXTERNAL_DIMENSION_CEILING = 250_000
EXTERNAL_ACTION_SECONDS_CEILING = 120.0


@dataclass(frozen=True)
class StabilityRoot:
    applicable: bool
    reason: str | None
    eigenvalue: float | None
    vector: np.ndarray | None
    dimension: int
    hessian_action_seconds: float | None


@dataclass
class StabilityResult:
    initial_branch: MeanFieldBranch
    final_branch: MeanFieldBranch
    internal_roots: list[StabilityRoot]
    follow_outcomes: list[dict[str, object]]
    external_root: StabilityRoot


def _deterministic_starts(hdiag: np.ndarray) -> list[np.ndarray]:
    finite = np.flatnonzero(np.isfinite(hdiag))
    ordered = sorted(finite, key=lambda index: (float(hdiag[index]), int(index)))
    starts = []
    for index in ordered[: min(4, len(ordered))]:
        vector = np.zeros(hdiag.size)
        vector[index] = 1.0
        starts.append(vector)
    return starts


def lowest_davidson_root(
    hop,
    hdiag: np.ndarray,
    *,
    dimension_ceiling: int | None = None,
    action_seconds_ceiling: float | None = None,
) -> StabilityRoot:
    hdiag = np.asarray(hdiag, dtype=float)
    dimension = hdiag.size
    if dimension == 0:
        return StabilityRoot(False, "empty_particle_hole_space", None, None, 0, None)
    if dimension_ceiling is not None and dimension > dimension_ceiling:
        return StabilityRoot(
            False, "external_dimension_ceiling", None, None, dimension, None
        )
    starts = _deterministic_starts(hdiag)
    if not starts:
        return StabilityRoot(
            False, "no_finite_hessian_diagonal", None, None, dimension, None
        )

    started = time.monotonic()
    first_action = np.asarray(hop(starts[0]), dtype=float)
    action_seconds = time.monotonic() - started
    if action_seconds_ceiling is not None and action_seconds > action_seconds_ceiling:
        return StabilityRoot(
            False,
            "external_hessian_action_ceiling",
            None,
            None,
            dimension,
            action_seconds,
        )
    first_start = starts[0]

    def measured_hop(vector: np.ndarray) -> np.ndarray:
        if vector is first_start:
            return first_action
        return np.asarray(hop(vector), dtype=float)

    def precondition(
        residual: np.ndarray, eigenvalue: float, _: np.ndarray
    ) -> np.ndarray:
        denominator = hdiag - eigenvalue
        denominator = denominator.copy()
        denominator[np.abs(denominator) < 1.0e-8] = 1.0e-8
        return residual / denominator

    converged, eigenvalues, vectors = lib.davidson1(
        lambda vectors: [measured_hop(vector) for vector in vectors],
        starts,
        precondition,
        tol=STABILITY_RESIDUAL_TOL,
        tol_residual=STABILITY_RESIDUAL_TOL,
        max_cycle=STABILITY_MAX_CYCLE,
        max_space=STABILITY_MAX_SPACE,
        lindep=STABILITY_LINDEP,
        nroots=1,
        verbose=0,
    )
    eigenvalue = float(eigenvalues[0])
    vector = np.asarray(vectors[0], dtype=float)
    vector /= np.linalg.norm(vector)
    residual_norm = float(np.linalg.norm(measured_hop(vector) - eigenvalue * vector))
    if not bool(converged[0]) or residual_norm > STABILITY_RESIDUAL_TOL:
        return StabilityRoot(
            False,
            "davidson_not_converged",
            None,
            None,
            dimension,
            action_seconds,
        )
    return StabilityRoot(
        True,
        None,
        eigenvalue,
        vector,
        dimension,
        action_seconds,
    )


def _internal_root(
    data: SparseFcidump, eri: np.ndarray, branch: MeanFieldBranch
) -> StabilityRoot:
    solver = pyscf_solver_for_branch(data, eri, branch)
    if branch.method == "RHF":
        _, hop, hdiag = newton_ah.gen_g_hop_rhf(
            solver, solver.mo_coeff, solver.mo_occ, with_symmetry=False
        )
    else:
        _, hop, hdiag = newton_ah.gen_g_hop_uhf(
            solver, solver.mo_coeff, solver.mo_occ, with_symmetry=False
        )
    return lowest_davidson_root(
        lambda vector: 2.0 * np.asarray(hop(vector)).real,
        2.0 * np.asarray(hdiag),
    )


def _follow_density(
    data: SparseFcidump,
    eri: np.ndarray,
    branch: MeanFieldBranch,
    vector: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    solver = pyscf_solver_for_branch(data, eri, branch)
    if branch.method == "RHF":
        rotated = stability._rotate_mo(solver.mo_coeff, solver.mo_occ, vector)
        occupied = rotated[:, : data.nalpha]
        density = occupied @ occupied.T
        return density, density
    nalpha_rotations = data.nalpha * (data.norb - data.nalpha)
    rotated_alpha = stability._rotate_mo(
        solver.mo_coeff[0], solver.mo_occ[0], vector[:nalpha_rotations]
    )
    rotated_beta = stability._rotate_mo(
        solver.mo_coeff[1], solver.mo_occ[1], vector[nalpha_rotations:]
    )
    occupied_alpha = rotated_alpha[:, : data.nalpha]
    occupied_beta = rotated_beta[:, : data.nbeta]
    return occupied_alpha @ occupied_alpha.T, occupied_beta @ occupied_beta.T


def _external_root(
    data: SparseFcidump, eri: np.ndarray, branch: MeanFieldBranch
) -> StabilityRoot:
    solver = pyscf_solver_for_branch(data, eri, branch)
    if branch.method == "RHF":
        _, _, hop, hdiag = stability._gen_hop_rhf_external(solver, with_symmetry=False)
    else:
        _, _, hop, hdiag = stability._gen_hop_uhf_external(solver, with_symmetry=False)
    return lowest_davidson_root(
        hop,
        hdiag,
        dimension_ceiling=EXTERNAL_DIMENSION_CEILING,
        action_seconds_ceiling=EXTERNAL_ACTION_SECONDS_CEILING,
    )


def run_stability(
    data: SparseFcidump, eri: np.ndarray, selected: MeanFieldBranch
) -> StabilityResult:
    """Compute roots, follow at most two internal instabilities, then audit external."""
    particle_sector(data.norb, data.nelec, data.ms2)
    current = selected
    roots = []
    outcomes = []
    seen_densities = [(selected.density_alpha, selected.density_beta)]
    for step in range(MAX_FOLLOW_STEPS + 1):
        root = _internal_root(data, eri, current)
        roots.append(root)
        if (
            not root.applicable
            or root.eigenvalue >= INSTABILITY_THRESHOLD
            or step == MAX_FOLLOW_STEPS
        ):
            break
        spin_density = _follow_density(data, eri, current, root.vector)
        repeated = any(
            np.hypot(
                np.linalg.norm(spin_density[0] - previous[0]),
                np.linalg.norm(spin_density[1] - previous[1]),
            )
            <= SOLUTION_DENSITY_TOL
            for previous in seen_densities
        )
        if repeated:
            outcomes.append(
                {"step": step + 1, "status": "repeated_density", "converged": False}
            )
            break
        followed = run_mean_field_from_density(
            data,
            eri,
            current.method,
            spin_density,
            guess=f"{selected.guess}_stability_{step + 1}",
        )
        outcomes.append(
            {
                "step": step + 1,
                "status": "converged" if followed.converged else "scf_failed",
                "converged": followed.converged,
                "energy_hartree": followed.energy,
            }
        )
        if not followed.converged:
            break
        current = followed
        seen_densities.append((current.density_alpha, current.density_beta))
    external = _external_root(data, eri, current)
    return StabilityResult(selected, current, roots, outcomes, external)


def stability_feature_values(result: StabilityResult) -> dict[str, object]:
    initial = result.internal_roots[0]
    final = result.internal_roots[-1]
    external = result.external_root
    return {
        "mf_stability_internal_applicable": initial.applicable,
        "mf_stability_internal_reason": initial.reason,
        "mf_stability_internal_initial_eigenvalue_hartree": initial.eigenvalue,
        "mf_stability_internal_final_eigenvalue_hartree": final.eigenvalue,
        "mf_stability_internal_marginal": (
            None
            if final.eigenvalue is None
            else abs(final.eigenvalue) <= MARGINAL_ABS_THRESHOLD
        ),
        "mf_stability_follow_count": len(result.follow_outcomes),
        "mf_stability_external_applicable": external.applicable,
        "mf_stability_external_reason": external.reason,
        "mf_stability_external_eigenvalue_hartree": external.eigenvalue,
        "mf_stability_external_dimension": external.dimension,
        "mf_stability_external_dimension_ceiling": EXTERNAL_DIMENSION_CEILING,
        "mf_stability_external_action_seconds": external.hessian_action_seconds,
        "mf_stability_external_action_seconds_ceiling": EXTERNAL_ACTION_SECONDS_CEILING,
    }
