# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Deterministic numerical primitives for G40 MFPROTO-v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump
import numpy as np

MFPROTO_VERSION = "g40_p2_mfproto_v2"
DEGENERACY_ENTER_ATOL = 1.0e-10
DEGENERACY_ATOL = 1.0e-8
PROJECTED_INDEX_DEGENERACY_ATOL = 1.0e-10
COORDINATE_PIN_TOL = 1.0e-12
FERMI_RESIDUAL_TOL = 1.0e-13
FERMI_BRACKET_TOL = 1.0e-13
THERMAL_KT_GRID = (0.025, 0.1, 0.25)
DOS_ETA_GRID = (0.05, 0.2)
SCF_ENERGY_TOL = 1.0e-9
SCF_GRADIENT_TOL = 1.0e-6
SCF_MAX_CYCLE = 150
SOLUTION_ENERGY_TOL = 1.0e-7
SOLUTION_DENSITY_TOL = 1.0e-4
SELECTION_ENERGY_TIE_TOL = 1.0e-10
GUESS_ORDER = ("G1", "G2", "G3", "G4")
METHOD_ORDER = ("RHF", "UHF")
IPR_WINDOW_GRID = (0.1, 0.5)


@dataclass(frozen=True)
class CanonicalSpectrum:
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    minimum_adjacent_split: float | None
    degenerate_subspace_count: int
    projected_index_tied_subspace_count: int
    hysteresis_band_split_count: int


@dataclass(frozen=True)
class ParticleSector:
    norb: int
    nelec: int
    ms2: int
    nalpha: int
    nbeta: int


@dataclass
class MeanFieldBranch:
    method: str
    guess: str
    converged: bool
    fallback_used: bool
    engine_converged: bool
    energy: float | None
    final_delta_energy: float | None
    maximum_ov_gradient: float | None
    density_alpha: np.ndarray | None
    density_beta: np.ndarray | None
    fock_alpha: np.ndarray | None
    fock_beta: np.ndarray | None
    orbitals_alpha: np.ndarray | None
    orbitals_beta: np.ndarray | None
    energies_alpha: np.ndarray | None
    energies_beta: np.ndarray | None
    fock_canonical_audit_alpha: dict[str, float | int | None] | None
    fock_canonical_audit_beta: dict[str, float | int | None] | None
    s2: float | None
    cycles: int
    error_type: str | None = None
    error_message: str | None = None


@dataclass
class MeanFieldResult:
    sector: ParticleSector
    branches: list[MeanFieldBranch]
    components: list[list[int]]
    selected_branch_index: int | None
    core_spectrum: CanonicalSpectrum
    tie_audit: dict[str, float | int | bool | str | None]

    @property
    def selected(self) -> MeanFieldBranch | None:
        if self.selected_branch_index is None:
            return None
        return self.branches[self.selected_branch_index]


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


def _coordinate_pinned_basis(
    subspace: np.ndarray, *, tolerance: float = COORDINATE_PIN_TOL
) -> np.ndarray:
    """Build a basis from coordinate projections, independent of input rotation."""
    subspace = np.asarray(subspace, dtype=float)
    dimension = subspace.shape[1]
    projector = subspace @ subspace.T
    basis: list[np.ndarray] = []
    for index in range(projector.shape[0]):
        vector = projector[:, index].copy()
        for _ in range(2):
            for prior in basis:
                vector -= np.dot(prior, vector) * prior
        norm = float(np.linalg.norm(vector))
        if norm <= tolerance:
            continue
        vector /= norm
        pivot = int(np.flatnonzero(np.abs(vector) == np.max(np.abs(vector)))[0])
        if vector[pivot] < 0.0:
            vector *= -1.0
        basis.append(vector)
        if len(basis) == dimension:
            break
    if len(basis) != dimension:
        raise RuntimeError("coordinate pin did not span the degenerate subspace")
    return np.column_stack(basis)


def _spectrum_audit(spectrum: CanonicalSpectrum) -> dict[str, float | int | None]:
    return {
        "minimum_adjacent_split": spectrum.minimum_adjacent_split,
        "degenerate_subspace_count": spectrum.degenerate_subspace_count,
        "projected_index_tied_subspace_count": (
            spectrum.projected_index_tied_subspace_count
        ),
        "hysteresis_band_split_count": spectrum.hysteresis_band_split_count,
    }


