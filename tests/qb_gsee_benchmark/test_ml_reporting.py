# Copyright 2026.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from io import StringIO
import types

import numpy as np
import pandas as pd

from qb_gsee_benchmark.benchmark_data import BenchmarkData
from qb_gsee_benchmark.ml.data import LEGACY_FULL_FEATURES
from qb_gsee_benchmark.ml.reporting import (
    build_ml_v2_report_summary,
    prediction_group_breakdown,
)
from qb_gsee_benchmark.standard_report import StandardReport


def _results_frame():
    return pd.DataFrame(
        [
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "protocol": "family_groupkfold_2",
                "model": "logistic_l2",
                "feature_set": "size_only",
                "average_precision": 0.40,
                "brier": 0.30,
                "empirical_instance_coverage": 0.25,
            },
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "protocol": "family_groupkfold_2",
                "model": "logistic_l2",
                "feature_set": "full16_plus_b2",
                "average_precision": 0.65,
                "brier": 0.15,
                "empirical_instance_coverage": 0.50,
            },
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "protocol": "random_2fold",
                "model": "logistic_l2",
                "feature_set": "full16_plus_b2",
                "average_precision": 0.80,
                "brier": 0.10,
                "empirical_instance_coverage": 0.55,
            },
        ]
    )


def test_prediction_group_breakdown_reports_family_and_category_metrics():
    predictions = pd.DataFrame(
        [
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "protocol": "family_groupkfold_2",
                "model": "logistic_l2",
                "feature_set": "full16_plus_b2",
                "family": "fam_a",
                "category": "cat_a",
                "label": True,
                "oof_probability": 0.8,
            },
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "protocol": "family_groupkfold_2",
                "model": "logistic_l2",
                "feature_set": "full16_plus_b2",
                "family": "fam_a",
                "category": "cat_a",
                "label": "false",
                "oof_probability": 0.7,
            },
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "protocol": "family_groupkfold_2",
                "model": "logistic_l2",
                "feature_set": "full16_plus_b2",
                "family": "fam_b",
                "category": "cat_b",
                "label": False,
                "oof_probability": 0.2,
            },
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "protocol": "random_2fold",
                "model": "logistic_l2",
                "feature_set": "full16_plus_b2",
                "family": "fam_a",
                "category": "cat_a",
                "label": True,
                "oof_probability": 0.1,
            },
        ]
    )

    breakdown = prediction_group_breakdown(predictions)
    category_rows = breakdown[breakdown["group_type"] == "category"].set_index("group")
    family_rows = breakdown[breakdown["group_type"] == "family"].set_index("group")

    assert set(category_rows.index) == {"cat_a", "cat_b"}
    assert set(family_rows.index) == {"fam_a", "fam_b"}
    assert category_rows.loc["cat_a", "n_tasks"] == 2
    assert category_rows.loc["cat_a", "true_positive"] == 1
    assert category_rows.loc["cat_a", "false_positive"] == 1
    assert np.isclose(category_rows.loc["cat_a", "precision"], 0.5)
    assert np.isclose(category_rows.loc["cat_a", "recall"], 1.0)
    assert np.isclose(category_rows.loc["cat_a", "f1"], 2.0 / 3.0)
    assert np.isclose(category_rows.loc["cat_b", "brier"], 0.04)
    assert breakdown["protocol"].eq("family_groupkfold_2").all()


def test_prediction_group_breakdown_sets_f1_zero_when_group_misses_positives():
    predictions = pd.DataFrame(
        [
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "protocol": "family_groupkfold_2",
                "model": "logistic_l2",
                "feature_set": "full16_plus_b2",
                "family": "fam_a",
                "category": "cat_a",
                "label": True,
                "oof_probability": 0.1,
            },
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "protocol": "family_groupkfold_2",
                "model": "logistic_l2",
                "feature_set": "full16_plus_b2",
                "family": "fam_a",
                "category": "cat_a",
                "label": False,
                "oof_probability": 0.2,
            },
        ]
    )

    row = prediction_group_breakdown(predictions)
    row = row[row["group_type"] == "category"].iloc[0]

    assert np.isnan(row["precision"])
    assert row["recall"] == 0.0
    assert row["f1"] == 0.0


