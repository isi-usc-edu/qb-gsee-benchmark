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

"""Out-of-fold evaluation helpers for QB-GSEE ML v2."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.exceptions import UndefinedMetricWarning
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    matthews_corrcoef,
    roc_auc_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    GroupKFold,
    KFold,
    LeaveOneGroupOut,
    StratifiedKFold,
)

from qb_gsee_benchmark.ml.models import (
    MODEL_LOGISTIC_L2,
    build_probability_model,
    default_param_grid,
)


MODEL_MAJORITY_CLASS = "majority_class"
METRIC_NAMES = ["auroc", "average_precision", "mcc", "brier"]


@dataclass(frozen=True)
class CVProtocol:
    """A cross-validation splitter plus the optional grouping column it uses."""

    name: str
    splitter: Any
    group_column: str | None = None


@dataclass(frozen=True)
class OOFEvaluation:
    """Container for one out-of-fold evaluation result."""

    summary: dict[str, Any]
    predictions: pd.DataFrame
    folds: pd.DataFrame
    calibration: pd.DataFrame


def protocol_splits(
        protocol: CVProtocol,
        data: pd.DataFrame,
        y: np.ndarray,
    ) -> list[tuple[np.ndarray, np.ndarray]]:
    """Return train/test index splits for one protocol."""
    if protocol.group_column is not None:
        groups = data[protocol.group_column].to_numpy()
        return list(protocol.splitter.split(data, y, groups))
    return list(protocol.splitter.split(data, y))


def family_leave_one_out_protocol(
        data: pd.DataFrame,
        family_column: str = "family",
    ) -> CVProtocol | None:
    """Return exact leave-one-family-out protocol when at least two families exist."""
    if family_column not in data:
        return None
    if int(data[family_column].nunique(dropna=True)) < 2:
        return None
    return CVProtocol(
        name="leave_one_family_out",
        splitter=LeaveOneGroupOut(),
        group_column=family_column,
    )


def make_default_protocols(
        data: pd.DataFrame,
        y: np.ndarray,
        seed: int = 6,
        max_splits: int = 5,
        family_column: str = "family",
        category_column: str = "category",
        include_family_leave_one_out: bool = False,
    ) -> list[CVProtocol]:
    """Build standard family-grouped, category-LOO, and random protocols."""
    protocols: list[CVProtocol] = []

    if family_column in data:
        n_family_groups = int(data[family_column].nunique(dropna=True))
        if n_family_groups >= 2:
            n_splits = min(max_splits, n_family_groups)
            protocols.append(
                CVProtocol(
                    name=f"family_groupkfold_{n_splits}",
                    splitter=GroupKFold(n_splits=n_splits),
                    group_column=family_column,
                )
            )
            if include_family_leave_one_out:
                protocols.append(
                    CVProtocol(
                        name="leave_one_family_out",
                        splitter=LeaveOneGroupOut(),
                        group_column=family_column,
                    )
                )

    if category_column in data and data[category_column].nunique(dropna=True) >= 2:
        protocols.append(
            CVProtocol(
                name="leave_one_category_out",
                splitter=LeaveOneGroupOut(),
                group_column=category_column,
            )
        )

    class_counts = np.bincount(y.astype(int), minlength=2)
    min_class_count = int(class_counts.min())
    if min_class_count >= 2:
        random_splits = min(max_splits, min_class_count)
        protocols.append(
            CVProtocol(
                name=f"random_{random_splits}fold",
                splitter=StratifiedKFold(
                    n_splits=random_splits,
                    shuffle=True,
                    random_state=seed,
                ),
            )
        )
    elif len(y) >= 2:
        random_splits = min(max_splits, len(y))
        protocols.append(
            CVProtocol(
                name=f"random_{random_splits}fold",
                splitter=KFold(
                    n_splits=random_splits,
                    shuffle=True,
                    random_state=seed,
                ),
            )
        )

    return protocols


def _held_out_groups(protocol: CVProtocol, data: pd.DataFrame, test_idx: np.ndarray) -> dict[str, str]:
    if protocol.group_column is None:
        return {}
    return {
        protocol.group_column: ",".join(
            sorted(map(str, data.iloc[test_idx][protocol.group_column].unique()))
        )
    }


def majority_oof(
        data: pd.DataFrame,
        y: np.ndarray,
        protocol: CVProtocol,
    ) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    """Compute fold-local majority-class out-of-fold predictions."""
    probabilities = np.full(len(data), np.nan, dtype=float)
    predictions = np.full(len(data), False, dtype=bool)
    fold_rows: list[dict[str, Any]] = []

    for fold_idx, (train_idx, test_idx) in enumerate(protocol_splits(protocol, data, y)):
        y_train = y[train_idx]
        train_positive_rate = float(np.mean(y_train)) if len(y_train) else 0.0
        probabilities[test_idx] = train_positive_rate
        predictions[test_idx] = train_positive_rate >= 0.5
        fold_rows.append(
            {
                "fold": fold_idx,
                "n_train": int(len(train_idx)),
                "n_test": int(len(test_idx)),
                "train_positive": int(y_train.sum()),
                "test_positive": int(y[test_idx].sum()),
                "used_constant_fallback": True,
                "hyperparameter_tuned": False,
                "best_params": "{}",
                **_held_out_groups(protocol, data, test_idx),
            }
        )
    return probabilities, predictions, fold_rows



def _make_inner_cv(
        train_data: pd.DataFrame,
        y_train: np.ndarray,
        protocol: CVProtocol,
        seed: int,
        max_splits: int = 3,
    ) -> tuple[Any, np.ndarray | None]:
    """Build an inner CV splitter that preserves grouping when possible."""
    class_counts = np.bincount(y_train.astype(int), minlength=2)
    min_class_count = int(class_counts.min())
    if protocol.group_column is not None and protocol.group_column in train_data:
        groups = train_data[protocol.group_column].to_numpy()
        n_groups = int(pd.Series(groups).nunique(dropna=True))
        if n_groups >= 2:
            return GroupKFold(n_splits=min(max_splits, n_groups)), groups

    if min_class_count >= 2:
        return StratifiedKFold(
            n_splits=min(max_splits, min_class_count),
            shuffle=True,
            random_state=seed,
        ), None
    return KFold(
        n_splits=min(max_splits, len(y_train)),
        shuffle=True,
        random_state=seed,
    ), None


def _fit_probability_model(
        x_train: pd.DataFrame,
        y_train: np.ndarray,
        train_data: pd.DataFrame,
        protocol: CVProtocol,
        model_name: str,
        seed: int,
        hyperparameter_tuning: bool,
        parameter_grid: dict[str, list[object]] | None,
        inner_cv_splits: int,
    ) -> tuple[Any, dict[str, object], bool]:
    """Fit a probability model, optionally with grouped inner GridSearchCV."""
    model = build_probability_model(model_name, seed)
    grid = default_param_grid(model_name) if parameter_grid is None else parameter_grid
    if not hyperparameter_tuning or not grid:
        model.fit(x_train, y_train)
        return model, {}, False

    inner_cv, groups = _make_inner_cv(
        train_data=train_data,
        y_train=y_train,
        protocol=protocol,
        seed=seed,
        max_splits=inner_cv_splits,
    )
    search = GridSearchCV(
        estimator=model,
        param_grid=grid,
        scoring="average_precision",
        cv=inner_cv,
        error_score=np.nan,
        refit=True,
    )
    try:
        if groups is None:
            search.fit(x_train, y_train)
        else:
            search.fit(x_train, y_train, groups=groups)
    except ValueError:
        model.fit(x_train, y_train)
        return model, {}, False
    best_params = {key: value for key, value in search.best_params_.items()}
    return search.best_estimator_, best_params, True

def fit_predict_oof(
        data: pd.DataFrame,
        y: np.ndarray,
        protocol: CVProtocol,
        feature_columns: list[str],
        model_name: str = MODEL_LOGISTIC_L2,
        seed: int = 6,
        hyperparameter_tuning: bool = False,
        parameter_grid: dict[str, list[object]] | None = None,
        inner_cv_splits: int = 3,
    ) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    """Fit fold-local models and return out-of-fold probabilities."""
    if not feature_columns:
        raise ValueError("feature_columns must be non-empty for model-based OOF prediction")

    probabilities = np.full(len(data), np.nan, dtype=float)
    predictions = np.full(len(data), False, dtype=bool)
    fold_rows: list[dict[str, Any]] = []

    for fold_idx, (train_idx, test_idx) in enumerate(protocol_splits(protocol, data, y)):
        y_train = y[train_idx]
        train_positive_rate = float(np.mean(y_train)) if len(y_train) else 0.0
        fallback = len(np.unique(y_train)) < 2
        tuned = False
        best_params: dict[str, object] = {}
        if fallback:
            fold_proba = np.full(len(test_idx), train_positive_rate, dtype=float)
        else:
            x_train = data.iloc[train_idx][feature_columns]
            x_test = data.iloc[test_idx][feature_columns]
            train_data = data.iloc[train_idx]
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UndefinedMetricWarning)
                model, best_params, tuned = _fit_probability_model(
                    x_train=x_train,
                    y_train=y_train,
                    train_data=train_data,
                    protocol=protocol,
                    model_name=model_name,
                    seed=seed + fold_idx,
                    hyperparameter_tuning=hyperparameter_tuning,
                    parameter_grid=parameter_grid,
                    inner_cv_splits=inner_cv_splits,
                )
                fold_proba = model.predict_proba(x_test)[:, 1]

        probabilities[test_idx] = fold_proba
        predictions[test_idx] = fold_proba >= 0.5
        fold_rows.append(
            {
                "fold": fold_idx,
                "n_train": int(len(train_idx)),
                "n_test": int(len(test_idx)),
                "train_positive": int(y_train.sum()),
                "test_positive": int(y[test_idx].sum()),
                "used_constant_fallback": bool(fallback),
                "hyperparameter_tuned": bool(tuned),
                "best_params": repr(best_params),
                **_held_out_groups(protocol, data, test_idx),
            }
        )
    return probabilities, predictions, fold_rows


def safe_metric(
        metric_name: str,
        y_true: np.ndarray,
        y_score: np.ndarray,
        y_pred: np.ndarray,
    ) -> float:
    """Compute one metric, returning NaN when the metric is undefined."""
    finite = np.isfinite(y_score)
    y_true = y_true[finite]
    y_score = y_score[finite]
    y_pred = y_pred[finite]
    if len(y_true) == 0:
        return math.nan
    if metric_name in {"auroc", "average_precision"} and len(np.unique(y_true)) < 2:
        return math.nan
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UndefinedMetricWarning)
            warnings.filterwarnings(
                "ignore",
                message="A single label was found in 'y_true' and 'y_pred'.*",
                category=UserWarning,
            )
            if metric_name == "auroc":
                return float(roc_auc_score(y_true, y_score))
            if metric_name == "average_precision":
                return float(average_precision_score(y_true, y_score))
            if metric_name == "mcc":
                return float(matthews_corrcoef(y_true, y_pred))
            if metric_name == "brier":
                return float(brier_score_loss(y_true, y_score))
    except ValueError:
        return math.nan
    raise ValueError(f"Unknown metric {metric_name}")


def compute_metrics(y_true: np.ndarray, y_score: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute standard out-of-fold classification metrics."""
    return {
        metric_name: safe_metric(metric_name, y_true, y_score, y_pred)
        for metric_name in METRIC_NAMES
    }


