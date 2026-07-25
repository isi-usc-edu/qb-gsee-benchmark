"""Focused tests for the ML-8C gradeable-mask sensitivity annex."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from qb_gsee_benchmark.ml.g50_gradeable_mask_sensitivity import (
    COMPARISON_COLUMNS,
    GRADEABLE_GROWTH_COLUMNS,
    PREREGISTRATION_ID,
    _positive_lower_bound_count,
    build_comparison_table,
    build_gradeable_growth_table,
    gradeable_selection_weights,
    load_mask,
    load_sensitivity_preregistration,
)
from qb_gsee_benchmark.ml.g50_solver_families_run import GROWTH_COLUMNS

PREREGISTRATION = Path(
    "analysis/ml_g50_solver_families/sensitivity_preregistration_gradeable_mask.json"
)


def test_preregistration_is_frozen_and_supersedes_nothing():
    payload = load_sensitivity_preregistration(PREREGISTRATION)
    assert payload["artifact_id"] == PREREGISTRATION_ID
    assert payload["frozen_before_masked_results"] is True
    assert payload["supersedes"] is None
    assert payload["parent_bytes_must_be_unchanged"] is True
    assert payload["mask"]["hand_listed"] is False
    assert payload["mask"]["expected_retained_tasks"] == 80
    assert payload["equivalence_guard"][
        "assert_regenerated_parent_observations_byte_identical"
    ] is True
    assert (
        payload["gradeable_population_reweighting"]["orphan_policy"]
        == "disclosed, never reassigned"
    )
    assert payload["comparison_contract"]["parent_values"][
        "with_jw_ap_lower_bound_above_size_sector_count"
    ] == 0


def test_preregistration_holds_every_parent_knob_identical():
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    parent = json.loads(
        Path("analysis/ml_g50_solver_families/preregistration.json").read_text(
            encoding="utf-8"
        )
    )
    held = payload["held_identical_to_parent"]
    assert held["k"] == parent["model"]["k"]
    assert held["model_seed"] == parent["seeds"]["model"]
    assert held["bootstrap_seed"] == parent["bootstrap"]["seed"]
    assert (
        held["accepted_two_class_draws"] == parent["bootstrap"]["accepted_two_class_draws"]
    )
    assert held["eligibility_floor"] == parent["model_eligibility_floor"]
    assert held["metrics"] == parent["evaluation"]["metrics"]
    assert held["baselines"] == parent["model"]["baselines"]
    assert held["protocol"] == parent["evaluation"]["protocol"]


def test_growth_columns_swap_only_the_two_population_fields():
    assert len(GRADEABLE_GROWTH_COLUMNS) == len(GROWTH_COLUMNS)
    assert "selection_weighted_population_success_rate" not in GRADEABLE_GROWTH_COLUMNS
    assert "population_rate_status" not in GRADEABLE_GROWTH_COLUMNS
    assert (
        "gradeable_selection_weighted_population_success_rate"
        in GRADEABLE_GROWTH_COLUMNS
    )
    assert "gradeable_population_rate_status" in GRADEABLE_GROWTH_COLUMNS
    unchanged = set(GROWTH_COLUMNS) - {
        "selection_weighted_population_success_rate",
        "population_rate_status",
    }
    assert unchanged <= set(GRADEABLE_GROWTH_COLUMNS)


def test_gradeable_weights_restrict_and_disclose_orphans(tmp_path):
    assignments = pd.DataFrame(
        [
            # center A is retained; two gradeable tasks and one non-gradeable map to it
            {"task_uuid": "A", "selected_task_uuid": "A"},
            {"task_uuid": "t1", "selected_task_uuid": "A"},
            {"task_uuid": "t2", "selected_task_uuid": "A"},
            {"task_uuid": "ng1", "selected_task_uuid": "A"},
            # center B is retained with only itself
            {"task_uuid": "B", "selected_task_uuid": "B"},
            # center M is masked; its gradeable members are orphaned, not reassigned
            {"task_uuid": "M", "selected_task_uuid": "M"},
            {"task_uuid": "t3", "selected_task_uuid": "M"},
        ]
    )
    path = tmp_path / "coverage_assignments_718.csv"
    assignments.to_csv(path, index=False)
    preregistration = {
        "inputs": {"coverage_assignments_718": {"path": path.name}}
    }
    gradeable = {
        "A": True,
        "t1": True,
        "t2": True,
        "ng1": False,
        "B": True,
        "M": False,
        "t3": True,
    }
    # the module asserts the corpus row count; patch it for the fixture size
    import qb_gsee_benchmark.ml.g50_gradeable_mask_sensitivity as module

    original = module.EXPECTED_CORPUS_TASKS
    module.EXPECTED_CORPUS_TASKS = len(assignments)
    try:
        result = gradeable_selection_weights(
            tmp_path, preregistration, ["A", "B"], gradeable
        )
    finally:
        module.EXPECTED_CORPUS_TASKS = original

    assert result["weights"] == {"A": 3, "B": 1}
    assert result["gradeable_population_total"] == 5
    assert result["gradeable_population_covered"] == 4
    assert result["gradeable_population_orphaned"] == 1
    assert result["orphaned_task_uuids"] == ["t3"]
    assert result["gradeable_population_coverage_fraction"] == pytest.approx(0.8)


def test_growth_table_reports_not_estimable_on_an_incomplete_panel():
    variants = [
        {
            "solver_family_id": "fam",
            "solver_short_name": "v1",
            "solver_uuid": "u1",
            "solver_variant_id": "vid",
            "resource_ladder_id": None,
            "resource_axis_name": None,
            "resource_value": None,
            "resource_units": None,
            "resource_rank": None,
        }
    ]
    observations = pd.DataFrame(
        [
            {"solver_uuid": "u1", "task_uuid": "A", "observed_outcome": "success"},
            {"solver_uuid": "u1", "task_uuid": "B", "observed_outcome": "fail"},
        ]
    )
    coverage = pd.DataFrame(
        [
            {"solver_uuid": "u1", "task_uuid": "A"},
            {"solver_uuid": "u1", "task_uuid": "B"},
            {"solver_uuid": "u1", "task_uuid": "C"},
        ]
    )
    predictions = pd.DataFrame(
        columns=["solver_uuid", "feature_arm", "predicted_outcome"]
    )
    complete = build_gradeable_growth_table(
        variants, observations, coverage, predictions, {"A", "B"}, {"A": 7, "B": 3}
    )
    assert complete[0][
        "gradeable_selection_weighted_population_success_rate"
    ] == pytest.approx(0.7)
    assert (
        complete[0]["gradeable_population_rate_status"]
        == "estimated_covered_gradeable_subpopulation_80_task_panel"
    )
    partial = build_gradeable_growth_table(
        variants, observations, coverage, predictions, {"A", "B", "C"}, {"A": 7, "B": 3}
    )
    assert partial[0]["gradeable_selection_weighted_population_success_rate"] is None
    assert (
        partial[0]["gradeable_population_rate_status"]
        == "not_estimable_incomplete_or_censored_panel"
    )


def test_positive_lower_bound_count_only_counts_strictly_positive_ap_bounds():
    deltas = [
        {
            "comparison": "with_jw_vs_size_sector",
            "metric": "average_precision_success",
            "lower_95": 0.01,
        },
        {
            "comparison": "with_jw_vs_size_sector",
            "metric": "average_precision_success",
            "lower_95": 0.0,
        },
        {
            "comparison": "with_jw_vs_size_sector",
            "metric": "average_precision_success",
            "lower_95": -0.2,
        },
        {
            "comparison": "with_jw_vs_size_sector",
            "metric": "roc_auc",
            "lower_95": 0.5,
        },
        {
            "comparison": "with_jw_vs_without_jw",
            "metric": "average_precision_success",
            "lower_95": 0.3,
        },
    ]
    assert _positive_lower_bound_count(deltas, "with_jw_vs_size_sector") == 1
    assert _positive_lower_bound_count(deltas, "with_jw_vs_without_jw") == 1
    assert _positive_lower_bound_count([], "with_jw_vs_size_sector") == 0


def test_comparison_table_pairs_before_and_after_and_flags_status_change():
    variants = [
        {
            "solver_family_id": "fam",
            "solver_short_name": "v1",
            "solver_uuid": "u1",
            "solver_variant_id": "vid1",
            "resource_ladder_id": "ladder",
            "resource_value": 1,
        }
    ]
    parent_eligibility = pd.DataFrame(
        [
            {
                "solver_uuid": "u1",
                "n_labels": 96,
                "n_success": 42,
                "n_fail": 54,
                "model_status": "eligible",
            }
        ]
    )
    parent_deltas = pd.DataFrame(
        [
            {
                "solver_uuid": "u1",
                "comparison": "with_jw_vs_size_sector",
                "metric": "average_precision_success",
                "point_improvement": -0.1,
                "lower_95": -0.3,
            }
        ]
    )
    masked_eligibility = [
        {
            "solver_uuid": "u1",
            "n_labels": 80,
            "n_success": 42,
            "n_fail": 38,
            "model_status": "insufficient_data",
        }
    ]
    rows = build_comparison_table(
        variants, parent_eligibility, parent_deltas, masked_eligibility, []
    )
    assert set(rows[0]) == set(COMPARISON_COLUMNS)
    assert rows[0]["n_labels_before"] == 96
    assert rows[0]["n_labels_after"] == 80
    assert rows[0]["n_success_before"] == rows[0]["n_success_after"] == 42
    assert rows[0]["model_status_before"] == "eligible"
    assert rows[0]["model_status_after"] == "insufficient_data"
    assert rows[0]["with_jw_vs_size_sector_ap_delta_before"] == pytest.approx(-0.1)
    # no masked deltas were supplied, so the "after" side is absent, not zero
    assert rows[0]["with_jw_vs_size_sector_ap_delta_after"] is None
    assert rows[0]["with_jw_vs_without_jw_ap_lower_95_before"] is None


def test_load_mask_rejects_a_census_disagreeing_with_its_own_cross_check(tmp_path):
    census = pd.DataFrame(
        [
            {
                "task_uuid": "A",
                "gradeable_for_campaign_scoring": True,
                "gradeability_reason": "gradeable",
            },
            {
                "task_uuid": "B",
                "gradeable_for_campaign_scoring": False,
                "gradeability_reason": "excluded_test_tier",
            },
        ]
    )
    census.to_csv(tmp_path / "census.csv", index=False)
    (tmp_path / "report.json").write_text(
        json.dumps({"panel_cross_check": {"not_gradeable_task_uuids": ["A"]}}),
        encoding="utf-8",
    )
    preregistration = {
        "inputs": {
            "gradeability_census": {"path": "census.csv"},
            "gradeability_census_report": {"path": "report.json"},
        },
        "mask": {
            "expected_panel_tasks": 2,
            "expected_masked_tasks": 1,
            "expected_retained_tasks": 1,
        },
    }
    with pytest.raises(ValueError, match="panel cross-check"):
        load_mask(tmp_path, preregistration, ["A", "B"])
