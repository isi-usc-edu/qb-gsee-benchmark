# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Hamiltonian orderability and coefficient-matricization features."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import reverse_cuthill_mckee

from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump, read_sparse_fcidump

ORDERABILITY_VERSION = "g40_p1c_orderability_v2"
RANDOM_ORDER_SEED = 40041
HEURISTIC_NAMES = ("fiedler", "rcm", "minimum_degree", "linear_relaxation")
PROFILE_METRICS = ("max", "p95", "sum")


def interaction_graph(data: SparseFcidump) -> np.ndarray:
    """Build |h_pq| plus the Frobenius norm of the V_(pr),(qs) block."""
    weights = np.abs(data.h1)
    exchange_squares = np.zeros((data.norb, data.norb), dtype=float)
    for (p, r, q, s), value in data.iter_eri_entries():
        exchange_squares[p, q] += value * value
    weights = weights + np.sqrt(exchange_squares)
    weights = 0.5 * (weights + weights.T)
    np.fill_diagonal(weights, 0.0)
    return weights


def _ordered_eigenvector(matrix: np.ndarray, which: int = 1) -> np.ndarray:
    if len(matrix) <= 1:
        return np.arange(len(matrix), dtype=int)
    _, vectors = np.linalg.eigh(matrix)
    vector = vectors[:, min(which, len(matrix) - 1)]
    pivot = int(np.argmax(np.abs(vector)))
    if vector[pivot] < 0.0:
        vector = -vector
    return np.lexsort((np.arange(len(matrix)), vector))


def fiedler_order(weights: np.ndarray) -> np.ndarray:
    degree = np.sum(weights, axis=1)
    laplacian = np.diag(degree) - weights
    return _ordered_eigenvector(laplacian)


def linear_relaxation_order(weights: np.ndarray) -> np.ndarray:
    degree = np.sum(weights, axis=1)
    inverse_sqrt = np.zeros_like(degree)
    positive = degree > 0.0
    inverse_sqrt[positive] = 1.0 / np.sqrt(degree[positive])
    normalized = np.eye(len(weights)) - (
        inverse_sqrt[:, None] * weights * inverse_sqrt[None, :]
    )
    normalized[~positive, ~positive] = 0.0
    return _ordered_eigenvector(normalized)


def rcm_order(weights: np.ndarray) -> np.ndarray:
    adjacency = sparse.csr_matrix(weights > 0.0)
    return reverse_cuthill_mckee(adjacency, symmetric_mode=True)


def _elimination_order(
    adjacency: np.ndarray, *, min_fill: bool
) -> tuple[np.ndarray, int]:
    graph = adjacency.copy().astype(bool)
    active = np.ones(len(graph), dtype=bool)
    order: list[int] = []
    width = 0
    while np.any(active):
        candidates = []
        for vertex in np.flatnonzero(active):
            neighbors = np.flatnonzero(graph[vertex] & active)
            if min_fill and len(neighbors) > 1:
                induced = graph[np.ix_(neighbors, neighbors)]
                existing = int(np.count_nonzero(np.triu(induced, 1)))
                fill = len(neighbors) * (len(neighbors) - 1) // 2 - existing
            else:
                fill = 0
            key = (
                (fill, len(neighbors), vertex) if min_fill else (len(neighbors), vertex)
            )
            candidates.append((key, vertex, neighbors))
        _, vertex, neighbors = min(candidates, key=lambda item: item[0])
        width = max(width, len(neighbors))
        graph[np.ix_(neighbors, neighbors)] = True
        np.fill_diagonal(graph, False)
        active[vertex] = False
        order.append(vertex)
    return np.asarray(order, dtype=int), width


def minimum_degree_order(weights: np.ndarray) -> np.ndarray:
    return _elimination_order(weights > 0.0, min_fill=False)[0]


def min_fill_width_upper_bound(weights: np.ndarray) -> int:
    return _elimination_order(weights > 0.0, min_fill=True)[1]


def cut_profile(weights: np.ndarray, order: np.ndarray) -> np.ndarray:
    if len(order) <= 1:
        return np.zeros(0, dtype=float)
    permuted = weights[np.ix_(order, order)]
    return np.asarray(
        [np.sum(permuted[:cut, cut:]) for cut in range(1, len(order))],
        dtype=float,
    )


def _profile_summary(profile: np.ndarray) -> dict[str, float]:
    if profile.size == 0:
        return {metric: 0.0 for metric in PROFILE_METRICS}
    return {
        "max": float(np.max(profile)),
        "p95": float(np.percentile(profile, 95)),
        "sum": float(np.sum(profile)),
    }