def test_build_ml_v2_report_summary_is_json_safe_and_compact():
    results = _results_frame()
    calibration = pd.DataFrame(
        [
            {
                "protocol": "family_groupkfold_2",
                "model": "logistic_l2",
                "feature_set": "full16_plus_b2",
                "bin": 0,
                "mean_probability": np.nan,
                "observed_positive_rate": np.nan,
            }
        ]
    )
    labels = pd.DataFrame({"outcome": ["solved", "failed-runtime", "solved"]})

    summary = build_ml_v2_report_summary(results, calibration, labels)

    assert summary["primary_result"]["feature_set"] == "full16_plus_b2"
    comparison = summary["family_grouped_feature_comparison"]
    assert np.isclose(comparison["full16_plus_b2_minus_size_only_average_precision"], 0.25)
    assert np.isclose(summary["random_vs_grouped_leakage"][0]["average_precision_random_minus_grouped"], 0.15)
    assert summary["calibration"][0]["mean_probability"] is None
    assert summary["two_channel_outcome_counts"] == {"solved": 2, "failed-runtime": 1}


class _FakeMiniML:
    def __init__(self, solver_labels_by_task_uuid, hamiltonian_features_by_task_uuid):
        self.ml_solvability_ratio = {"PCA": 0.5}
        self.ml_model_notes = ["fake legacy model"]
        self.f1_score = (0.1, 0.2, 0.3, None)


def _benchmark_data_for_ml_scores():
    benchmark_data = object.__new__(BenchmarkData)
    benchmark_data.solvers_dict = {
        "solver-a": {"solver_uuid": "solver-a", "solver_short_name": "SolverA"}
    }
    rows = []
    feature_rows = []
    for idx in range(16):
        label = idx % 2 == 0
        task_uuid = f"task-{idx}"
        rows.append(
            {
                "solver_uuid": "solver-a",
                "solver_short_name": "SolverA",
                "task_uuid": task_uuid,
                "problem_instance_short_name": f"mol_{idx % 4}",
                "family": f"family_{idx % 4}",
                "category": "cat_a" if idx < 8 else "cat_b",
                "attempted": True,
                "label": label,
                "reference_energy": -1.0,
                "outcome": "solved" if label else "failed-accuracy",
            }
        )
        feature_row = {"task_uuid": task_uuid}
        for feature_idx, feature in enumerate(LEGACY_FULL_FEATURES):
            feature_row[feature] = float(idx + feature_idx + 1)
        feature_row["df_eig_decay_exponent"] = 1.0 + idx
        feature_row["one_norm_per_orbital"] = 2.0 + idx
        feature_row["df_rank_per_orbital"] = 3.0 + idx
        feature_row["mp2_corr_energy_per_electron"] = -0.01 * (idx + 1)
        feature_rows.append(feature_row)
    benchmark_data.aggregated_solver_labels_df = pd.DataFrame(rows)
    benchmark_data.hamiltonian_features = pd.DataFrame(feature_rows)
    return benchmark_data