def bootstrap_cis(
        y_true: np.ndarray,
        y_score: np.ndarray,
        y_pred: np.ndarray,
        n_resamples: int = 200,
        seed: int = 6,
    ) -> dict[str, float]:
    """Bootstrap percentile confidence intervals for standard metrics."""
    values = {metric_name: [] for metric_name in METRIC_NAMES}
    if n_resamples <= 0 or len(y_true) == 0:
        return {
            f"{metric_name}_{suffix}": math.nan
            for metric_name in METRIC_NAMES
            for suffix in ["ci_low", "ci_high"]
        }

    rng = np.random.default_rng(seed)
    indices = np.arange(len(y_true))
    for _ in range(n_resamples):
        sample_idx = rng.choice(indices, size=len(indices), replace=True)
        sample_metrics = compute_metrics(
            y_true[sample_idx],
            y_score[sample_idx],
            y_pred[sample_idx],
        )
        for metric_name, value in sample_metrics.items():
            if not math.isnan(value):
                values[metric_name].append(value)

    ci: dict[str, float] = {}
    for metric_name, metric_values in values.items():
        if metric_values:
            low, high = np.percentile(metric_values, [2.5, 97.5])
            ci[f"{metric_name}_ci_low"] = float(low)
            ci[f"{metric_name}_ci_high"] = float(high)
        else:
            ci[f"{metric_name}_ci_low"] = math.nan
            ci[f"{metric_name}_ci_high"] = math.nan
    return ci


