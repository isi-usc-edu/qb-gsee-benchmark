# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Exact sparse G58 Jordan-Wigner encoding statistics."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import permutations, product
from pathlib import Path
from typing import Any

import numpy as np

from qb_gsee_benchmark.features.fcidump_sparse import (
    SparseFcidump,
    read_sparse_fcidump,
)

JW_ENCODING_VERSION = "g58_jw_encoding_v1_1"
COEFFICIENT_ATOL = 1.0e-8
COMPLEX_RESIDUE_ATOL = 1.0e-10
OUTPUT_COLUMNS = (
    "max_vertex_degree",
    "min_vertex_degree",
    "mean_vertex_degree",
    "std_dev_vertex_degree",
    "max_weight",
    "mean_weight",
    "std_dev_weight",
    "mean_edge_order",
    "std_dev_edge_order",
    "number_of_terms",
    "pauli_terms_per_orbital_quartic",
    "mean_vertex_degree_per_orbital",
    "max_vertex_degree_per_orbital",
    "vertex_degree_coefficient_of_variation",
    "edge_order_coefficient_of_variation",
)


class JwEncodingInfeasibleError(ValueError):
    """Exact G58 result cannot be produced under the protocol."""

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason


def _canonical_eri_key(i: int, j: int, k: int, l: int) -> tuple[int, ...]:
    first = (min(i, j), max(i, j))
    second = (min(k, l), max(k, l))
    if second < first:
        first, second = second, first
    return first + second


def _eri(data: SparseFcidump, i: int, j: int, k: int, l: int) -> float:
    return data.eri_records.get(_canonical_eri_key(i, j, k, l), 0.0)


def _jw_support(majoranas: tuple[int, ...]) -> int:
    x_bits = 0
    z_bits = 0
    for majorana in majoranas:
        mode = majorana // 2
        x_bits ^= 1 << mode
        z_bits ^= (1 << mode) - 1
        if majorana % 2:
            z_bits ^= 1 << mode
    return x_bits | z_bits


def _normal_order_majoranas(
    indices: tuple[int, ...],
) -> tuple[tuple[int, ...], int]:
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


def _dirac_to_majorana(
    kind: str, mode: int
) -> tuple[tuple[int, complex], tuple[int, complex]]:
    if kind == "create":
        return ((2 * mode, 0.5), (2 * mode + 1, -0.5j))
    if kind == "annihilate":
        return ((2 * mode, 0.5), (2 * mode + 1, 0.5j))
    raise ValueError(f"unknown Dirac operator kind: {kind}")


def _ordered_majorana_terms(
    operators: tuple[tuple[str, int], ...], coefficient: float
) -> tuple[tuple[tuple[int, ...], complex], ...]:
    terms: list[tuple[tuple[int, ...], complex]] = []
    options = tuple(_dirac_to_majorana(kind, mode) for kind, mode in operators)
    for factors in product(*options):
        key = tuple(item[0] for item in factors)
        value = complex(coefficient)
        for _, factor in factors:
            value *= factor
        terms.append((key, value))
    return tuple(terms)


def _canonicalize_historical_raw(
    raw: dict[tuple[int, ...], complex],
) -> tuple[dict[tuple[int, ...], complex], int]:
    canonical: dict[tuple[int, ...], complex] = defaultdict(complex)
    filtered = 0
    for key, value in raw.items():
        if np.isclose(value, 0):
            filtered += 1
            continue
        ordered, phase = _normal_order_majoranas(key)
        canonical[ordered] += phase * value
    return dict(canonical), filtered


@dataclass(frozen=True)
class _CompiledRawFilter:
    threshold_vector: tuple[complex, ...]
    raw_key_count: int
    contributions: tuple[tuple[tuple[int, ...], tuple[complex, ...]], ...]


@dataclass(frozen=True)
class _CompiledQuarticTemplate:
    variable_keys: tuple[tuple[int, ...], ...]
    filters: tuple[_CompiledRawFilter, ...]


@lru_cache(maxsize=None)
def _compile_quartic_template(
    pattern: tuple[int, int, int, int],
) -> _CompiledQuarticTemplate:
    entries = sorted(set(permutations(pattern)))
    variable_keys = tuple(sorted({_canonical_eri_key(*entry) for entry in entries}))
    variable_indices = {key: index for index, key in enumerate(variable_keys)}
    raw: dict[tuple[int, ...], list[complex]] = {}
    for entry in entries:
        variable_index = variable_indices[_canonical_eri_key(*entry)]
        operators = (
            ("create", entry[0]),
            ("annihilate", entry[1]),
            ("create", entry[2]),
            ("annihilate", entry[3]),
        )
        for key, coefficient in _ordered_majorana_terms(operators, 1.0):
            vector = raw.setdefault(key, [0.0j] * len(variable_keys))
            vector[variable_index] += coefficient

    class_counts: dict[tuple[complex, ...], int] = defaultdict(int)
    class_contributions: dict[
        tuple[complex, ...], dict[tuple[int, ...], list[complex]]
    ] = defaultdict(dict)
    for raw_key, raw_vector_list in raw.items():
        raw_vector = tuple(raw_vector_list)
        first = next(value for value in raw_vector if value != 0.0)
        unit_phase = first / abs(first)
        threshold_vector = tuple(value / unit_phase for value in raw_vector)
        class_counts[threshold_vector] += 1
        canonical_key, phase = _normal_order_majoranas(raw_key)
        contributions = class_contributions[threshold_vector]
        vector = contributions.setdefault(canonical_key, [0.0j] * len(variable_keys))
        for index, value in enumerate(raw_vector):
            vector[index] += phase * value

    filters = tuple(
        _CompiledRawFilter(
            threshold_vector=threshold_vector,
            raw_key_count=class_counts[threshold_vector],
            contributions=tuple(
                (key, tuple(vector)) for key, vector in contributions.items()
            ),
        )
        for threshold_vector, contributions in class_contributions.items()
    )
    return _CompiledQuarticTemplate(variable_keys, filters)


