# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Polynomial seniority and pair-structure proxies from an FCIDUMP."""

from __future__ import annotations

import gzip
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, TextIO

import numpy as np

PAIR_STRUCTURE_FEATURES_VERSION = "g24_pair_structure_v1"
PAIR_STRUCTURE_FEATURE_COLUMNS = (
    "g24_coverage_group",
    "two_body_input_record_count",
    "two_body_unique_record_count",
    "two_body_duplicate_orientation_records_skipped",
    "eri_full_l1_norm",
    "eri_full_l2_norm",
    "pair_scattering_eri_l1_fraction",
    "pair_scattering_eri_l2_fraction",
    "seniority_preserving_eri_l1_fraction",
    "seniority_preserving_eri_l2_fraction",
    "pair_to_density_eri_l2_ratio",
    "pair_to_seniority_breaking_eri_l2_ratio",
    "hf_fock_ov_l2_norm",
    "hf_fock_ov_max_abs",
    "hf_stationarity_tolerance",
    "mp2_os_corr_energy_hartree",
    "mp2_ss_corr_energy_hartree",
    "mp2_corr_energy_hartree",
    "mp2_os_energy_abs_fraction",
    "mp2_ss_energy_abs_fraction",
    "mp2_pair_double_amplitude_l1_fraction",
    "mp2_pair_double_amplitude_l2_fraction",
    "mp2_spin_decomposition_status",
    "pair_structure_basis",
    "pair_structure_features_version",
)


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="ascii")
    return path.open("rt", encoding="ascii")


def _read_header(handle: TextIO) -> dict[str, int]:
    chunks = []
    for line in handle:
        chunks.append(line)
        if "/" in line or "&END" in line.upper():
            break
    text = " ".join(chunks)
    result = {}
    for key in ("NORB", "NELEC", "MS2"):
        match = re.search(rf"\b{key}\s*=\s*(-?\d+)", text, re.IGNORECASE)
        if not match:
            raise ValueError(f"Missing {key} in FCIDUMP header")
        result[key.lower()] = int(match.group(1))
    return result


def _symmetry_permutations(
    i: int, j: int, k: int, l: int
) -> set[tuple[int, int, int, int]]:
    return {
        (i, j, k, l),
        (j, i, k, l),
        (i, j, l, k),
        (j, i, l, k),
        (k, l, i, j),
        (l, k, i, j),
        (k, l, j, i),
        (l, k, j, i),
    }


def _safe_fraction(numerator: float, denominator: float) -> float | None:
    return float(numerator / denominator) if denominator > 0.0 else None