def calibration_curve_dataframe(
        y_true: np.ndarray,
        y_score: np.ndarray,
        n_bins: int = 10,
    ) -> pd.DataFrame:
    """Return equal-width reliability-curve bins."""
    finite = np.isfinite(y_score)
    y_true = y_true[finite]
    y_score = y_score[finite]
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for bin_idx in range(n_bins):
        low = bins[bin_idx]
        high = bins[bin_idx + 1]
        if bin_idx == n_bins - 1:
            in_bin = (y_score >= low) & (y_score <= high)
        else:
            in_bin = (y_score >= low) & (y_score < high)
        if not np.any(in_bin):
            rows.append(
                {
                    "bin": bin_idx,
                    "probability_low": low,
                    "probability_high": high,
                    "n": 0,
                    "mean_probability": math.nan,
                    "observed_positive_rate": math.nan,
                }
            )
            continue
        rows.append(
            {
                "bin": bin_idx,
                "probability_low": low,
                "probability_high": high,
                "n": int(in_bin.sum()),
                "mean_probability": float(np.mean(y_score[in_bin])),
                "observed_positive_rate": float(np.mean(y_true[in_bin])),
            }
        )
    return pd.DataFrame(rows)


def _single_value(data: pd.DataFrame, column: str) -> Any:
    if column not in data or data[column].nunique(dropna=False) != 1:
        return None
    return data[column].iloc[0]


