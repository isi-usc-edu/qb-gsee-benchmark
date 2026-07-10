#!/usr/bin/env python3
"""Generate the project-owned G-30 all-trans polyene FCIDUMP ladder."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import platform
from pathlib import Path
from typing import Any

for _name in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_name, "1")

import numpy as np
import pyscf
from pyscf import ao2mo, fci, gto, lib, scf
from pyscf.tools import fcidump

MEMBERS = (4, 8, 12, 16, 24)
BASIS = "sto-3g"
CC_DOUBLE_ANGSTROM = 1.3693
CC_SINGLE_ANGSTROM = 1.4244
CH_ANGSTROM = 1.0820
BOND_ANGLE_DEGREES = 120.0
FCIDUMP_TOL = 1.0e-14
SOURCE_URL = "https://arxiv.org/abs/cond-mat/0606115"
SOURCE_DOI = "https://doi.org/10.1063/1.2345196"

# Hachmann et al. Table II. These rounded historical values are cross-checks,
# never references for the project-owned Hamiltonians.
HISTORICAL = {
    4: {"rhf_total": -153.006364, "active_correlation": -0.091502},
    8: {"rhf_total": -304.889389, "active_correlation": -0.177127},
    12: {"rhf_total": -456.773412, "active_correlation": -0.262297},
    16: {"rhf_total": -608.657556, "active_correlation": -0.347403},
    24: {"rhf_total": -912.425883, "active_correlation": -0.517591},
}


def digest(path: Path, algorithm: str) -> str:
    value = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while block := handle.read(8 * 1024 * 1024):
            value.update(block)
    return value.hexdigest()


def deterministic_gzip(source: Path, target: Path) -> None:
    with source.open("rb") as src, target.open("wb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9
        ) as dst:
            while block := src.read(8 * 1024 * 1024):
                dst.write(block)


def rotate_xy(vector: np.ndarray, degrees: float) -> np.ndarray:
    angle = math.radians(degrees)
    rotation = np.asarray(
        [[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]]
    )
    return rotation @ vector


def polyene_geometry(k: int) -> list[tuple[str, tuple[float, float, float]]]:
    """Return a planar all-trans C_k H_(k+2) geometry in Angstrom."""
    if k not in MEMBERS:
        raise ValueError(f"k must be one of {MEMBERS}; got {k}")

    carbons = [np.zeros(2)]
    for bond_index in range(k - 1):
        length = CC_DOUBLE_ANGSTROM if bond_index % 2 == 0 else CC_SINGLE_ANGSTROM
        direction = 0.0 if bond_index % 2 == 0 else 60.0
        step = length * np.asarray(
            [math.cos(math.radians(direction)), math.sin(math.radians(direction))]
        )
        carbons.append(carbons[-1] + step)

    hydrogens: list[np.ndarray] = []
    first_bond = carbons[1] - carbons[0]
    first_bond /= np.linalg.norm(first_bond)
    hydrogens.extend(
        carbons[0] + CH_ANGSTROM * rotate_xy(first_bond, angle)
        for angle in (BOND_ANGLE_DEGREES, -BOND_ANGLE_DEGREES)
    )

    for index in range(1, k - 1):
        to_left = carbons[index - 1] - carbons[index]
        to_right = carbons[index + 1] - carbons[index]
        to_left /= np.linalg.norm(to_left)
        to_right /= np.linalg.norm(to_right)
        direction = -(to_left + to_right)
        direction /= np.linalg.norm(direction)
        hydrogens.append(carbons[index] + CH_ANGSTROM * direction)

    last_bond = carbons[-2] - carbons[-1]
    last_bond /= np.linalg.norm(last_bond)
    hydrogens.extend(
        carbons[-1] + CH_ANGSTROM * rotate_xy(last_bond, angle)
        for angle in (BOND_ANGLE_DEGREES, -BOND_ANGLE_DEGREES)
    )

    atoms = [("C", (float(x), float(y), 0.0)) for x, y in carbons]
    atoms.extend(("H", (float(x), float(y), 0.0)) for x, y in hydrogens)
    if len(atoms) != 2 * k + 2:
        raise AssertionError(f"C{k}H{k + 2} atom count is inconsistent")
    return atoms


def write_xyz(path: Path, atoms: list[tuple[str, tuple[float, float, float]]], k: int) -> None:
    lines = [str(len(atoms)), f"G-30 all-trans C{k}H{k + 2}; Hachmann-2006 Figure-2 geometry"]
    lines.extend(
        f"{symbol:<2s} {x: .12f} {y: .12f} {z: .12f}"
        for symbol, (x, y, z) in atoms
    )
    path.write_text("\n".join(lines) + "\n")


def converged_rhf(molecule: gto.Mole) -> scf.hf.RHF:
    mean_field = scf.RHF(molecule)
    mean_field.conv_tol = 1.0e-12
    mean_field.max_cycle = 200
    mean_field.kernel()
    if not mean_field.converged:
        mean_field = mean_field.newton()
        mean_field.conv_tol = 1.0e-12
        mean_field.max_cycle = 100
        mean_field.kernel()
    if not mean_field.converged:
        raise RuntimeError("RHF did not converge")
    return mean_field


def symmetric_pz_orbitals(
    molecule: gto.Mole, overlap: np.ndarray
) -> tuple[np.ndarray, list[int], np.ndarray]:
    labels = molecule.ao_labels()
    pz_indices = [
        index
        for index, label in enumerate(labels)
        if " C " in f" {label} " and label.strip().endswith("2pz")
    ]
    k = sum(1 for symbol in molecule.elements if symbol == "C")
    if len(pz_indices) != k:
        raise RuntimeError(
            f"expected {k} carbon 2pz AOs, found {len(pz_indices)}: {pz_indices}"
        )
    selector = np.eye(molecule.nao_nr())[:, pz_indices]
    pz_overlap = selector.T @ overlap @ selector
    eigenvalues, eigenvectors = np.linalg.eigh(pz_overlap)
    if float(np.min(eigenvalues)) <= 1.0e-10:
        raise RuntimeError(f"carbon pz overlap is singular: {eigenvalues}")
    inverse_sqrt = (
        eigenvectors @ np.diag(eigenvalues ** -0.5) @ eigenvectors.T
    )
    active = selector @ inverse_sqrt
    return active, pz_indices, eigenvalues


def frozen_core_orbitals(
    mean_field: scf.hf.RHF,
    active: np.ndarray,
    overlap: np.ndarray,
    k: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    occupied = np.asarray(mean_field.mo_coeff)[:, np.asarray(mean_field.mo_occ) > 0]
    active_weights = np.sum((active.T @ overlap @ occupied) ** 2, axis=0)
    pi_count = k // 2
    pi_indices = np.argsort(active_weights)[-pi_count:]
    core_indices = np.asarray(
        [index for index in range(occupied.shape[1]) if index not in set(pi_indices)]
    )
    if len(core_indices) != occupied.shape[1] - pi_count:
        raise RuntimeError("frozen-core occupied count is inconsistent")
    if float(np.min(active_weights[pi_indices])) < 1.0 - 1.0e-8:
        raise RuntimeError(f"occupied pi space is not contained in pz space: {active_weights}")
    if len(core_indices) and float(np.max(active_weights[core_indices])) > 1.0e-8:
        raise RuntimeError(f"frozen occupied space leaks into pz space: {active_weights}")
    return occupied[:, core_indices], occupied[:, pi_indices], active_weights


def active_rhf_energy(
    h1: np.ndarray,
    eri: np.ndarray,
    ecore: float,
    active_occupied: np.ndarray,
) -> float:
    density = 2.0 * active_occupied @ active_occupied.T
    coulomb = np.einsum("pqrs,rs->pq", eri, density, optimize=True)
    exchange = np.einsum("prqs,rs->pq", eri, density, optimize=True)
    return float(ecore + np.einsum("pq,pq->", density, h1 + 0.5 * (coulomb - 0.5 * exchange)))


def exact_fci_certificate(
    h1: np.ndarray,
    eri: np.ndarray,
    norb: int,
    nelec: int,
    ecore: float,
) -> dict[str, Any]:
    electron_pair = (nelec // 2, nelec // 2)
    energy, coefficients = fci.direct_spin1.kernel(
        h1,
        eri,
        norb,
        electron_pair,
        ecore=ecore,
        tol=1.0e-12,
        max_cycle=500,
        max_space=40,
    )
    absorbed = fci.direct_spin1.absorb_h1e(h1, eri, norb, electron_pair, 0.5)
    applied = fci.direct_spin1.contract_2e(absorbed, coefficients, norb, electron_pair)
    residual = np.asarray(applied) - (float(energy) - ecore) * np.asarray(
        coefficients
    )
    return {
        "energy_hartree": float(energy),
        "ci_norm": float(np.linalg.norm(coefficients)),
        "root_residual_l2_hartree": float(np.linalg.norm(residual)),
        "determinant_dimension": int(coefficients.size),
        "solver": "PySCF direct_spin1 FCI",
        "solver_tolerance_hartree": 1.0e-12,
    }


def build_member(k: int, output_dir: Path, run_fci: bool) -> dict[str, Any]:
    slug = f"all_trans_c{k}h{k + 2}_sto3g_pi{k}e{k}o"
    atoms = polyene_geometry(k)
    xyz_path = output_dir / f"{slug}.xyz"
    write_xyz(xyz_path, atoms, k)

    molecule = gto.M(
        atom=atoms,
        unit="Angstrom",
        basis=BASIS,
        charge=0,
        spin=0,
        symmetry=False,
        verbose=0,
    )
    mean_field = converged_rhf(molecule)
    overlap = mean_field.get_ovlp()
    active, pz_indices, pz_overlap_eigenvalues = symmetric_pz_orbitals(
        molecule, overlap
    )
    core, pi_occupied_ao, occupied_active_weights = frozen_core_orbitals(
        mean_field, active, overlap, k
    )

    core_density = 2.0 * core @ core.T
    hcore = mean_field.get_hcore()
    core_veff = mean_field.get_veff(molecule, core_density)
    ecore = float(
        molecule.energy_nuc()
        + np.einsum("pq,pq->", core_density, hcore + 0.5 * core_veff)
    )
    h1 = active.T @ (hcore + core_veff) @ active
    eri = ao2mo.restore(1, ao2mo.kernel(molecule, active), k)
    active_occupied = active.T @ overlap @ pi_occupied_ao
    emitted_rhf = active_rhf_energy(h1, eri, ecore, active_occupied)
    rhf_delta = emitted_rhf - float(mean_field.e_tot)

    orthonormality = float(
        np.max(np.abs(active.T @ overlap @ active - np.eye(k)))
    )
    if orthonormality >= 1.0e-10:
        raise RuntimeError(f"active pz orthonormality failed: {orthonormality}")
    if abs(rhf_delta) >= 1.0e-9:
        raise RuntimeError(f"emitted/full RHF mismatch: {rhf_delta}")

    raw_path = output_dir / f"{slug}.fcidump"
    gzip_path = raw_path.with_suffix(raw_path.suffix + ".gz")
    fcidump.from_integrals(
        str(raw_path),
        h1,
        eri,
        k,
        k,
        ecore,
        ms=0,
        tol=FCIDUMP_TOL,
        float_format=" %.16e",
    )
    deterministic_gzip(raw_path, gzip_path)

    fci_certificate = (
        exact_fci_certificate(h1, eri, k, k, ecore)
        if run_fci and k <= 12
        else None
    )
    historical = HISTORICAL[k]
    historical_total = historical["rhf_total"] + historical["active_correlation"]
    our_active_correlation = (
        None
        if fci_certificate is None
        else fci_certificate["energy_hartree"] - float(mean_field.e_tot)
    )
    row = {
        "slug": slug,
        "k": k,
        "formula": f"C{k}H{k + 2}",
        "norb": k,
        "nelec": k,
        "ms2": 0,
        "basis": "STO-3G",
        "rhf_total_energy_hartree": float(mean_field.e_tot),
        "emitted_hamiltonian_rhf_energy_hartree": emitted_rhf,
        "rhf_consistency_delta_hartree": rhf_delta,
        "frozen_core_energy_hartree": ecore,
        "active_orthonormality_max_abs": orthonormality,
        "pz_ao_indices_zero_based": pz_indices,
        "pz_overlap_eigenvalue_min": float(np.min(pz_overlap_eigenvalues)),
        "pz_overlap_eigenvalue_max": float(np.max(pz_overlap_eigenvalues)),
        "occupied_active_weights": occupied_active_weights.tolist(),
        "fci_certificate": fci_certificate,
        "reference_status": "exact" if fci_certificate is not None else "pending_dmrg",
        "historical_crosscheck_only": {
            "source": "Hachmann, Cardoen, and Chan (2006), Table II",
            "source_url": SOURCE_URL,
            "rhf_total_hartree_rounded": historical["rhf_total"],
            "active_correlation_hartree_rounded": historical["active_correlation"],
            "total_hartree_rounded": historical_total,
            "our_minus_historical_rhf_hartree": float(mean_field.e_tot)
            - historical["rhf_total"],
            "our_minus_historical_active_correlation_hartree": None
            if our_active_correlation is None
            else our_active_correlation - historical["active_correlation"],
            "our_minus_historical_total_hartree": None
            if fci_certificate is None
            else fci_certificate["energy_hartree"] - historical_total,
        },
        "xyz": xyz_path.name,
        "xyz_sha256": digest(xyz_path, "sha256"),
        "fcidump": raw_path.name,
        "fcidump_sha1": digest(raw_path, "sha1"),
        "fcidump_sha256": digest(raw_path, "sha256"),
        "fcidump_gzip": gzip_path.name,
        "fcidump_gzip_sha1": digest(gzip_path, "sha1"),
        "fcidump_gzip_sha256": digest(gzip_path, "sha256"),
        "fcidump_gzip_size_bytes": gzip_path.stat().st_size,
    }
    sidecar_path = output_dir / f"{slug}.generation.json"
    sidecar_path.write_text(json.dumps(row, indent=2) + "\n")
    row["generation_sidecar"] = sidecar_path.name
    row["generation_sidecar_sha256"] = digest(sidecar_path, "sha256")
    return row


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "slug",
        "k",
        "formula",
        "norb",
        "nelec",
        "ms2",
        "basis",
        "reference_status",
        "rhf_total_energy_hartree",
        "emitted_hamiltonian_rhf_energy_hartree",
        "rhf_consistency_delta_hartree",
        "frozen_core_energy_hartree",
        "active_orthonormality_max_abs",
        "fci_energy_hartree",
        "fci_root_residual_l2_hartree",
        "historical_total_hartree_rounded",
        "our_minus_historical_total_hartree",
        "xyz",
        "fcidump",
        "fcidump_sha256",
        "fcidump_gzip",
        "fcidump_gzip_sha256",
        "generation_sidecar",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            certificate = row["fci_certificate"] or {}
            historical = row["historical_crosscheck_only"]
            writer.writerow(
                {
                    **{field: row.get(field, "") for field in fields},
                    "fci_energy_hartree": certificate.get("energy_hartree", ""),
                    "fci_root_residual_l2_hartree": certificate.get(
                        "root_residual_l2_hartree", ""
                    ),
                    "historical_total_hartree_rounded": historical[
                        "total_hartree_rounded"
                    ],
                    "our_minus_historical_total_hartree": historical[
                        "our_minus_historical_total_hartree"
                    ],
                }
            )


def parse_members(value: str) -> tuple[int, ...]:
    members = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    invalid = sorted(set(members) - set(MEMBERS))
    if invalid:
        raise argparse.ArgumentTypeError(f"unsupported members: {invalid}")
    return members


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--analysis-dir", type=Path, required=True)
    parser.add_argument("--members", type=parse_members, default=MEMBERS)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--skip-fci", action="store_true")
    args = parser.parse_args()

    lib.num_threads(max(1, args.threads))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.analysis_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        build_member(k, args.output_dir, run_fci=not args.skip_fci)
        for k in args.members
    ]
    manifest = {
        "family": "all_trans_polyene_sto3g_pi",
        "status": "generated_pending_dmrg"
        if any(row["reference_status"] == "pending_dmrg" for row in rows)
        else "generated_with_exact_references",
        "convention": {
            "members": list(args.members),
            "geometry_source": SOURCE_URL,
            "geometry_source_doi": SOURCE_DOI,
            "cc_double_angstrom": CC_DOUBLE_ANGSTROM,
            "cc_single_angstrom": CC_SINGLE_ANGSTROM,
            "ch_angstrom": CH_ANGSTROM,
            "bond_angle_degrees": BOND_ANGLE_DEGREES,
            "torsion_degrees": 0.0,
            "basis": "STO-3G",
            "active_space": "complete pi_z: k electrons in k orbitals",
            "active_orbitals": "symmetric S^-1/2 orthogonalization of one carbon 2pz AO per site",
            "orbital_order": "carbon-chain topological order",
            "frozen_space": "remaining doubly occupied RHF orbitals",
            "absolute_energy": "FCIDUMP eigenvalue equals RHF total plus active correlation",
        },
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyscf": pyscf.__version__,
            "threads": max(1, args.threads),
        },
        "members": rows,
    }
    json_path = args.analysis_dir / "polyene_generation_manifest.json"
    csv_path = args.analysis_dir / "polyene_generation_manifest.csv"
    json_path.write_text(json.dumps(manifest, indent=2) + "\n")
    write_csv(csv_path, rows)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "members": len(rows),
                "exact": sum(row["reference_status"] == "exact" for row in rows),
                "pending_dmrg": sum(
                    row["reference_status"] == "pending_dmrg" for row in rows
                ),
                "manifest": str(json_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