def _evaluate_quartic_template(
    data: SparseFcidump, group: tuple[int, ...]
) -> tuple[dict[tuple[int, ...], complex], int, int]:
    distinct = tuple(sorted(set(group)))
    labels = {value: index for index, value in enumerate(distinct)}
    pattern = tuple(labels[value] for value in group)
    template = _compile_quartic_template(pattern)
    values = tuple(
        _eri(data, *(distinct[index] for index in key))
        for key in template.variable_keys
    )
    canonical: dict[tuple[int, ...], complex] = defaultdict(complex)
    filtered = 0
    raw_key_count = 0
    for compiled_filter in template.filters:
        raw_key_count += compiled_filter.raw_key_count
        threshold_value = sum(
            coefficient * value
            for coefficient, value in zip(compiled_filter.threshold_vector, values)
        )
        if np.isclose(threshold_value, 0):
            filtered += compiled_filter.raw_key_count
            continue
        for representative_key, contribution_vector in compiled_filter.contributions:
            coefficient = sum(
                factor * value for factor, value in zip(contribution_vector, values)
            )
            actual_key = tuple(
                2 * distinct[index // 2] + index % 2 for index in representative_key
            )
            canonical[actual_key] += coefficient
    return dict(canonical), filtered, raw_key_count


@dataclass
class _SufficientStatistics:
    norb: int

    def __post_init__(self) -> None:
        self.nonidentity_terms = 0
        self.weight_sum = 0.0
        self.weight_square_sum = 0.0
        self.max_weight = 0.0
        self.edge_sum = 0
        self.edge_square_sum = 0
        self.vertex_degrees = np.zeros(self.norb, dtype=np.int64)

    def emit(self, majoranas: tuple[int, ...], coefficient: complex) -> None:
        weight = abs(coefficient)
        if not math.isfinite(weight):
            raise JwEncodingInfeasibleError(
                "nonfinite_or_complex_coefficient", "nonfinite coefficient"
            )
        if weight < COEFFICIENT_ATOL:
            return
        if (
            len(majoranas) == 2
            and abs(complex(coefficient).real) > COMPLEX_RESIDUE_ATOL
        ):
            raise JwEncodingInfeasibleError(
                "nonfinite_or_complex_coefficient",
                "two-Majorana coefficient has an unexpected real residue",
            )
        if (
            len(majoranas) == 4
            and abs(complex(coefficient).imag) > COMPLEX_RESIDUE_ATOL
        ):
            raise JwEncodingInfeasibleError(
                "nonfinite_or_complex_coefficient",
                "four-Majorana coefficient has an unexpected imaginary residue",
            )
        support = _jw_support(majoranas)
        edge_order = support.bit_count()
        if edge_order == 0:
            raise JwEncodingInfeasibleError(
                "empty_nonidentity_jw_support", "nonidentity term has empty support"
            )
        self.nonidentity_terms += 1
        self.weight_sum += weight
        self.weight_square_sum += weight * weight
        self.max_weight = max(self.max_weight, weight)
        self.edge_sum += edge_order
        self.edge_square_sum += edge_order * edge_order
        while support:
            bit = support & -support
            self.vertex_degrees[bit.bit_length() - 1] += 1
            support ^= bit

    def finalize(self, identity_coefficient: complex) -> dict[str, float | int]:
        if abs(complex(identity_coefficient).imag) > COMPLEX_RESIDUE_ATOL:
            raise JwEncodingInfeasibleError(
                "nonfinite_or_complex_coefficient",
                "identity coefficient has an unexpected imaginary residue",
            )
        if self.nonidentity_terms == 0:
            raise JwEncodingInfeasibleError(
                "empty_nonidentity_jw_support", "no nonidentity JW term survives"
            )
        touched = self.vertex_degrees[self.vertex_degrees > 0]
        if not len(touched):
            raise JwEncodingInfeasibleError(
                "empty_nonidentity_jw_support", "no qubit is touched"
            )
        term_count = self.nonidentity_terms + int(
            abs(identity_coefficient) >= COEFFICIENT_ATOL
        )
        weight_mean = self.weight_sum / self.nonidentity_terms
        weight_variance = max(
            self.weight_square_sum / self.nonidentity_terms - weight_mean**2, 0.0
        )
        edge_mean = self.edge_sum / self.nonidentity_terms
        edge_variance = max(
            self.edge_square_sum / self.nonidentity_terms - edge_mean**2, 0.0
        )
        vertex_mean = float(np.mean(touched))
        vertex_std = float(np.std(touched, ddof=0))
        edge_std = math.sqrt(edge_variance)
        result: dict[str, float | int] = {
            "max_vertex_degree": int(np.max(touched)),
            "min_vertex_degree": int(np.min(touched)),
            "mean_vertex_degree": vertex_mean,
            "std_dev_vertex_degree": vertex_std,
            "max_weight": self.max_weight,
            "mean_weight": weight_mean,
            "std_dev_weight": math.sqrt(weight_variance),
            "mean_edge_order": edge_mean,
            "std_dev_edge_order": edge_std,
            "number_of_terms": term_count,
            "pauli_terms_per_orbital_quartic": term_count / self.norb**4,
            "mean_vertex_degree_per_orbital": vertex_mean / self.norb,
            "max_vertex_degree_per_orbital": int(np.max(touched)) / self.norb,
            "vertex_degree_coefficient_of_variation": vertex_std / vertex_mean,
            "edge_order_coefficient_of_variation": edge_std / edge_mean,
        }
        if not all(math.isfinite(float(value)) for value in result.values()):
            raise JwEncodingInfeasibleError(
                "nonpositive_derived_denominator", "nonfinite derived statistic"
            )
        return result


def _compute_historical_compatible_sparse(
    data: SparseFcidump,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if data.norb <= 0:
        raise JwEncodingInfeasibleError(
            "invalid_fcidump_header", f"invalid NORB={data.norb}"
        )

    statistics = _SufficientStatistics(data.norb)
    raw_one_body: dict[tuple[int, ...], complex] = defaultdict(complex)
    for p, q in zip(*np.nonzero(data.h1)):
        operators = (("create", int(p)), ("annihilate", int(q)))
        for key, coefficient in _ordered_majorana_terms(
            operators, float(data.h1[p, q])
        ):
            raw_one_body[key] += coefficient

    canonical_one_body, raw_filtered = _canonicalize_historical_raw(raw_one_body)
    raw_term_count = len(raw_one_body)
    identity = canonical_one_body.pop((), 0.0)
    two_majorana: dict[tuple[int, ...], complex] = defaultdict(complex)
    for key, coefficient in canonical_one_body.items():
        if len(key) != 2:
            raise JwEncodingInfeasibleError(
                "nonfinite_or_complex_coefficient",
                f"one-body expansion produced order-{len(key)} Majorana term",
            )
        two_majorana[key] += coefficient

    groups = {
        tuple(sorted(key)) for key, value in data.eri_records.items() if value != 0.0
    }
    streamed_four_majorana = 0
    for group in sorted(groups):
        canonical_group, group_filtered, group_raw_count = _evaluate_quartic_template(
            data, group
        )
        raw_term_count += group_raw_count
        raw_filtered += group_filtered
        for key, coefficient in canonical_group.items():
            if len(key) == 0:
                identity += coefficient
            elif len(key) == 2:
                two_majorana[key] += coefficient
            elif len(key) == 4:
                statistics.emit(key, coefficient)
                streamed_four_majorana += int(abs(coefficient) >= COEFFICIENT_ATOL)
            else:
                raise JwEncodingInfeasibleError(
                    "nonfinite_or_complex_coefficient",
                    f"quartic expansion produced order-{len(key)} Majorana term",
                )

    for key, coefficient in two_majorana.items():
        statistics.emit(key, coefficient)
    features = statistics.finalize(identity)
    audit = {
        "extractor_version": JW_ENCODING_VERSION,
        "route": "sparse_multiset_historical_two_stage_threshold",
        "norb": data.norb,
        "two_body_input_record_count": data.two_body_input_records,
        "two_body_unique_record_count": len(data.eri_records),
        "integral_multiset_group_count": len(groups),
        "historical_ordered_majorana_key_count": raw_term_count,
        "historical_raw_terms_filtered": raw_filtered,
        "two_majorana_accumulator_count": len(two_majorana),
        "streamed_four_majorana_survivor_count": streamed_four_majorana,
        "nonidentity_pauli_term_count": statistics.nonidentity_terms,
        "identity_survives": abs(identity) >= COEFFICIENT_ATOL,
        "coefficient_absolute_threshold": COEFFICIENT_ATOL,
    }
    return features, audit


def compute_jw_encoding_features(
    path: str | Path, *, ms2_override: int | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compute all 15 exact G58 columns without a dense ERI or Pauli object."""
    try:
        data = read_sparse_fcidump(
            path,
            strict_duplicates=True,
            ms2_override=ms2_override,
        )
    except ValueError as exc:
        message = str(exc)
        reason = (
            "conflicting_symmetry_records"
            if "Conflicting" in message
            else "invalid_fcidump_header"
        )
        raise JwEncodingInfeasibleError(reason, message) from exc
    return _compute_historical_compatible_sparse(data)