def _prediction_base_columns(data: pd.DataFrame, label_column: str) -> list[str]:
    preferred = [
        "solver_short_name",
        "solver_uuid",
        "task_uuid",
        "problem_instance_short_name",
        "family",
        "category",
        label_column,
    ]
    return [column for column in preferred if column in data]


def evaluate_oof_classifier(
        data: pd.DataFrame,
        feature_columns: list[str],
        protocol: CVProtocol,
        model_name: str = MODEL_LOGISTIC_L2,
        feature_set_name: str = "features",
        label_column: str = "label",
        bootstrap_resamples: int = 200,
        seed: int = 6,
        threshold: float = 0.5,
        n_calibration_bins: int = 10,
        hyperparameter_tuning: bool = False,
        parameter_grid: dict[str, list[object]] | None = None,
        inner_cv_splits: int = 3,
    ) -> OOFEvaluation:
    """Run one model/feature/protocol combination with OOF metrics only."""
    if label_column not in data:
        raise ValueError(f"label column {label_column!r} is missing")
    missing_features = set(feature_columns) - set(data.columns)
    if missing_features:
        raise ValueError(f"data missing feature columns: {sorted(missing_features)}")

    y = data[label_column].to_numpy(dtype=bool)
    if model_name == MODEL_MAJORITY_CLASS:
        probabilities, _, fold_rows = majority_oof(data, y, protocol)
    else:
        probabilities, _, fold_rows = fit_predict_oof(
            data=data,
            y=y,
            protocol=protocol,
            feature_columns=feature_columns,
            model_name=model_name,
            seed=seed,
            hyperparameter_tuning=hyperparameter_tuning,
            parameter_grid=parameter_grid,
            inner_cv_splits=inner_cv_splits,
        )
    predictions = probabilities >= threshold
    metrics = compute_metrics(y, probabilities, predictions)
    metrics.update(bootstrap_cis(y, probabilities, predictions, bootstrap_resamples, seed))

    folds = pd.DataFrame(fold_rows)
    for column, value in [
        ("protocol", protocol.name),
        ("model", model_name),
        ("feature_set", feature_set_name),
    ]:
        folds.insert(0, column, value)

    prediction_columns = _prediction_base_columns(data, label_column)
    prediction_rows = data[prediction_columns].copy()
    prediction_rows["protocol"] = protocol.name
    prediction_rows["model"] = model_name
    prediction_rows["feature_set"] = feature_set_name
    prediction_rows["oof_probability"] = probabilities
    prediction_rows["oof_prediction"] = predictions

    calibration = calibration_curve_dataframe(y, probabilities, n_bins=n_calibration_bins)
    calibration.insert(0, "solver_uuid", _single_value(data, "solver_uuid"))
    calibration.insert(0, "solver_short_name", _single_value(data, "solver_short_name"))
    calibration.insert(0, "feature_set", feature_set_name)
    calibration.insert(0, "model", model_name)
    calibration.insert(0, "protocol", protocol.name)

    summary = {
        "solver_short_name": _single_value(data, "solver_short_name"),
        "solver_uuid": _single_value(data, "solver_uuid"),
        "protocol": protocol.name,
        "model": model_name,
        "feature_set": feature_set_name,
        "n_features": int(len(feature_columns)),
        "n_tasks": int(len(data)),
        "positive_labels": int(y.sum()),
        "negative_labels": int(len(y) - y.sum()),
        "positive_rate": float(np.mean(y)) if len(y) else math.nan,
        "n_families": int(data["family"].nunique()) if "family" in data else math.nan,
        "n_categories": int(data["category"].nunique()) if "category" in data else math.nan,
        "n_splits": int(len(folds)),
        "constant_fallback_folds": int(folds["used_constant_fallback"].sum()) if not folds.empty else 0,
        "threshold": float(threshold),
        "hyperparameter_tuning": bool(hyperparameter_tuning and model_name != MODEL_MAJORITY_CLASS),
        "empirical_instance_coverage": float(np.mean(predictions)) if len(predictions) else math.nan,
        **metrics,
    }
    return OOFEvaluation(summary=summary, predictions=prediction_rows, folds=folds, calibration=calibration)