def canonical_eigh(
    matrix: np.ndarray, *, degeneracy_atol: float = DEGENERACY_ATOL
) -> CanonicalSpectrum:
    """Diagonalize with recursive projected-index and coordinate tie pins."""
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
    projected_tie_count = 0
    hysteresis_band_count = 0
    for group in groups:
        if group.stop - group.start < 2:
            continue
        degenerate_count += 1
        splits = np.abs(np.diff(values[group]))
        hysteresis_band_count += int(
            np.count_nonzero(
                (splits > DEGENERACY_ENTER_ATOL) & (splits <= degeneracy_atol)
            )
        )
        subspace = vectors[:, group]
        projected = subspace.T @ (shipped_index[:, None] * subspace)
        projected_values, rotation = np.linalg.eigh(projected)
        resolved = subspace @ rotation
        for projected_group in _degenerate_groups(
            projected_values, PROJECTED_INDEX_DEGENERACY_ATOL
        ):
            if projected_group.stop - projected_group.start < 2:
                continue
            projected_tie_count += 1
            resolved[:, projected_group] = _coordinate_pinned_basis(
                resolved[:, projected_group]
            )
        vectors[:, group] = resolved
    vectors = _fix_column_signs(vectors)
    minimum_split = None if values.size < 2 else float(np.min(np.abs(np.diff(values))))
    return CanonicalSpectrum(
        eigenvalues=values,
        eigenvectors=vectors,
        minimum_adjacent_split=minimum_split,
        degenerate_subspace_count=degenerate_count,
        projected_index_tied_subspace_count=projected_tie_count,
        hysteresis_band_split_count=hysteresis_band_count,
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
    h1: np.ndarray,
    nelec: int,
    ms2: int,
    *,
    core_spectrum: CanonicalSpectrum | None = None,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Return G1--G4 alpha/beta densities in shipped-orbital coordinates."""
    h1 = np.asarray(h1, dtype=float)
    sector = particle_sector(h1.shape[0], nelec, ms2)
    core = canonical_eigh(h1) if core_spectrum is None else core_spectrum
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
) -> dict[str, float | bool | None | str]:
    """Compute one-spin gap, thermal, DOS, and projector-IPR primitives."""
    values = np.asarray(eigenvalues, dtype=float)
    vectors = np.asarray(eigenvectors, dtype=float)
    if vectors.shape != (values.size, values.size):
        raise ValueError("eigenvector dimensions do not match eigenvalues")
    if particles <= 0 or particles >= values.size:
        result: dict[str, float | bool | None | str] = {
            "applicable": False,
            "reason": "empty_or_full_spin_sector",
            "gap": None,
            "center": None,
            "edge_degenerate": None,
        }
        for kt in THERMAL_KT_GRID:
            result[f"thermal_active_fraction_kt_{kt:g}"] = None
        for eta in DOS_ETA_GRID:
            result[f"dos_total_eta_{eta:g}"] = None
            result[f"dos_per_orbital_eta_{eta:g}"] = None
        for width in IPR_WINDOW_GRID:
            result[f"ipr_window_orbital_count_{width:g}"] = 0
            result[f"ipr_window_{width:g}_applicable"] = False
            result[f"ipr_window_{width:g}_reason"] = "empty_or_full_spin_sector"
            result[f"ipr_window_{width:g}"] = None
        return result
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
        result[f"ipr_window_{width:g}_applicable"] = rank > 0
        result[f"ipr_window_{width:g}_reason"] = (
            None if rank > 0 else "empty_spectral_projector"
        )
        result[f"ipr_window_{width:g}"] = (
            None
            if rank == 0
            else float(np.sum(np.sum(vectors[:, selected] ** 2, axis=1) ** 2) / rank**2)
        )
    return result


def _build_pyscf_mean_field(data: SparseFcidump, eri: np.ndarray, method: str) -> Any:
    from pyscf import gto, scf

    mol = gto.M()
    mol.nelectron = data.nelec
    mol.spin = data.ms2
    mol.nao = data.norb
    mol.incore_anyway = True
    mol.verbose = 0
    mol.enuc = data.ecore
    mf = scf.RHF(mol) if method == "RHF" else scf.UHF(mol)
    mf.verbose = 0
    mf.max_cycle = SCF_MAX_CYCLE
    mf.conv_tol = SCF_ENERGY_TOL
    mf.conv_tol_grad = SCF_GRADIENT_TOL
    hcore = data.h1 if method == "RHF" else np.asarray((data.h1, data.h1))
    mf.get_hcore = lambda *args: hcore
    mf.get_ovlp = lambda *args: np.eye(data.norb)
    mf._eri = eri
    return mf


def configure_newton_fallback(solver: Any) -> Any:
    """Apply every frozen MFPROTO-v2 augmented-Hessian control."""
    controls = {
        "max_cycle": 50,
        "max_cycle_inner": 12,
        "max_stepsize": 0.05,
        "ah_start_cycle": 1,
        "ah_start_tol": 1.0e9,
        "ah_conv_tol": 1.0e-12,
        "ah_lindep": 1.0e-14,
        "ah_max_cycle": 40,
        "ah_level_shift": 0.0,
        "ah_grad_trust_region": 2.5,
        "kf_interval": 4,
        "kf_trust_region": 5,
    }
    for name, value in controls.items():
        if not hasattr(solver, name):
            raise AttributeError(f"PySCF Newton solver lacks frozen control {name}")
        setattr(solver, name, value)
    solver.conv_tol = SCF_ENERGY_TOL
    solver.conv_tol_grad = SCF_GRADIENT_TOL
    return solver


def _kernel_with_history(
    solver: Any,
    *,
    dm0: np.ndarray | tuple[np.ndarray, np.ndarray] | None = None,
    mo_coeff: Any = None,
    mo_occ: Any = None,
) -> list[float]:
    energy_changes: list[float] = []

    def callback(environment: dict[str, Any]) -> None:
        energy = environment.get("e_tot")
        previous = environment.get("last_hf_e")
        if (
            energy is not None
            and previous is not None
            and np.isfinite(energy)
            and np.isfinite(previous)
        ):
            energy_changes.append(abs(float(energy) - float(previous)))

    solver.callback = callback
    if mo_coeff is not None:
        solver.kernel(mo_coeff=mo_coeff, mo_occ=mo_occ)
    else:
        solver.kernel(dm0=dm0)
    return energy_changes


def _canonical_state(
    solver: Any, method: str, sector: ParticleSector
) -> dict[str, Any]:
    """Canonicalize one frozen Fock classification and evaluate that state."""
    original_dm = solver.make_rdm1(solver.mo_coeff, solver.mo_occ)
    original_fock = solver.get_fock(dm=original_dm)
    if method == "RHF":
        spectrum = canonical_eigh(original_fock)
        orbitals = spectrum.eigenvectors
        occupations = np.zeros(sector.norb)
        occupations[: sector.nalpha] = 2.0
        density = occupation_density(orbitals, occupations)
        evaluation_fock = solver.get_fock(dm=density)
        # PySCF RHF get_grad returns 2 F_ai; normalize both methods to |F_ai|.
        gradient = 0.5 * solver.get_grad(orbitals, occupations, evaluation_fock)
        veff = solver.get_veff(dm=density)
        energy = float(solver.energy_tot(dm=density, h1e=data_hcore(solver), vhf=veff))
        return {
            "energy": energy,
            "gradient": float(np.max(np.abs(gradient), initial=0.0)),
            "density_alpha": 0.5 * density,
            "density_beta": 0.5 * density,
            "fock_alpha": original_fock,
            "fock_beta": original_fock,
            "orbitals_alpha": orbitals,
            "orbitals_beta": orbitals,
            "energies_alpha": spectrum.eigenvalues,
            "energies_beta": spectrum.eigenvalues,
            "fock_canonical_audit_alpha": _spectrum_audit(spectrum),
            "fock_canonical_audit_beta": _spectrum_audit(spectrum),
            "s2": 0.0,
        }

    original_fock_alpha, original_fock_beta = original_fock
    spectrum_alpha = canonical_eigh(original_fock_alpha)
    spectrum_beta = canonical_eigh(original_fock_beta)
    occupation_alpha = np.zeros(sector.norb)
    occupation_beta = np.zeros(sector.norb)
    occupation_alpha[: sector.nalpha] = 1.0
    occupation_beta[: sector.nbeta] = 1.0
    density_alpha = occupation_density(spectrum_alpha.eigenvectors, occupation_alpha)
    density_beta = occupation_density(spectrum_beta.eigenvectors, occupation_beta)
    density = np.asarray((density_alpha, density_beta))
    evaluation_fock = solver.get_fock(dm=density)
    gradient = solver.get_grad(
        (spectrum_alpha.eigenvectors, spectrum_beta.eigenvectors),
        (occupation_alpha, occupation_beta),
        evaluation_fock,
    )
    veff = solver.get_veff(dm=density)
    energy = float(solver.energy_tot(dm=density, h1e=data_hcore(solver), vhf=veff))
    occupied = (
        spectrum_alpha.eigenvectors[:, : sector.nalpha],
        spectrum_beta.eigenvectors[:, : sector.nbeta],
    )
    s2 = float(solver.spin_square(occupied, np.eye(sector.norb))[0])
    return {
        "energy": energy,
        "gradient": float(np.max(np.abs(gradient), initial=0.0)),
        "density_alpha": density_alpha,
        "density_beta": density_beta,
        "fock_alpha": original_fock_alpha,
        "fock_beta": original_fock_beta,
        "orbitals_alpha": spectrum_alpha.eigenvectors,
        "orbitals_beta": spectrum_beta.eigenvectors,
        "energies_alpha": spectrum_alpha.eigenvalues,
        "energies_beta": spectrum_beta.eigenvalues,
        "fock_canonical_audit_alpha": _spectrum_audit(spectrum_alpha),
        "fock_canonical_audit_beta": _spectrum_audit(spectrum_beta),
        "s2": s2,
    }


def data_hcore(solver: Any) -> Any:
    """Return hcore with the shape expected by RHF or UHF energy_tot."""
    return solver.get_hcore(solver.mol)


def _evaluate_branch(
    solver: Any,
    method: str,
    guess: str,
    sector: ParticleSector,
    history: list[float],
    *,
    fallback_used: bool,
) -> MeanFieldBranch:
    state = _canonical_state(solver, method, sector)
    iterative_delta = history[-1] if history else float("inf")
    canonical_delta = abs(state["energy"] - float(solver.e_tot))
    final_delta = max(iterative_delta, canonical_delta)
    gradient = state["gradient"]
    converged = bool(final_delta < SCF_ENERGY_TOL and gradient < SCF_GRADIENT_TOL)
    return MeanFieldBranch(
        method=method,
        guess=guess,
        converged=converged,
        fallback_used=fallback_used,
        engine_converged=bool(solver.converged),
        energy=state["energy"],
        final_delta_energy=float(final_delta),
        maximum_ov_gradient=gradient,
        density_alpha=state["density_alpha"],
        density_beta=state["density_beta"],
        fock_alpha=state["fock_alpha"],
        fock_beta=state["fock_beta"],
        orbitals_alpha=state["orbitals_alpha"],
        orbitals_beta=state["orbitals_beta"],
        energies_alpha=state["energies_alpha"],
        energies_beta=state["energies_beta"],
        fock_canonical_audit_alpha=state["fock_canonical_audit_alpha"],
        fock_canonical_audit_beta=state["fock_canonical_audit_beta"],
        s2=state["s2"],
        cycles=int(getattr(solver, "cycles", len(history))),
    )


def _failed_branch(method: str, guess: str, exc: Exception) -> MeanFieldBranch:
    return MeanFieldBranch(
        method=method,
        guess=guess,
        converged=False,
        fallback_used=False,
        engine_converged=False,
        energy=None,
        final_delta_energy=None,
        maximum_ov_gradient=None,
        density_alpha=None,
        density_beta=None,
        fock_alpha=None,
        fock_beta=None,
        orbitals_alpha=None,
        orbitals_beta=None,
        energies_alpha=None,
        energies_beta=None,
        fock_canonical_audit_alpha=None,
        fock_canonical_audit_beta=None,
        s2=None,
        cycles=0,
        error_type=type(exc).__name__,
        error_message=str(exc),
    )


def _run_mean_field_branch(
    data: SparseFcidump,
    eri: np.ndarray,
    method: str,
    guess: str,
    spin_density: tuple[np.ndarray, np.ndarray],
    sector: ParticleSector,
) -> MeanFieldBranch:
    try:
        solver = _build_pyscf_mean_field(data, eri, method)
        dm0 = spin_density[0] + spin_density[1] if method == "RHF" else spin_density
        history = _kernel_with_history(solver, dm0=dm0)
        result = _evaluate_branch(
            solver, method, guess, sector, history, fallback_used=False
        )
        if result.converged:
            return result
        second_order = configure_newton_fallback(solver.newton())
        history = _kernel_with_history(
            second_order, mo_coeff=solver.mo_coeff, mo_occ=solver.mo_occ
        )
        return _evaluate_branch(
            second_order, method, guess, sector, history, fallback_used=True
        )
    except Exception as exc:
        return _failed_branch(method, guess, exc)


def spin_density_distance(left: MeanFieldBranch, right: MeanFieldBranch) -> float:
    if left.density_alpha is None or right.density_alpha is None:
        return float("inf")
    alpha = np.linalg.norm(left.density_alpha - right.density_alpha)
    beta = np.linalg.norm(left.density_beta - right.density_beta)
    return float(np.hypot(alpha, beta))


def _stationary_components(branches: list[MeanFieldBranch]) -> list[list[int]]:
    eligible = [index for index, branch in enumerate(branches) if branch.converged]
    parents = {index: index for index in eligible}

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for position, left in enumerate(eligible):
        for right in eligible[position + 1 :]:
            if (
                abs(branches[left].energy - branches[right].energy)
                <= SOLUTION_ENERGY_TOL
                and spin_density_distance(branches[left], branches[right])
                <= SOLUTION_DENSITY_TOL
            ):
                union(left, right)
    groups: dict[int, list[int]] = {}
    for index in eligible:
        groups.setdefault(find(index), []).append(index)
    return sorted(
        (sorted(group) for group in groups.values()), key=lambda group: group[0]
    )


def _select_branch(indices: list[int], branches: list[MeanFieldBranch]) -> int:
    minimum_energy = min(float(branches[index].energy) for index in indices)
    tied = [
        index
        for index in indices
        if abs(float(branches[index].energy) - minimum_energy)
        <= SELECTION_ENERGY_TIE_TOL
    ]
    return min(
        tied,
        key=lambda index: (
            GUESS_ORDER.index(branches[index].guess),
            METHOD_ORDER.index(branches[index].method),
        ),
    )


def _ordered_diagonal_boundary_tie(
    diagonal: np.ndarray, order: np.ndarray, particles: int
) -> bool:
    if particles <= 0 or particles >= order.size:
        return False
    return bool(
        abs(diagonal[order[particles]] - diagonal[order[particles - 1]])
        <= DEGENERACY_ATOL
    )


def run_mean_field(
    data: SparseFcidump, eri: np.ndarray | None = None
) -> MeanFieldResult:
    """Run the complete MFPROTO-v2 RHF/UHF x G1--G4 branch panel."""
    sector = particle_sector(data.norb, data.nelec, data.ms2)
    core = canonical_eigh(data.h1)
    guesses = initial_spin_density_guesses(
        data.h1, data.nelec, data.ms2, core_spectrum=core
    )
    if eri is None:
        eri = data.dense_eri()
    methods = METHOD_ORDER if data.ms2 == 0 else ("UHF",)
    branches = [
        _run_mean_field_branch(data, eri, method, guess, guesses[guess], sector)
        for method in methods
        for guess in GUESS_ORDER
    ]
    components = _stationary_components(branches)
    representatives = [_select_branch(group, branches) for group in components]
    selected_index = (
        None if not representatives else _select_branch(representatives, branches)
    )

    diagonal = np.diag(data.h1)
    shipped = np.arange(data.norb)
    alpha_alternating = np.array(sorted(range(data.norb), key=lambda i: (i % 2, i)))
    beta_alternating = np.array(
        sorted(range(data.norb), key=lambda i: ((i + 1) % 2, i))
    )
    tie_audit: dict[str, float | int | bool | str | None] = {
        "core_minimum_adjacent_split": core.minimum_adjacent_split,
        "core_degenerate_subspace_count": core.degenerate_subspace_count,
        "core_projected_index_tied_subspace_count": (
            core.projected_index_tied_subspace_count
        ),
        "core_hysteresis_band_split_count": core.hysteresis_band_split_count,
        "g1_alpha_boundary_tie": occupation_boundary_tie(
            core.eigenvalues, sector.nalpha
        ),
        "g1_beta_boundary_tie": occupation_boundary_tie(core.eigenvalues, sector.nbeta),
        "g2_alpha_boundary_tie": _ordered_diagonal_boundary_tie(
            diagonal, shipped, sector.nalpha
        ),
        "g2_beta_boundary_tie": _ordered_diagonal_boundary_tie(
            diagonal, shipped, sector.nbeta
        ),
        "g3_alpha_boundary_tie": _ordered_diagonal_boundary_tie(
            diagonal, alpha_alternating, sector.nalpha
        ),
        "g3_beta_boundary_tie": _ordered_diagonal_boundary_tie(
            diagonal, beta_alternating, sector.nbeta
        ),
    }
    selected = None if selected_index is None else branches[selected_index]
    for spin, particles in (
        ("alpha", sector.nalpha),
        ("beta", sector.nbeta),
    ):
        audit = (
            None
            if selected is None
            else getattr(selected, f"fock_canonical_audit_{spin}")
        )
        for key in (
            "minimum_adjacent_split",
            "degenerate_subspace_count",
            "projected_index_tied_subspace_count",
            "hysteresis_band_split_count",
        ):
            tie_audit[f"selected_fock_{spin}_{key}"] = (
                None if audit is None else audit[key]
            )
        energies = None if selected is None else getattr(selected, f"energies_{spin}")
        tie_audit[f"selected_fock_{spin}_boundary_tie"] = (
            None if energies is None else occupation_boundary_tie(energies, particles)
        )
    tie_audit["selection_energy_tie_tolerance_hartree"] = SELECTION_ENERGY_TIE_TOL
    tie_audit["selection_method_order"] = ">".join(METHOD_ORDER)

    return MeanFieldResult(
        sector=sector,
        branches=branches,
        components=components,
        selected_branch_index=selected_index,
        core_spectrum=core,
        tie_audit=tie_audit,
    )


def mean_field_feature_values(result: MeanFieldResult) -> dict[str, Any]:
    """Flatten the stationary-state and one-body panels for corpus states."""
    selected = result.selected
    converged = [branch for branch in result.branches if branch.converged]
    features: dict[str, Any] = {
        "mfproto_features_version": MFPROTO_VERSION,
        "mf_branch_count": len(result.branches),
        "mf_converged_branch_count": len(converged),
        "mf_distinct_solution_count": len(result.components),
        "mf_solution_energy_spread_hartree": (
            None
            if not converged
            else float(
                max(branch.energy for branch in converged)
                - min(branch.energy for branch in converged)
            )
        ),
        "mf_selected_applicable": selected is not None,
        "mf_selected_reason": (
            None if selected is not None else "no_converged_scf_branch"
        ),
        "mf_selected_method": None if selected is None else selected.method,
        "mf_selected_guess": None if selected is None else selected.guess,
        "mf_selected_energy_hartree": None if selected is None else selected.energy,
        "mf_selected_s2": None if selected is None else selected.s2,
    }
    features["mf_solution_energy_spread_per_electron_hartree"] = (
        None
        if features["mf_solution_energy_spread_hartree"] is None
        else features["mf_solution_energy_spread_hartree"] / result.sector.nelec
    )
    features.update({f"mf_tie_{key}": value for key, value in result.tie_audit.items()})

    method_energies = {
        method: [branch.energy for branch in converged if branch.method == method]
        for method in ("RHF", "UHF")
    }
    for method, energies in method_energies.items():
        features[f"mf_lowest_{method.lower()}_energy_hartree"] = (
            None if not energies else float(min(energies))
        )
    if method_energies["RHF"] and method_energies["UHF"]:
        features["mf_symmetry_breaking_applicable"] = True
        features["mf_symmetry_breaking_reason"] = None
        delta = min(method_energies["RHF"]) - min(method_energies["UHF"])
        features["mf_symmetry_breaking_energy_hartree"] = float(delta)
        features["mf_symmetry_breaking_energy_per_electron"] = float(
            delta / result.sector.nelec
        )
    else:
        features["mf_symmetry_breaking_energy_hartree"] = None
        features["mf_symmetry_breaking_applicable"] = False
        features["mf_symmetry_breaking_reason"] = (
            "ms2_nonzero" if result.sector.ms2 != 0 else "missing_converged_rhf_or_uhf"
        )
        features["mf_symmetry_breaking_energy_per_electron"] = None

    core_panels = {
        "alpha": spectral_panel(
            result.core_spectrum.eigenvalues,
            result.core_spectrum.eigenvectors,
            result.sector.nalpha,
        ),
        "beta": spectral_panel(
            result.core_spectrum.eigenvalues,
            result.core_spectrum.eigenvectors,
            result.sector.nbeta,
        ),
    }
    for spin, panel in core_panels.items():
        features[f"mf_core_gap_{spin}_applicable"] = panel["applicable"]
        features[f"mf_core_gap_{spin}_reason"] = panel["reason"]
        features[f"mf_core_gap_{spin}_hartree"] = panel["gap"]
    applicable_core_gaps = [
        panel["gap"] for panel in core_panels.values() if panel["applicable"]
    ]
    features["mf_core_gap_min_hartree"] = (
        None if not applicable_core_gaps else float(min(applicable_core_gaps))
    )
    features["mf_core_gap_min_applicable"] = bool(applicable_core_gaps)
    features["mf_core_gap_min_reason"] = (
        None if applicable_core_gaps else "no_applicable_spin_gap"
    )
    if selected is None:
        return features

    selected_panels = {}
    for spin, particles in (
        ("alpha", result.sector.nalpha),
        ("beta", result.sector.nbeta),
    ):
        panel = spectral_panel(
            getattr(selected, f"energies_{spin}"),
            getattr(selected, f"orbitals_{spin}"),
            particles,
        )
        selected_panels[spin] = panel
        for key, value in panel.items():
            output_key = {
                "gap": "gap_hartree",
                "center": "center_hartree",
            }.get(key, key)
            features[f"mf_selected_fock_{spin}_{output_key}"] = value
    applicable_fock_gaps = [
        panel["gap"] for panel in selected_panels.values() if panel["applicable"]
    ]
    features["mf_selected_fock_gap_min_hartree"] = (
        None if not applicable_fock_gaps else float(min(applicable_fock_gaps))
    )
    features["mf_selected_fock_gap_min_applicable"] = bool(applicable_fock_gaps)
    features["mf_selected_fock_gap_min_reason"] = (
        None if applicable_fock_gaps else "no_applicable_spin_gap"
    )
    for label in ("alpha", "beta", "min"):
        core_gap = (
            features["mf_core_gap_min_hartree"]
            if label == "min"
            else core_panels[label]["gap"]
        )
        selected_gap = (
            features["mf_selected_fock_gap_min_hartree"]
            if label == "min"
            else selected_panels[label]["gap"]
        )
        applicable = core_gap is not None and selected_gap is not None
        features[f"mf_gap_mismatch_{label}_applicable"] = applicable
        features[f"mf_gap_mismatch_{label}_reason"] = (
            None if applicable else "core_or_selected_fock_gap_not_applicable"
        )
        features[f"mf_gap_mismatch_{label}_hartree"] = (
            abs(float(selected_gap) - float(core_gap)) if applicable else None
        )
    return features


def pyscf_solver_for_branch(
    data: SparseFcidump, eri: np.ndarray, branch: MeanFieldBranch
) -> Any:
    """Reconstruct a PySCF object at a canonical converged branch."""
    if not branch.converged:
        raise ValueError("cannot reconstruct an unconverged branch")
    solver = _build_pyscf_mean_field(data, eri, branch.method)
    if branch.method == "RHF":
        occupations = np.zeros(data.norb)
        occupations[: data.nalpha] = 2.0
        solver.mo_coeff = branch.orbitals_alpha
        solver.mo_energy = branch.energies_alpha
        solver.mo_occ = occupations
    else:
        occupation_alpha = np.zeros(data.norb)
        occupation_beta = np.zeros(data.norb)
        occupation_alpha[: data.nalpha] = 1.0
        occupation_beta[: data.nbeta] = 1.0
        solver.mo_coeff = np.asarray((branch.orbitals_alpha, branch.orbitals_beta))
        solver.mo_energy = np.asarray((branch.energies_alpha, branch.energies_beta))
        solver.mo_occ = np.asarray((occupation_alpha, occupation_beta))
    solver.e_tot = branch.energy
    solver.converged = True
    return solver


def run_mean_field_from_density(
    data: SparseFcidump,
    eri: np.ndarray,
    method: str,
    spin_density: tuple[np.ndarray, np.ndarray],
    *,
    guess: str,
) -> MeanFieldBranch:
    """Apply the frozen primary-plus-fallback protocol to a followed density."""
    sector = particle_sector(data.norb, data.nelec, data.ms2)
    return _run_mean_field_branch(data, eri, method, guess, spin_density, sector)