def pair_space_cut_effective_rank(
    data: SparseFcidump, order: np.ndarray, cut: int
) -> float:
    """Return the exact Renyi-2 rank of V_(pr),(qs) across one orbital cut."""
    left = order[:cut]
    right = order[cut:]
    if not len(left) or not len(right):
        return 0.0
    left_index = {orbital: index for index, orbital in enumerate(left)}
    right_index = {orbital: index for index, orbital in enumerate(right)}
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    for (p, r, q, s), value in data.iter_eri_entries():
        if (
            p in left_index
            and r in left_index
            and q in right_index
            and s in right_index
        ):
            rows.append(left_index[p] * len(left) + left_index[r])
            columns.append(right_index[q] * len(right) + right_index[s])
            values.append(value)
    if not values:
        return 0.0
    matrix = sparse.coo_matrix(
        (values, (rows, columns)),
        shape=(len(left) ** 2, len(right) ** 2),
    ).tocsr()
    frobenius_square = float(np.dot(matrix.data, matrix.data))
    if matrix.shape[0] <= matrix.shape[1]:
        gram = matrix @ matrix.T
    else:
        gram = matrix.T @ matrix
    fourth_sum = float(np.dot(gram.data, gram.data))
    return 0.0 if fourth_sum == 0.0 else frobenius_square**2 / fourth_sum


def mpo_pair_rank_applicable(data: SparseFcidump) -> bool:
    """Return false when every nonzero interaction is strictly on-site."""
    return any(len({p, q, r, s}) > 1 for p, q, r, s in data.eri_records)


def compute_orderability_features(
    source: str | Path | SparseFcidump,
    *,
    ms2_override: int | None = None,
    random_seed: int = RANDOM_ORDER_SEED,
) -> dict[str, Any]:
    """Compute the shared-space G40 P1-C orderability and MPO panels."""
    data = (
        source
        if isinstance(source, SparseFcidump)
        else read_sparse_fcidump(source, ms2_override=ms2_override)
    )
    weights = interaction_graph(data)
    orders = {
        "fiedler": fiedler_order(weights),
        "rcm": rcm_order(weights),
        "minimum_degree": minimum_degree_order(weights),
        "linear_relaxation": linear_relaxation_order(weights),
    }
    rng = np.random.default_rng(random_seed)
    baselines = {
        "file": np.arange(data.norb, dtype=int),
        "random": rng.permutation(data.norb),
    }
    summaries = {
        name: _profile_summary(cut_profile(weights, order))
        for name, order in {**orders, **baselines}.items()
    }
    result: dict[str, Any] = {
        "orderability_random_seed": random_seed,
        "interaction_graph_edge_count": int(np.count_nonzero(np.triu(weights, 1))),
        "interaction_graph_total_weight": float(np.sum(np.triu(weights, 1))),
        "min_fill_width_upper_bound": min_fill_width_upper_bound(weights),
        "mpo_pair_rank_applicable": mpo_pair_rank_applicable(data),
        "orderability_features_version": ORDERABILITY_VERSION,
    }
    for name in (*HEURISTIC_NAMES, "file", "random"):
        for metric in PROFILE_METRICS:
            result[f"cut_weight_{name}_{metric}"] = summaries[name][metric]

    for metric in PROFILE_METRICS:
        heuristic_values = {name: summaries[name][metric] for name in HEURISTIC_NAMES}
        best_name, best_value = min(
            heuristic_values.items(), key=lambda item: (item[1], item[0])
        )
        result[f"cut_weight_best_{metric}"] = best_value
        result[f"cut_weight_best_{metric}_heuristic"] = best_name
        for baseline in ("file", "random"):
            denominator = summaries[baseline][metric]
            result[f"cut_weight_improvement_vs_{baseline}_{metric}"] = (
                0.0 if denominator == 0.0 else 1.0 - best_value / denominator
            )
        maximum = max(heuristic_values.values())
        minimum = min(heuristic_values.values())
        result[f"cut_weight_heuristic_spread_{metric}"] = (
            0.0 if maximum == 0.0 else (maximum - minimum) / maximum
        )

    selected_name = min(
        HEURISTIC_NAMES,
        key=lambda name: (summaries[name]["sum"], name),
    )
    selected_order = orders[selected_name]
    ranks = np.asarray(
        [
            pair_space_cut_effective_rank(data, selected_order, cut)
            for cut in range(1, data.norb)
        ],
        dtype=float,
    )
    result["mpo_ordering_heuristic"] = selected_name
    result["mpo_pair_rank_max"] = float(np.max(ranks, initial=0.0))
    result["mpo_pair_rank_p95"] = (
        0.0 if ranks.size == 0 else float(np.percentile(ranks, 95))
    )
    result["mpo_pair_rank_mean"] = float(np.mean(ranks)) if ranks.size else 0.0
    return result