def compute_pair_structure_features(
    path: str | Path,
    *,
    coverage_group: str = "",
    stationarity_tolerance: float = 2.0e-7,
) -> dict[str, Any]:
    """Compute the G-24 proxies in the declared spatial-orbital basis."""
    path = Path(path)
    with _open_text(path) as handle:
        header = _read_header(handle)
        norb, nelec, ms2 = header["norb"], header["nelec"], header["ms2"]
        if ms2 != 0 or nelec % 2:
            raise ValueError(
                f"G-24 requires a closed-shell sector, got NELEC={nelec} MS2={ms2}"
            )
        nocc = nelec // 2
        nvir = norb - nocc
        if nvir <= 0:
            raise ValueError("G-24 requires at least one virtual orbital")
        h1 = np.zeros((norb, norb))
        fock_two_body = np.zeros((norb, norb))
        ovov = np.zeros((nocc, nvir, nocc, nvir))
        input_records = records = skipped_orientations = 0
        total_l1 = total_sq = pair_l1 = pair_sq = density_sq = 0.0
        seniority_l1 = seniority_sq = 0.0

        for line_number, line in enumerate(handle, start=1):
            fields = line.split()
            if not fields:
                continue
            if len(fields) != 5:
                raise ValueError(
                    f"Malformed FCIDUMP record at data line {line_number}: {line!r}"
                )
            value = float(fields[0].replace("D", "E").replace("d", "e"))
            i, j, k, l = (int(field) - 1 for field in fields[1:])
            if k == -1 and l == -1 and i >= 0 and j >= 0:
                h1[i, j] = h1[j, i] = value
                continue
            if i == j == k == l == -1:
                continue
            if min(i, j, k, l) < 0:
                raise ValueError(
                    f"Mixed zero/nonzero indices at data line {line_number}: {line!r}"
                )
            input_records += 1
            pair_ij = max(i, j) * (max(i, j) + 1) // 2 + min(i, j)
            pair_kl = max(k, l) * (max(k, l) + 1) // 2 + min(k, l)
            if pair_ij < pair_kl:
                skipped_orientations += 1
                continue
            records += 1
            multiplicity = (1 if i == j else 2) * (1 if k == l else 2)
            if (i, j) != (k, l):
                multiplicity *= 2
            absolute = abs(value)
            square = value * value
            total_l1 += multiplicity * absolute
            total_sq += multiplicity * square

            counts = Counter((i, j, k, l))
            seniority_preserving = all(count % 2 == 0 for count in counts.values())
            occupied_repeated = any(
                index < nocc and count >= 2 for index, count in counts.items()
            )
            occupied_count = sum(index < nocc for index in (i, j, k, l))
            if not (seniority_preserving or occupied_repeated or occupied_count == 2):
                continue
            permutations = _symmetry_permutations(i, j, k, l)
            if len(permutations) != multiplicity:
                raise AssertionError((i, j, k, l, len(permutations), multiplicity))

            if seniority_preserving:
                seniority_l1 += multiplicity * absolute
                seniority_sq += multiplicity * square
                pair_count = sum(
                    p == r and q == s and p != q for p, q, r, s in permutations
                )
                density_count = sum(
                    p == q and r == s and p != r for p, q, r, s in permutations
                )
                pair_l1 += pair_count * absolute
                pair_sq += pair_count * square
                density_sq += density_count * square

            for p, q, r, s in permutations:
                if r == s and r < nocc:
                    fock_two_body[p, q] += 2.0 * value
                if q == r and q < nocc:
                    fock_two_body[p, s] -= value
                if p < nocc <= q and r < nocc <= s:
                    ovov[p, q - nocc, r, s - nocc] = value

    fock = h1 + fock_two_body
    fov = fock[:nocc, nocc:]
    fov_l2 = float(np.linalg.norm(fov))
    fov_max = float(np.max(np.abs(fov), initial=0.0))
    result: dict[str, Any] = {
        "n_orbs": norb,
        "n_elec": nelec,
        "ms2": ms2,
        "g24_coverage_group": coverage_group,
        "two_body_input_record_count": input_records,
        "two_body_unique_record_count": records,
        "two_body_duplicate_orientation_records_skipped": skipped_orientations,
        "eri_full_l1_norm": total_l1,
        "eri_full_l2_norm": math.sqrt(total_sq),
        "pair_scattering_eri_l1_fraction": _safe_fraction(pair_l1, total_l1),
        "pair_scattering_eri_l2_fraction": _safe_fraction(pair_sq, total_sq),
        "seniority_preserving_eri_l1_fraction": _safe_fraction(
            seniority_l1, total_l1
        ),
        "seniority_preserving_eri_l2_fraction": _safe_fraction(
            seniority_sq, total_sq
        ),
        "pair_to_density_eri_l2_ratio": _safe_fraction(pair_sq, density_sq),
        "pair_to_seniority_breaking_eri_l2_ratio": _safe_fraction(
            pair_sq, total_sq - seniority_sq
        ),
        "hf_fock_ov_l2_norm": fov_l2,
        "hf_fock_ov_max_abs": fov_max,
        "hf_stationarity_tolerance": stationarity_tolerance,
        "mp2_os_corr_energy_hartree": None,
        "mp2_ss_corr_energy_hartree": None,
        "mp2_corr_energy_hartree": None,
        "mp2_os_energy_abs_fraction": None,
        "mp2_ss_energy_abs_fraction": None,
        "mp2_pair_double_amplitude_l1_fraction": None,
        "mp2_pair_double_amplitude_l2_fraction": None,
        "mp2_spin_decomposition_status": (
            "nonstationary_declared_aufbau_determinant"
            if fov_max > stationarity_tolerance
            else "ok"
        ),
        "pair_structure_basis": "declared_fcidump_spatial_orbitals",
        "pair_structure_features_version": PAIR_STRUCTURE_FEATURES_VERSION,
    }
    if fov_max <= stationarity_tolerance:
        occupied_energies, occupied_rotation = np.linalg.eigh(fock[:nocc, :nocc])
        virtual_energies, virtual_rotation = np.linalg.eigh(fock[nocc:, nocc:])
        transformed = np.einsum(
            "pi,qa,rj,sb,pqrs->iajb",
            occupied_rotation,
            virtual_rotation,
            occupied_rotation,
            virtual_rotation,
            ovov,
            optimize=True,
        )
        denominator = (
            occupied_energies[:, None, None, None]
            + occupied_energies[None, None, :, None]
            - virtual_energies[None, :, None, None]
            - virtual_energies[None, None, None, :]
        )
        if float(np.min(np.abs(denominator))) < 1.0e-10:
            result["mp2_spin_decomposition_status"] = "near_zero_mp2_denominator"
        else:
            amplitudes = transformed / denominator
            exchange = transformed.transpose(0, 3, 2, 1)
            os_energy = float(np.einsum("iajb,iajb->", amplitudes, transformed))
            ss_energy = float(
                np.einsum("iajb,iajb->", amplitudes, transformed - exchange)
            )
            pair_amplitudes = amplitudes[
                np.arange(nocc)[:, None],
                np.arange(nvir)[None, :],
                np.arange(nocc)[:, None],
                np.arange(nvir)[None, :],
            ]
            energy_weight = abs(os_energy) + abs(ss_energy)
            result.update(
                {
                    "mp2_os_corr_energy_hartree": os_energy,
                    "mp2_ss_corr_energy_hartree": ss_energy,
                    "mp2_corr_energy_hartree": os_energy + ss_energy,
                    "mp2_os_energy_abs_fraction": _safe_fraction(
                        abs(os_energy), energy_weight
                    ),
                    "mp2_ss_energy_abs_fraction": _safe_fraction(
                        abs(ss_energy), energy_weight
                    ),
                    "mp2_pair_double_amplitude_l1_fraction": _safe_fraction(
                        float(np.sum(np.abs(pair_amplitudes))),
                        float(np.sum(np.abs(amplitudes))),
                    ),
                    "mp2_pair_double_amplitude_l2_fraction": _safe_fraction(
                        float(np.sum(pair_amplitudes * pair_amplitudes)),
                        float(np.sum(amplitudes * amplitudes)),
                    ),
                }
            )
    return result
