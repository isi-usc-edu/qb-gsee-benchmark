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

"""Grouped-CV permutation importance for QB-GSEE ML v2."""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.exceptions import UndefinedMetricWarning

from qb_gsee_benchmark.ml.evaluation import CVProtocol, protocol_splits, safe_metric
from qb_gsee_benchmark.ml.models import MODEL_LOGISTIC_L2, build_probability_model


def _metric_prediction_labels(scores: np.ndarray, threshold: float) -> np.ndarray:
    return scores >= threshold


def grouped_permutation_importance(
        data: pd.DataFrame,
        feature_columns: list[str],
        protocol: CVProtocol,
        model_name: str = MODEL_LOGISTIC_L2,
        label_column: str = "label",
        metric_name: str = "average_precision",
        n_repeats: int = 5,
        seed: int = 6,
        threshold: float = 0.5,
    ) -> pd.DataFrame:
    """Estimate feature importance by permuting held-out folds only.

    A fresh model is trained in each outer fold.  Importance is the drop in the
    requested metric after permuting one feature within the held-out fold.
    Undefined fold metrics are skipped rather than silently treated as zero.
    """
    if label_column not in data:
        raise ValueError(f"label column {label_column!r} is missing")
    missing_features = set(feature_columns) - set(data.columns)
    if missing_features:
        raise ValueError(f"data missing feature columns: {sorted(missing_features)}")
    if n_repeats < 1:
        raise ValueError("n_repeats must be positive")

    rng = np.random.default_rng(seed)
    y = data[label_column].to_numpy(dtype=bool)
    drops: dict[str, list[float]] = {feature: [] for feature in feature_columns}

    for fold_idx, (train_idx, test_idx) in enumerate(protocol_splits(protocol, data, y)):
        y_train = y[train_idx]
        y_test = y[test_idx]
        if len(np.unique(y_train)) < 2:
            continue
        model = build_probability_model(model_name, seed + fold_idx)
        x_train = data.iloc[train_idx][feature_columns]
        x_test = data.iloc[test_idx][feature_columns]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UndefinedMetricWarning)
            model.fit(x_train, y_train)
            base_score = model.predict_proba(x_test)[:, 1]
        base_metric = safe_metric(
            metric_name,
            y_test,
            base_score,
            _metric_prediction_labels(base_score, threshold),
        )
        if math.isnan(base_metric):
            continue

        for feature in feature_columns:
            for _ in range(n_repeats):
                permuted = x_test.copy()
                permuted[feature] = rng.permutation(permuted[feature].to_numpy())
                permuted_score = model.predict_proba(permuted)[:, 1]
                permuted_metric = safe_metric(
                    metric_name,
                    y_test,
                    permuted_score,
                    _metric_prediction_labels(permuted_score, threshold),
                )
                if not math.isnan(permuted_metric):
                    drops[feature].append(float(base_metric - permuted_metric))

    rows: list[dict[str, Any]] = []
    for feature, values in drops.items():
        if values:
            mean_importance = float(np.mean(values))
            std_importance = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
        else:
            mean_importance = np.nan
            std_importance = np.nan
        rows.append(
            {
                "feature": feature,
                "metric": metric_name,
                "mean_importance": mean_importance,
                "std_importance": std_importance,
                "n_permutations_scored": int(len(values)),
                "protocol": protocol.name,
                "model": model_name,
            }
        )
    return pd.DataFrame(rows).sort_values(
        "mean_importance",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)
