# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Sparse, symmetry-aware reader for real spatial-orbital FCIDUMPs."""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, TextIO

import numpy as np


_HEADER_KEYS = ("NORB", "NELEC", "MS2")
DEFAULT_DUPLICATE_RTOL = 1.0e-8
DEFAULT_DUPLICATE_ATOL = 1.0e-8


def _open_text(path: Path) -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="ascii")
    return path.open("rt", encoding="ascii")


def eri_symmetry_permutations(
    i: int, j: int, k: int, l: int
) -> set[tuple[int, int, int, int]]:
    """Return the real chemist-integral eightfold symmetry orbit."""
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


def canonical_eri_key(
    i: int, j: int, k: int, l: int
) -> tuple[int, int, int, int]:
    return min(eri_symmetry_permutations(i, j, k, l))


@dataclass(frozen=True)
class SparseFcidump:
    norb: int
    nelec: int
    ms2: int
    h1: np.ndarray
    eri_records: dict[tuple[int, int, int, int], float]
    ecore: float
    one_body_duplicate_orientations: int
    one_body_duplicate_max_abs_difference: float
    one_body_duplicate_max_rel_difference: float
    one_body_symmetry_conflict_records: int
    two_body_input_records: int
    two_body_duplicate_orientations: int
    two_body_duplicate_max_abs_difference: float
    two_body_duplicate_max_rel_difference: float
    two_body_symmetry_conflict_records: int

    @property
    def nalpha(self) -> int:
        return (self.nelec + self.ms2) // 2

    @property
    def nbeta(self) -> int:
        return (self.nelec - self.ms2) // 2

    def iter_eri_entries(
        self,
    ) -> Iterator[tuple[tuple[int, int, int, int], float]]:
        """Yield every symmetry-expanded tensor entry exactly once."""
        for key, value in self.eri_records.items():
            for indices in eri_symmetry_permutations(*key):
                yield indices, value

    def eri_value(self, i: int, j: int, k: int, l: int) -> float:
        return self.eri_records.get(canonical_eri_key(i, j, k, l), 0.0)

    def dense_eri(self) -> np.ndarray:
        eri = np.zeros((self.norb,) * 4, dtype=float)
        for indices, value in self.iter_eri_entries():
            eri[indices] = value
        return eri


def _parse_header(handle: TextIO) -> dict[str, int]:
    chunks: list[str] = []
    for line in handle:
        chunks.append(line)
        upper = line.upper()
        if "/" in line or "&END" in upper:
            break
    else:
        raise ValueError("FCIDUMP header has no / or &END terminator")

    text = " ".join(chunks)
    result: dict[str, int] = {}
    for key in _HEADER_KEYS:
        match = re.search(rf"\b{key}\s*=\s*(-?\d+)", text, re.IGNORECASE)
        if match is None:
            raise ValueError(f"Missing {key} in FCIDUMP header")
        result[key.lower()] = int(match.group(1))
    iuhf = re.search(r"\bIUHF\s*=\s*(-?\d+)", text, re.IGNORECASE)
    if iuhf is not None and int(iuhf.group(1)) != 0:
        raise ValueError("IUHF FCIDUMPs are not supported by the spatial parser")
    return result


def _store_checked(
    values: dict[tuple[int, ...], float],
    counts: dict[tuple[int, ...], int],
    key: tuple[int, ...],
    value: float,
    *,
    label: str,
    rtol: float,
    atol: float,
    strict: bool,
) -> tuple[bool, float, float, bool]:
    previous = values.get(key)
    if previous is None:
        values[key] = value
        counts[key] = 1
        return False, 0.0, 0.0, False
    absolute_difference = abs(previous - value)
    relative_difference = absolute_difference / max(
        abs(previous), abs(value), float(np.finfo(float).tiny)
    )
    conflict = not np.isclose(previous, value, rtol=rtol, atol=atol)
    if conflict and strict:
        raise ValueError(
            f"Conflicting {label} records for {key}: "
            f"{previous:.17g} vs {value:.17g}; "
            f"abs_diff={absolute_difference:.3g}, "
            f"rel_diff={relative_difference:.3g}"
        )
    count = counts[key]
    values[key] = (count * previous + value) / (count + 1)
    counts[key] = count + 1
    return True, absolute_difference, relative_difference, conflict


