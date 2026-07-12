import numpy as np
import pytest

from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump
from qb_gsee_benchmark.features.orderability_features import (
    compute_orderability_features,
    cut_profile,
    interaction_graph,
    pair_space_cut_effective_rank,
)


def _data(norb: int, h1: np.ndarray, eri: dict) -> SparseFcidump:
    return SparseFcidump(
        norb=norb,
        nelec=2,
        ms2=0,
        h1=h1,
        eri_records=eri,
        ecore=0.0,
        one_body_duplicate_orientations=0,
        one_body_duplicate_max_abs_difference=0.0,
        one_body_duplicate_max_rel_difference=0.0,
        one_body_symmetry_conflict_records=0,
        two_body_input_records=len(eri),
        two_body_duplicate_orientations=0,
        two_body_duplicate_max_abs_difference=0.0,
        two_body_duplicate_max_rel_difference=0.0,
        two_body_symmetry_conflict_records=0,
        container_format="plain",
        container_member=None,
        ms2_source="fcidump_header",
    )


def test_cut_profile_for_unit_chain() -> None:
    weights = np.zeros((4, 4))
    for left, right in ((0, 1), (1, 2), (2, 3)):
        weights[left, right] = weights[right, left] = 1.0
    assert cut_profile(weights, np.arange(4)) == pytest.approx([1.0, 1.0, 1.0])
    assert cut_profile(weights, np.array([0, 2, 1, 3])) == pytest.approx(
        [1.0, 3.0, 1.0]
    )


def test_interaction_graph_uses_exchange_block_frobenius_norm() -> None:
    data = _data(2, np.array([[0.0, 0.25], [0.25, 0.0]]), {(0, 0, 1, 1): 0.5})
    weights = interaction_graph(data)
    assert weights[0, 1] == pytest.approx(0.75)
    assert weights[1, 0] == pytest.approx(0.75)


def test_pair_space_effective_rank_detects_rank_one_cut() -> None:
    data = _data(2, np.zeros((2, 2)), {(0, 0, 1, 1): 0.5})
    assert pair_space_cut_effective_rank(data, np.arange(2), 1) == pytest.approx(1.0)


def test_orderability_panel_is_deterministic() -> None:
    h1 = np.zeros((4, 4))
    for left, right in ((0, 1), (1, 2), (2, 3)):
        h1[left, right] = h1[right, left] = 1.0
    data = _data(4, h1, {})
    first = compute_orderability_features(data)
    second = compute_orderability_features(data)
    assert first == second
    assert first["cut_weight_best_max"] == pytest.approx(1.0)
    assert first["min_fill_width_upper_bound"] == 1
    assert first["mpo_pair_rank_max"] == 0.0