def test_calculate_ml_scores_adds_ml_v2_without_importing_legacy_miniml(monkeypatch):
    fake_module = types.ModuleType("qb_gsee_benchmark.mini_ml")
    fake_module.MiniML = _FakeMiniML
    monkeypatch.setitem(sys.modules, "qb_gsee_benchmark.mini_ml", fake_module)
    monkeypatch.setattr(
        "qb_gsee_benchmark.ml.data.canonical_problem_family",
        lambda short_name, *, task_uuid: short_name.replace("mol_", "family_"),
    )
    benchmark_data = _benchmark_data_for_ml_scores()

    scores = benchmark_data.calculate_ml_scores()

    solver_scores = scores["solver-a"]
    assert solver_scores["legacy_solvability_ratio"] == 0.5
    assert solver_scores["solvability_ratio"] == 0.5
    assert solver_scores["ml_v2"]["primary_result"]["model"] == "logistic_l2"
    assert solver_scores["ml_v2"]["family_grouped_feature_comparison"]
    assert solver_scores["ml_v2"]["two_channel_outcome_counts"] == {
        "solved": 8,
        "failed-accuracy": 8,
    }

    all_data = benchmark_data.aggregated_solver_labels_df.copy()
    all_data["problem_instance_uuid"] = "problem-a"
    all_data["solution_uuid"] = "11111111-1111-1111-1111-111111111111"
    all_data["instance_data_object_uuid"] = [f"22222222-2222-2222-2222-{idx:012d}" for idx in range(len(all_data))]
    all_data["solved_within_run_time"] = all_data["label"]
    all_data["solved_within_accuracy_requirement"] = all_data["label"]
    all_data["submitted_by_calendar_due_date"] = True
    all_data["overall_run_time_seconds"] = 1.0
    benchmark_data.all_data_df = all_data
    benchmark_data.timestamp = "2026-07-03T00:00:00+00:00"

    performance_metrics = benchmark_data.calculate_performance_metrics()[0]

    assert performance_metrics["$schema"].endswith("performance_metrics.schema.0.0.2.json")
    assert performance_metrics["ml_metrics"]["ml_v2"]["primary_result"]["model"] == "logistic_l2"


def test_standard_report_ml_summary_line_labels_oof_and_legacy_metrics():
    report = object.__new__(StandardReport)
    output = StringIO()
    ml_metrics = {
        "legacy_solvability_ratio": 0.7,
        "f1_score": [0.1, 0.2, 0.3, None],
        "ml_v2": {
            "primary_result": {
                "average_precision": 0.65,
                "brier": 0.15,
                "empirical_instance_coverage": 0.5,
            },
            "family_grouped_feature_comparison": {
                "full16_plus_b2_minus_size_only_average_precision": 0.25,
            },
            "random_vs_grouped_leakage": [
                {
                    "feature_set": "full16_plus_b2",
                    "average_precision_random_minus_grouped": 0.15,
                }
            ],
        },
    }

    report._write_ml_summary_line(output, "SolverA", "solver-a", ml_metrics)
    rendered = output.getvalue()

    assert "ML v2 family-grouped AP: 0.650" in rendered
    assert "AP(full16+B2 - size-only): 0.250" in rendered
    assert "random-minus-grouped AP: 0.150" in rendered
    assert "Legacy MiniML grid solvability ratio (not OOF): 0.700" in rendered


def test_standard_report_ml_v2_leaderboard_marks_size_only_delta():
    report = object.__new__(StandardReport)
    report.benchmark_data = types.SimpleNamespace(
        solvers_dict={
            "solver-a": {"solver_uuid": "solver-a", "solver_short_name": "SolverA"},
            "solver-b": {"solver_uuid": "solver-b", "solver_short_name": "SolverB"},
        }
    )
    performance_metrics_by_solver = {
        "solver-a": {
            "top_level_results": {
                "number_of_tasks_attempted": 16,
                "number_of_tasks_solved": 10,
            },
            "ml_metrics": {
                "legacy_solvability_ratio": 0.7,
                "ml_v2": {
                    "primary_result": {
                        "average_precision": 0.65,
                        "brier": 0.15,
                        "empirical_instance_coverage": 0.5,
                    },
                    "family_grouped_feature_comparison": {
                        "full16_plus_b2_minus_size_only_average_precision": 0.25,
                    },
                },
            },
        },
        "solver-b": {
            "top_level_results": {
                "number_of_tasks_attempted": 12,
                "number_of_tasks_solved": 4,
            },
            "ml_metrics": {
                "legacy_solvability_ratio": 0.2,
                "ml_v2": {
                    "primary_result": {
                        "average_precision": 0.40,
                        "brier": 0.22,
                        "empirical_instance_coverage": 0.3,
                    },
                    "family_grouped_feature_comparison": {
                        "full16_plus_b2_minus_size_only_average_precision": -0.02,
                    },
                },
            },
        },
    }
    output = StringIO()

    report._write_ml_v2_leaderboard_table(output, performance_metrics_by_solver)
    rendered = output.getvalue()

    assert "ML v2 Out-of-Fold Leaderboard" in rendered
    assert "Beats size-only?" in rendered
    assert "SolverA (solver-a)" in rendered
    assert "| SolverA (solver-a) | 16 | 10 | 0.650 | 0.150 | 0.500 | 0.250 | Yes | 0.700 |" in rendered
    assert "| SolverB (solver-b) | 12 | 4 | 0.400 | 0.220 | 0.300 | -0.020 | No | 0.200 |" in rendered


