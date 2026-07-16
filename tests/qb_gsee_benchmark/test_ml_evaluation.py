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

import math

import numpy as np
import pandas as pd
import pytest

from qb_gsee_benchmark.ml.data import (
    SIZE_ONLY_FEATURES,
    assemble_solver_ml_table,
    coerce_bool_series,
)
from qb_gsee_benchmark.ml.evaluation import (
    MODEL_MAJORITY_CLASS,
    calibration_curve_dataframe,
    compute_metrics,
    evaluate_oof_classifier,
    evaluate_standard_comparators,
    family_leave_one_out_protocol,
    make_default_protocols,
)
from qb_gsee_benchmark.ml.importance import grouped_permutation_importance
from qb_gsee_benchmark.ml.maps import empirical_coverage_by_group, fit_feature_embedding
from qb_gsee_benchmark.ml.models import MODEL_LOGISTIC_L2, build_probability_model


def _synthetic_solver_table():
    rows = []
    for idx in range(16):
        label = idx % 2 == 0
        family = f"family_{idx % 4}"
        category = "cat_a" if idx < 8 else "cat_b"
        rows.append(
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "task_uuid": f"task-{idx}",
                "problem_instance_short_name": f"mol_{idx % 4}",
                "family": family,
                "category": category,
                "label": label,
                "attempted": True,
                "signal": 1.0 if label else 0.0,
                "n_elec": 2 + idx,
                "n_orbs": 4 + idx,
            }
        )
    return pd.DataFrame(rows)