def read_sparse_fcidump(
    path: str | Path,
    *,
    duplicate_rtol: float = DEFAULT_DUPLICATE_RTOL,
    duplicate_atol: float = DEFAULT_DUPLICATE_ATOL,
    strict_duplicates: bool = False,
) -> SparseFcidump:
    """Read a real spatial FCIDUMP without allocating an N**4 tensor."""
    path = Path(path)
    with _open_text(path) as handle:
        header = _parse_header(handle)
        norb = header["norb"]
        nelec = header["nelec"]
        ms2 = header["ms2"]
        if (nelec + ms2) % 2:
            raise ValueError("FCIDUMP NELEC and MS2 have inconsistent parity")
        nalpha = (nelec + ms2) // 2
        nbeta = (nelec - ms2) // 2
        if not 0 <= nalpha <= norb or not 0 <= nbeta <= norb:
            raise ValueError("FCIDUMP electron sector does not fit NORB")

        one_body: dict[tuple[int, int], float] = {}
        one_body_counts: dict[tuple[int, int], int] = {}
        two_body: dict[tuple[int, int, int, int], float] = {}
        two_body_counts: dict[tuple[int, int, int, int], int] = {}
        ecore = 0.0
        one_body_duplicate_orientations = 0
        one_body_duplicate_max_abs_difference = 0.0
        one_body_duplicate_max_rel_difference = 0.0
        one_body_symmetry_conflict_records = 0
        input_records = 0
        duplicate_orientations = 0
        two_body_duplicate_max_abs_difference = 0.0
        two_body_duplicate_max_rel_difference = 0.0
        two_body_symmetry_conflict_records = 0
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("!", "#")):
                continue
            fields = stripped.split()
            if len(fields) != 5:
                raise ValueError(
                    f"Malformed FCIDUMP data line {line_number}: {stripped!r}"
                )
            value = float(fields[0].replace("D", "E").replace("d", "e"))
            raw_indices = tuple(int(field) for field in fields[1:])
            if raw_indices == (0, 0, 0, 0):
                ecore = value
                continue
            i, j, k, l = (index - 1 for index in raw_indices)
            if k == -1 and l == -1 and i >= 0 and j >= 0:
                if max(i, j) >= norb:
                    raise ValueError(
                        f"One-body index exceeds NORB at line {line_number}"
                    )
                key = (min(i, j), max(i, j))
                duplicate, abs_difference, rel_difference, conflict = _store_checked(
                    one_body,
                    one_body_counts,
                    key,
                    value,
                    label="one-body",
                    rtol=duplicate_rtol,
                    atol=duplicate_atol,
                    strict=strict_duplicates,
                )
                one_body_duplicate_orientations += int(duplicate)
                one_body_duplicate_max_abs_difference = max(
                    one_body_duplicate_max_abs_difference, abs_difference
                )
                one_body_duplicate_max_rel_difference = max(
                    one_body_duplicate_max_rel_difference, rel_difference
                )
                one_body_symmetry_conflict_records += int(conflict)
                continue
            if min(i, j, k, l) < 0 or max(i, j, k, l) >= norb:
                raise ValueError(f"Invalid two-body indices at line {line_number}")
            input_records += 1
            key = canonical_eri_key(i, j, k, l)
            duplicate, abs_difference, rel_difference, conflict = _store_checked(
                two_body,
                two_body_counts,
                key,
                value,
                label="two-body",
                rtol=duplicate_rtol,
                atol=duplicate_atol,
                strict=strict_duplicates,
            )
            duplicate_orientations += int(duplicate)
            two_body_duplicate_max_abs_difference = max(
                two_body_duplicate_max_abs_difference, abs_difference
            )
            two_body_duplicate_max_rel_difference = max(
                two_body_duplicate_max_rel_difference, rel_difference
            )
            two_body_symmetry_conflict_records += int(conflict)

    h1 = np.zeros((norb, norb), dtype=float)
    for (i, j), value in one_body.items():
        h1[i, j] = value
        h1[j, i] = value
    return SparseFcidump(
        norb=norb,
        nelec=nelec,
        ms2=ms2,
        h1=h1,
        eri_records=two_body,
        ecore=ecore,
        one_body_duplicate_orientations=one_body_duplicate_orientations,
        one_body_duplicate_max_abs_difference=(
            one_body_duplicate_max_abs_difference
        ),
        one_body_duplicate_max_rel_difference=(
            one_body_duplicate_max_rel_difference
        ),
        one_body_symmetry_conflict_records=one_body_symmetry_conflict_records,
        two_body_input_records=input_records,
        two_body_duplicate_orientations=duplicate_orientations,
        two_body_duplicate_max_abs_difference=(
            two_body_duplicate_max_abs_difference
        ),
        two_body_duplicate_max_rel_difference=(
            two_body_duplicate_max_rel_difference
        ),
        two_body_symmetry_conflict_records=two_body_symmetry_conflict_records,
    )