def test_standard_report_ml_v2_leaderboard_handles_missing_delta():
    report = object.__new__(StandardReport)
    report.benchmark_data = types.SimpleNamespace(
        solvers_dict={
            "solver-c": {"solver_uuid": "solver-c", "solver_short_name": "SolverC"},
        }
    )
    output = StringIO()

    report._write_ml_v2_leaderboard_table(output, {"solver-c": {"ml_metrics": {}}})
    rendered = output.getvalue()

    assert "| SolverC (solver-c) | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |" in rendered


def test_standard_report_ml_metrics_block_renders_two_channel_table():
    report = object.__new__(StandardReport)
    output = StringIO()
    ml_metrics = {
        "legacy_solvability_ratio": 0.7,
        "f1_score": [0.1, 0.2, 0.3, None],
        "ml_v2": {
            "primary_model": "logistic_l2",
            "primary_result": {
                "protocol": "family_groupkfold_2",
                "feature_set": "full16_plus_b2",
                "average_precision": 0.65,
                "brier": 0.15,
                "empirical_instance_coverage": 0.5,
            },
            "family_grouped_feature_comparison": {
                "full16_plus_b2_minus_size_only_average_precision": 0.25,
            },
            "two_channel_outcome_counts": {
                "failed-accuracy": 3,
                "solved": 5,
            },
        },
    }

    report._write_ml_metrics_block(output, ml_metrics)
    rendered = output.getvalue()

    assert "two_channel_outcome_counts: {'failed-accuracy': 3, 'solved': 5}" in rendered
    assert "| outcome | count |" in rendered
    assert "| failed-accuracy | 3 |" in rendered
    assert "| solved | 5 |" in rendered


def test_standard_report_ml_v2_calibration_plot_uses_primary_feature_rows(tmp_path):
    report = object.__new__(StandardReport)
    report.full_artifact_directory_path = str(tmp_path)
    report.benchmark_data = types.SimpleNamespace(
        performance_metrics_list=[
            {
                "solver_uuid": "solver-a",
                "solver_short_name": "SolverA",
                "ml_metrics": {
                    "ml_v2": {
                        "calibration": [
                            {
                                "feature_set": "full16",
                                "mean_probability": 0.1,
                                "observed_positive_rate": 0.2,
                                "n": 10,
                            },
                            {
                                "feature_set": "full16_plus_b2",
                                "mean_probability": 0.7,
                                "observed_positive_rate": 0.6,
                                "n": 5,
                            },
                        ]
                    }
                },
            }
        ]
    )

    rows = report._calibration_rows_for_primary_features(
        report.benchmark_data.performance_metrics_list[0]["ml_metrics"]["ml_v2"]
    )
    report.create_plot_ml_v2_calibration_curves()

    assert [row["feature_set"] for row in rows] == ["full16_plus_b2"]
    assert (tmp_path / report._ml_v2_calibration_plot_filename("solver-a")).exists()
