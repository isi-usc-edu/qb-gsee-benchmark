"""Focused tests for the ML-8B / ML-5c gradeable-eligible reselection."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from qb_gsee_benchmark.ml.core_set_v2_gradeable import (
    AMENDMENT_ID,
    CALIBRATION_VERDICT,
    PRIMARY_MODE,
    SECONDARY_MODE,
    SELECTION_K,
    load_amendment,
    select_pure,
    select_retain_and_extend,
    verify_candidate_metric_placement,
    voronoi_weights,
)
from qb_gsee_benchmark.ml.core_set import global_farthest_first

AMENDMENT = Path("analysis/ml_core_set_v2/amendment_ml5c_gradeable_reselection.json")


def test_amendment_is_frozen_held_and_supersedes_nothing():
    payload = load_amendment(AMENDMENT)
    assert payload["artifact_id"] == AMENDMENT_ID
    assert payload["frozen_before_selection_output"] is True
    assert payload["supersedes"] is None
    assert payload["binding_selection"] is False
    assert payload["promotion_commit_in_this_wave"] is False
    assert payload["outcome_blind"] is True
    assert (
        payload["manifest_of_record_unchanged"]
        == "d1627e66e65f5ea33fcb8e4092a28def44ee6ad6111804df96e541135483959e"
    )


def test_amendment_holds_the_binding_doctrine_unchanged():
    payload = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    doctrine = payload["unchanged_doctrine"]
    assert doctrine["k"] == SELECTION_K == 96
    assert doctrine["mode"] == "floor_free"
    assert doctrine["algorithm"] == "global_farthest_first"
    assert doctrine["seed"] == 20260714
    assert doctrine["family_used_for_selection"] is False
    assert doctrine["family_used_for_assignment"] is False
    assert doctrine["family_floor_constraint"] is False
    assert doctrine["pca_variance_threshold"] == 0.95
    assert doctrine["scaling"] == "zscore"
    assert doctrine["universal_only"] is False


def test_amendment_declares_the_two_weight_populations_distinctly():
    payload = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    weights = payload["weight_sets"]
    assert weights["selection_weights_609"]["sums_to"] == 609
    assert (
        weights["selection_weights_609"][
            "admissible_for_population_statements"
        ]
        is True
    )
    assert weights["coverage_weights_718"]["sums_to"] == 718
    assert (
        weights["coverage_weights_718"][
            "admissible_for_population_statements"
        ]
        is False
    )


def test_amendment_flags_the_column_divergence_without_ruling_on_it():
    payload = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    divergence = payload["column_metric_divergence"]
    assert divergence["flagged"] is True
    assert divergence["scientifically_material"] is True
    assert divergence["introduced_by_ml5c"] is False
    assert divergence["pre_existing_in_the_accepted_record"] is True
    assert divergence["ml5_binding_metric"]["columns"] == 191
    assert divergence["g50_chain_metric"]["columns"] == 193
    assert divergence["extra_columns"] == ["max_edge_order", "min_edge_order"]
    assert divergence["extra_column_coverage"] == 184
    assert divergence["resolution"]["ml5c_rules_on_canonical_metric"] is False


def test_amendment_keeps_the_ml8d_adjudication_verbatim():
    payload = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    layer = payload["deployment_target_layer"]
    assert layer["adjudication_language_verbatim"] == CALIBRATION_VERDICT
    assert layer["validated_predictor_claim"] is False
    assert layer["calibration_certified_variants"] == 0
    assert layer["ratio_of_record"] == "design_based"
    assert layer["ml6_no_validated_predictor_rule"] == "stands_unamended"
    assert layer["tasks"] == 109


def test_amendment_marks_secondary_mode_as_not_a_doctrine_change():
    payload = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    modes = {record["name"]: record for record in payload["modes"]}
    assert modes[PRIMARY_MODE]["role"] == "PRIMARY"
    assert modes[PRIMARY_MODE]["is_the_ordered_deliverable"] is True
    assert modes[SECONDARY_MODE]["changes_primary"] is False
    assert modes[SECONDARY_MODE]["changes_doctrine"] is False


def _ring_distance(n: int) -> np.ndarray:
    positions = np.arange(n, dtype=float)
    return np.abs(positions[:, None] - positions[None, :])


def test_select_pure_restricted_to_candidates_never_leaves_the_candidate_set():
    distance = _ring_distance(10)
    tasks = [f"task-{index:02d}" for index in range(10)]
    candidates = [0, 2, 4, 6, 8]
    chosen, curve = select_pure(distance, candidates, tasks, k=3, seed=7)
    assert set(chosen) <= set(candidates)
    assert len(set(chosen)) == 3
    assert [row["k"] for row in curve] == [1, 2, 3]
    # coverage radius is monotone non-increasing in k
    radii = [row["coverage_radius"] for row in curve]
    assert all(later <= earlier + 1e-12 for earlier, later in zip(radii, radii[1:]))


def test_select_pure_matches_the_frozen_selector_on_the_submatrix():
    distance = _ring_distance(12)
    tasks = [f"t{index:02d}" for index in range(12)]
    candidates = [1, 3, 5, 7, 9, 11]
    chosen, _ = select_pure(distance, candidates, tasks, k=4, seed=20260714)
    submatrix = distance[np.ix_(candidates, candidates)]
    local_tasks = [tasks[index] for index in candidates]
    expected, _ = global_farthest_first(submatrix, local_tasks, max_k=4, seed=20260714)
    assert chosen == [candidates[position] for position in expected]


def test_select_pure_is_deterministic_under_the_frozen_seed():
    distance = _ring_distance(20)
    tasks = [f"t{index:02d}" for index in range(20)]
    candidates = list(range(0, 20, 2))
    first, _ = select_pure(distance, candidates, tasks, k=5, seed=20260714)
    second, _ = select_pure(distance, candidates, tasks, k=5, seed=20260714)
    assert first == second


def test_retain_and_extend_keeps_every_incumbent_and_fills_the_budget():
    distance = _ring_distance(12)
    tasks = [f"t{index:02d}" for index in range(12)]
    candidates = list(range(12))
    retained = [0, 5]
    chosen, curve = select_retain_and_extend(
        distance, candidates, tasks, retained, k=5, seed=20260714
    )
    assert chosen[: len(retained)] == retained
    assert set(retained) <= set(chosen)
    assert len(set(chosen)) == 5
    assert [row["k"] for row in curve] == [2, 3, 4, 5]


def test_retain_and_extend_rejects_an_incumbent_outside_the_candidate_set():
    distance = _ring_distance(8)
    tasks = [f"t{index}" for index in range(8)]
    with pytest.raises(ValueError, match="retained center is not a candidate"):
        select_retain_and_extend(
            distance, [0, 1, 2, 3], tasks, [5], k=3, seed=1
        )


def test_voronoi_weights_sum_over_the_declared_population_only():
    distance = _ring_distance(10)
    tasks = [f"t{index}" for index in range(10)]
    centers = [0, 9]
    population = [0, 1, 2, 9]
    result = voronoi_weights(distance, centers, population, tasks, seed=1)
    assert result["population_size"] == 4
    assert sum(result["counts"].values()) == 4
    # tasks 0,1,2 are nearest to center 0; task 9 to center 9
    assert result["counts"][0] == 3
    assert result["counts"][9] == 1
    full = voronoi_weights(distance, centers, list(range(10)), tasks, seed=1)
    assert sum(full["counts"].values()) == 10


def test_candidate_placement_detects_an_unshared_block_pair():
    shared = np.ones((4, 4), dtype=int)
    good = verify_candidate_metric_placement(shared, [0, 1, 2, 3], ["a", "b", "c", "d"])
    assert good["all_candidates_placeable"] is True
    assert good["unplaceable_task_uuids"] == []
    shared[1, 3] = 0
    shared[3, 1] = 0
    bad = verify_candidate_metric_placement(shared, [0, 1, 2, 3], ["a", "b", "c", "d"])
    assert bad["all_candidates_placeable"] is False
    assert bad["minimum_shared_blocks_among_candidates"] == 0
    assert bad["unplaceable_task_uuids"] == ["b", "d"]