def _mixed_family_solver_table():
    rows = []
    for idx in range(24):
        label = (idx // 4) % 2 == 0
        family = f"family_{idx % 4}"
        rows.append(
            {
                "solver_short_name": "SolverA",
                "solver_uuid": "solver-a",
                "task_uuid": f"mixed-task-{idx}",
                "problem_instance_short_name": f"mol_{idx % 4}",
                "family": family,
                "category": "cat_a" if idx < 12 else "cat_b",
                "label": label,
                "attempted": True,
                "signal": 1.0 if label else 0.0,
                "noise": float(idx % 3),
                "n_elec": 2 + idx,
                "n_orbs": 4 + idx,
            }
        )
    return pd.DataFrame(rows)


def test_coerce_bool_series_rejects_unknown_values():
    assert coerce_bool_series(pd.Series(["true", "0", 1])).tolist() == [True, False, True]
    with pytest.raises(ValueError):
        coerce_bool_series(pd.Series(["yes"]))


def test_assemble_solver_ml_table_filters_attempted_test_tier_and_adds_family(monkeypatch):
    monkeypatch.setattr(
        "qb_gsee_benchmark.ml.data.canonical_problem_family",
        lambda short_name, *, task_uuid: "prototype_transition_metal_atoms_monoxides",
    )
    labels = pd.DataFrame(
        [
            {
                "solver_uuid": "solver-a",
                "solver_short_name": "SolverA",
                "task_uuid": "task-1",
                "problem_instance_short_name": "FeO_0",
                "attempted": "true",
                "label": "1",
                "curation_tier": "expanded",
                "n_elec": 999,
            },
            {
                "solver_uuid": "solver-a",
                "solver_short_name": "SolverA",
                "task_uuid": "task-2",
                "problem_instance_short_name": "cl2_0",
                "attempted": "false",
                "label": "0",
                "curation_tier": "expanded",
                "n_elec": 999,
            },
            {
                "solver_uuid": "solver-a",
                "solver_short_name": "SolverA",
                "task_uuid": "task-test",
                "problem_instance_short_name": "test_instance",
                "attempted": "true",
                "label": "1",
                "curation_tier": "test",
                "n_elec": 999,
            },
        ]
    )
    features = pd.DataFrame(
        [
            {"task_uuid": "task-1", "n_elec": 10, "n_orbs": 20},
            {"task_uuid": "task-2", "n_elec": 2, "n_orbs": 4},
            {"task_uuid": "task-test", "n_elec": 1, "n_orbs": 1},
        ]
    )

    assembled = assemble_solver_ml_table(labels, features, SIZE_ONLY_FEATURES)

    assert set(assembled["task_uuid"]) == {"task-1"}
    assert len(assembled) == 1
    assert assembled.loc[0, "family"] == "prototype_transition_metal_atoms_monoxides"
    assert assembled.loc[0, "category"] == "unknown"
    assert assembled.loc[0, "n_elec"] == 10
    assert bool(assembled.loc[0, "label"]) is True


def test_build_probability_model_accepts_known_models():
    model = build_probability_model(MODEL_LOGISTIC_L2, seed=123)

    assert model.steps[-1][0] == "model"


def test_make_default_protocols_includes_grouped_and_random_protocols():
    data = _synthetic_solver_table()
    y = data["label"].to_numpy(dtype=bool)

    protocols = make_default_protocols(data, y, seed=123)
    protocol_names = [protocol.name for protocol in protocols]

    assert "family_groupkfold_4" in protocol_names
    assert "leave_one_category_out" in protocol_names
    assert "random_5fold" in protocol_names


def test_family_leave_one_out_protocol_is_exact_and_opt_in():
    data = _synthetic_solver_table()
    y = data["label"].to_numpy(dtype=bool)

    default_names = [protocol.name for protocol in make_default_protocols(data, y, seed=123)]
    assert "leave_one_family_out" not in default_names

    protocol = family_leave_one_out_protocol(data)
    assert protocol is not None
    splits = list(protocol.splitter.split(data, y, data[protocol.group_column]))
    assert len(splits) == data["family"].nunique()
    held_out_families = [set(data.iloc[test_idx]["family"]) for _, test_idx in splits]
    assert all(len(families) == 1 for families in held_out_families)

    opt_in_names = [
        protocol.name
        for protocol in make_default_protocols(
            data,
            y,
            seed=123,
            include_family_leave_one_out=True,
        )
    ]
    assert "leave_one_family_out" in opt_in_names


def test_evaluate_standard_comparators_returns_oof_outputs():
    data = _synthetic_solver_table()
    y = data["label"].to_numpy(dtype=bool)
    protocols = make_default_protocols(data, y, seed=123)

    results, predictions, folds, calibration = evaluate_standard_comparators(
        data=data,
        feature_sets={"signal": ["signal"], "size_only": SIZE_ONLY_FEATURES},
        protocols=protocols,
        model_names=[MODEL_LOGISTIC_L2],
        bootstrap_resamples=0,
        seed=123,
    )

    assert len(results) == len(protocols) * 3
    assert set(results["feature_set"]) == {"signal", "size_only", MODEL_MAJORITY_CLASS}
    assert predictions["oof_probability"].notna().all()
    assert set(predictions["model"]) == {MODEL_LOGISTIC_L2, MODEL_MAJORITY_CLASS}
    assert folds["n_test"].sum() == len(data) * len(results)
    assert set(calibration.columns) >= {
        "solver_short_name",
        "solver_uuid",
        "protocol",
        "model",
        "feature_set",
        "bin",
        "n",
    }
    assert calibration["solver_uuid"].eq("solver-a").all()
    assert results["empirical_instance_coverage"].between(0.0, 1.0).all()


def test_compute_metrics_single_class_marks_rank_metrics_undefined():
    y_true = np.array([True, True, True])
    y_score = np.array([0.8, 0.7, 0.6])
    y_pred = np.array([True, True, True])

    metrics = compute_metrics(y_true, y_score, y_pred)

    assert math.isnan(metrics["auroc"])
    assert math.isnan(metrics["average_precision"])
    assert metrics["mcc"] == 0.0
    assert metrics["brier"] >= 0.0


def test_calibration_curve_dataframe_has_requested_bins():
    curve = calibration_curve_dataframe(
        np.array([False, True, True]),
        np.array([0.1, 0.6, 0.9]),
        n_bins=5,
    )

    assert len(curve) == 5
    assert curve["n"].sum() == 3


def test_evaluate_oof_classifier_can_tune_hyperparameters():
    data = _mixed_family_solver_table()
    y = data["label"].to_numpy(dtype=bool)
    protocol = make_default_protocols(data, y, seed=123)[0]

    evaluation = evaluate_oof_classifier(
        data=data,
        feature_columns=["signal"],
        protocol=protocol,
        model_name=MODEL_LOGISTIC_L2,
        feature_set_name="signal",
        bootstrap_resamples=0,
        seed=123,
        hyperparameter_tuning=True,
        parameter_grid={"model__C": [0.1, 1.0]},
        inner_cv_splits=2,
    )

    assert evaluation.summary["hyperparameter_tuning"] is True
    assert evaluation.folds["hyperparameter_tuned"].any()
    assert evaluation.folds["best_params"].str.contains("model__C").any()


def test_fit_feature_embedding_returns_coordinates_and_loadings():
    data = _synthetic_solver_table()

    pca = fit_feature_embedding(data, ["signal", "n_elec", "n_orbs"], method="pca")
    nnmf = fit_feature_embedding(data, ["signal", "n_elec", "n_orbs"], method="nnmf")

    assert {"pca_component_1", "pca_component_2"}.issubset(pca.coordinates.columns)
    assert pca.loadings["feature"].tolist() == ["signal", "n_elec", "n_orbs"]
    assert len(pca.metadata["explained_variance_ratio"]) == 2
    assert {"nnmf_component_1", "nnmf_component_2"}.issubset(nnmf.coordinates.columns)
    assert "reconstruction_error" in nnmf.metadata


def test_empirical_coverage_by_group_summarizes_predictions():
    predictions = pd.DataFrame(
        [
            {"category": "a", "oof_probability": 0.8},
            {"category": "a", "oof_probability": 0.2},
            {"category": "b", "oof_probability": 0.9},
        ]
    )

    coverage = empirical_coverage_by_group(predictions, group_column="category", threshold=0.5)

    assert coverage.set_index("category").loc["a", "empirical_instance_coverage"] == 0.5
    assert coverage.set_index("category").loc["b", "empirical_instance_coverage"] == 1.0


def test_grouped_permutation_importance_scores_features():
    data = _mixed_family_solver_table()
    y = data["label"].to_numpy(dtype=bool)
    protocol = make_default_protocols(data, y, seed=123)[0]

    importance = grouped_permutation_importance(
        data=data,
        feature_columns=["signal", "noise"],
        protocol=protocol,
        model_name=MODEL_LOGISTIC_L2,
        n_repeats=2,
        seed=123,
    )

    assert set(importance["feature"]) == {"signal", "noise"}
    assert importance["n_permutations_scored"].sum() > 0
    assert importance.iloc[0]["mean_importance"] >= importance.iloc[-1]["mean_importance"]
