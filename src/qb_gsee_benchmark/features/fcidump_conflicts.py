# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Read-only duplicate-orientation census for shipped FCIDUMPs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from qb_gsee_benchmark.features.fcidump_sparse import (
    DEFAULT_DUPLICATE_ATOL,
    DEFAULT_DUPLICATE_RTOL,
    canonical_eri_key,
    open_fcidump_text,
)


DUPLICATE_CENSUS_VERSION = "g45_duplicate_census_v1"


@dataclass(frozen=True)
class DuplicateConflictCensus:
    two_body_input_record_count: int
    two_body_unique_key_count: int
    duplicate_key_count: int
    duplicate_record_count: int
    conflicting_key_count: int
    maximum_absolute_disagreement: float
    maximum_relative_disagreement: float
    maximum_disagreement_key_one_based: tuple[int, int, int, int] | None
    container_format: str
    container_member: str | None
    rtol: float
    atol: float
    comparison_rule: str
    census_version: str = DUPLICATE_CENSUS_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _KeyStats:
    mean: float
    count: int
    minimum: float
    maximum: float
    conflict: bool = False

    def add(self, value: float, *, rtol: float, atol: float) -> None:
        if not np.isclose(self.mean, value, rtol=rtol, atol=atol):
            self.conflict = True
        self.mean = (self.count * self.mean + value) / (self.count + 1)
        self.count += 1
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)

    @property
    def absolute_disagreement(self) -> float:
        return self.maximum - self.minimum

    @property
    def relative_disagreement(self) -> float:
        return self.absolute_disagreement / max(
            abs(self.minimum),
            abs(self.maximum),
            float(np.finfo(float).tiny),
        )


def scan_duplicate_conflicts(
    path: str | Path,
    *,
    rtol: float = DEFAULT_DUPLICATE_RTOL,
    atol: float = DEFAULT_DUPLICATE_ATOL,
) -> DuplicateConflictCensus:
    """Scan duplicate two-body keys without constructing integral tensors."""
    path = Path(path)
    stats: dict[tuple[int, int, int, int], _KeyStats] = {}
    input_records = 0
    with open_fcidump_text(path) as opened:
        handle, container_format, container_member = opened
        for line in handle:
            if "/" in line or "&END" in line.upper():
                break
        else:
            raise ValueError("FCIDUMP header has no / or &END terminator")

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
            raw = tuple(int(field) for field in fields[1:])
            if raw == (0, 0, 0, 0):
                continue
            i, j, k, l = (index - 1 for index in raw)
            if k == -1 and l == -1 and i >= 0 and j >= 0:
                continue
            if min(i, j, k, l) < 0:
                raise ValueError(
                    f"Mixed zero/nonzero indices at data line {line_number}"
                )
            input_records += 1
            key = canonical_eri_key(i, j, k, l)
            current = stats.get(key)
            if current is None:
                stats[key] = _KeyStats(value, 1, value, value)
            else:
                current.add(value, rtol=rtol, atol=atol)

    duplicate_items = [
        (key, item) for key, item in stats.items() if item.count > 1
    ]
    maximum_key = None
    maximum_absolute = 0.0
    maximum_relative = 0.0
    for key, item in duplicate_items:
        absolute = item.absolute_disagreement
        relative = item.relative_disagreement
        if absolute > maximum_absolute or (
            absolute == maximum_absolute
            and (maximum_key is None or key < maximum_key)
        ):
            maximum_key = key
            maximum_absolute = absolute
        maximum_relative = max(maximum_relative, relative)

    return DuplicateConflictCensus(
        two_body_input_record_count=input_records,
        two_body_unique_key_count=len(stats),
        duplicate_key_count=len(duplicate_items),
        duplicate_record_count=sum(item.count - 1 for _, item in duplicate_items),
        conflicting_key_count=sum(item.conflict for _, item in duplicate_items),
        maximum_absolute_disagreement=float(maximum_absolute),
        maximum_relative_disagreement=float(maximum_relative),
        maximum_disagreement_key_one_based=(
            None
            if maximum_key is None
            else tuple(index + 1 for index in maximum_key)
        ),
        container_format=container_format,
        container_member=container_member,
        rtol=rtol,
        atol=atol,
        comparison_rule="numpy.isclose(running_mean, next_value, rtol, atol)",
    )
