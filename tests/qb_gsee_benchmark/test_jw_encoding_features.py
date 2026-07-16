from __future__ import annotations

import math
from collections import defaultdict
from itertools import product
from pathlib import Path

import numpy as np
import pytest

from qb_gsee_benchmark.features.fcidump_sparse import read_sparse_fcidump
from qb_gsee_benchmark.features.jw_encoding_features import (
    COEFFICIENT_ATOL,
    OUTPUT_COLUMNS,
    _canonicalize_historical_raw,
    _jw_support,
    compute_jw_encoding_features,
)

FIXTURES = Path(__file__).parent / "fixtures" / "g40_permutation_pairs"


def _normal_order(indices: tuple[int, ...]) -> tuple[tuple[int, ...], int]:
    ordered: list[int] = []
    phase = 1
    for value in indices:
        position = len(ordered)
        while position and ordered[position - 1] > value:
            position -= 1
            phase *= -1
        if position and ordered[position - 1] == value:
            ordered.pop(position - 1)
        else:
            ordered.insert(position, value)
    return tuple(ordered), phase


def _operators(kind: str, mode: int) -> tuple[tuple[int, complex], ...]:
    if kind == "create":
        return ((2 * mode, 0.5), (2 * mode + 1, -0.5j))
    return ((2 * mode, 0.5), (2 * mode + 1, 0.5j))


def _reference_majoranas(path: Path) -> dict[tuple[int, ...], complex]:
    data = read_sparse_fcidump(path, strict_duplicates=True)
    raw_values: dict[tuple[int, ...], complex] = defaultdict(complex)
    for p, q in zip(*np.nonzero(data.h1)):
        for factors in product(_operators("create", p), _operators("annihilate", q)):
            key = tuple(item[0] for item in factors)
            raw_values[key] += data.h1[p, q] * math.prod(item[1] for item in factors)
    for (p, q, r, s), coefficient in sorted(data.iter_eri_entries()):
        if coefficient == 0.0:
            continue
        for factors in product(
            _operators("create", p),
            _operators("annihilate", q),
            _operators("create", r),
            _operators("annihilate", s),
        ):
            key = tuple(item[0] for item in factors)
            raw_values[key] += coefficient * math.prod(item[1] for item in factors)

    values: dict[tuple[int, ...], complex] = defaultdict(complex)
    for key, value in raw_values.items():
        if np.isclose(value, 0):
            continue
        ordered, phase = _normal_order(key)
        values[ordered] += phase * value
    return {
        key: value for key, value in values.items() if abs(value) >= COEFFICIENT_ATOL
    }


def _reference_features(path: Path) -> dict[str, float | int]:
    data = read_sparse_fcidump(path, strict_duplicates=True)
    majoranas = _reference_majoranas(path)
    nonidentity = [(key, value) for key, value in majoranas.items() if key]
    weights = np.asarray([abs(value) for _, value in nonidentity])
    supports = [_jw_support(key) for key, _ in nonidentity]
    orders = np.asarray([support.bit_count() for support in supports])
    degrees = np.zeros(data.norb, dtype=int)
    for support in supports:
        for qubit in range(data.norb):
            degrees[qubit] += (support >> qubit) & 1
    touched = degrees[degrees > 0]
    number = len(majoranas)
    return {
        "max_vertex_degree": int(touched.max()),
        "min_vertex_degree": int(touched.min()),
        "mean_vertex_degree": float(touched.mean()),
        "std_dev_vertex_degree": float(touched.std()),
        "max_weight": float(weights.max()),
        "mean_weight": float(weights.mean()),
        "std_dev_weight": float(weights.std()),
        "mean_edge_order": float(orders.mean()),
        "std_dev_edge_order": float(orders.std()),
        "number_of_terms": number,
        "pauli_terms_per_orbital_quartic": number / data.norb**4,
        "mean_vertex_degree_per_orbital": float(touched.mean()) / data.norb,
        "max_vertex_degree_per_orbital": int(touched.max()) / data.norb,
        "vertex_degree_coefficient_of_variation": float(touched.std() / touched.mean()),
        "edge_order_coefficient_of_variation": float(orders.std() / orders.mean()),
    }


def test_sparse_streaming_matches_independent_expansion() -> None:
    path = FIXTURES / "molecular_h2_original.FCIDUMP"
    actual, audit = compute_jw_encoding_features(path)
    expected = _reference_features(path)
    assert set(actual) == set(OUTPUT_COLUMNS)
    for column in OUTPUT_COLUMNS:
        assert actual[column] == pytest.approx(expected[column], rel=1e-12, abs=1e-12)
    assert audit["route"] == "sparse_multiset_historical_two_stage_threshold"


def test_compiled_templates_cover_all_orbital_multiplicities(
    tmp_path: Path,
) -> None:
    path = tmp_path / "all_patterns.FCIDUMP"
    path.write_text(
        "&FCI NORB=4, NELEC=2, MS2=0,\n"
        " ORBSYM=1,1,1,1, ISYM=1 /\n"
        " 2.100000000000000e-07 1 1 1 1\n"
        " 1.900000000000000e-07 2 1 1 1\n"
        " 3.100000000000000e-07 2 2 1 1\n"
        " 1.400000000000000e-07 2 1 2 1\n"
        " 4.200000000000000e-07 1 1 2 3\n"
        "-1.300000000000000e-07 1 2 1 3\n"
        " 5.100000000000000e-07 1 2 3 4\n"
        "-2.200000000000000e-07 1 3 2 4\n"
        " 1.100000000000000e-07 1 4 2 3\n"
        " 1.000000000000000e+00 1 1 0 0\n"
        " 0.000000000000000e+00 0 0 0 0\n"
    )
    actual, _ = compute_jw_encoding_features(path)
    expected = _reference_features(path)
    for column in OUTPUT_COLUMNS:
        assert actual[column] == pytest.approx(expected[column], rel=1e-12, abs=1e-12)


def test_historical_filter_precedes_normal_order() -> None:
    canonical, filtered = _canonicalize_historical_raw(
        {(1, 0): 6.0e-9, (0, 1): -6.0e-9}
    )
    assert canonical == {}
    assert filtered == 2


def test_shipped_order_is_observable_but_values_are_finite() -> None:
    original, _ = compute_jw_encoding_features(
        FIXTURES / "qsz_l4x4_u2_original.FCIDUMP"
    )
    permuted, _ = compute_jw_encoding_features(
        FIXTURES / "qsz_l4x4_u2_permuted.FCIDUMP"
    )
    assert all(math.isfinite(float(value)) for value in original.values())
    assert original["number_of_terms"] == permuted["number_of_terms"]
    assert original != permuted