def evaluate_standard_comparators(
        data: pd.DataFrame,
        feature_sets: dict[str, list[str]],
        protocols: list[CVProtocol] | None = None,
        model_names: list[str] | None = None,
        label_column: str = "label",
        bootstrap_resamples: int = 200,
        seed: int = 6,
        hyperparameter_tuning: bool = False,
        parameter_grids: dict[str, dict[str, list[object]]] | None = None,
        inner_cv_splits: int = 3,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Evaluate feature sets, random/grouped protocols, and majority baseline."""
    y = data[label_column].to_numpy(dtype=bool)
    if protocols is None:
        protocols = make_default_protocols(data, y, seed=seed)
    if model_names is None:
        model_names = [MODEL_LOGISTIC_L2]

    evaluations: list[OOFEvaluation] = []
    for protocol in protocols:
        for feature_set_name, feature_columns in feature_sets.items():
            for model_name in model_names:
                evaluations.append(
                    evaluate_oof_classifier(
                        data=data,
                        feature_columns=feature_columns,
                        protocol=protocol,
                        model_name=model_name,
                        feature_set_name=feature_set_name,
                        label_column=label_column,
                        bootstrap_resamples=bootstrap_resamples,
                        seed=seed,
                        hyperparameter_tuning=hyperparameter_tuning,
                        parameter_grid=(parameter_grids or {}).get(model_name),
                        inner_cv_splits=inner_cv_splits,
                    )
                )
        evaluations.append(
            evaluate_oof_classifier(
                data=data,
                feature_columns=[],
                protocol=protocol,
                model_name=MODEL_MAJORITY_CLASS,
                feature_set_name=MODEL_MAJORITY_CLASS,
                label_column=label_column,
                bootstrap_resamples=bootstrap_resamples,
                seed=seed,
            )
        )

    results = pd.DataFrame([evaluation.summary for evaluation in evaluations])
    predictions = pd.concat([evaluation.predictions for evaluation in evaluations], ignore_index=True)
    folds = pd.concat([evaluation.folds for evaluation in evaluations], ignore_index=True)
    calibration = pd.concat([evaluation.calibration for evaluation in evaluations], ignore_index=True)
    return results, predictions, folds, calibration
