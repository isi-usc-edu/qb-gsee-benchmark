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

"""Embedding helpers for QB-GSEE map artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF, PCA
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from qb_gsee_benchmark.ml.models import build_imputer


@dataclass(frozen=True)
class EmbeddingResult:
    """Coordinates plus fitted model metadata for a 2D feature embedding."""

    coordinates: pd.DataFrame
    loadings: pd.DataFrame
    metadata: dict[str, Any]


def _id_columns(df: pd.DataFrame) -> list[str]:
    preferred = [
        "task_uuid",
        "problem_instance_short_name",
        "family",
        "category",
    ]
    return [column for column in preferred if column in df]


def _build_pipeline(method: str, n_components: int, seed: int) -> Pipeline:
    if method == "pca":
        return Pipeline(
            steps=[
                ("imputer", build_imputer(add_indicator=False)),
                ("scaler", StandardScaler()),
                ("embedding", PCA(n_components=n_components, random_state=seed)),
            ]
        )
    if method in {"nnmf", "nmf"}:
        return Pipeline(
            steps=[
                ("imputer", build_imputer(add_indicator=False)),
                ("scaler", MinMaxScaler()),
                (
                    "embedding",
                    NMF(
                        n_components=n_components,
                        init="nndsvda",
                        max_iter=1000,
                        random_state=seed,
                    ),
                ),
            ]
        )
    raise ValueError(f"Unknown embedding method {method}")


def fit_feature_embedding(
        df: pd.DataFrame,
        feature_columns: list[str],
        method: str = "pca",
        n_components: int = 2,
        seed: int = 6,
    ) -> EmbeddingResult:
    """Fit a PCA or NNMF embedding and return task-coordinate artifacts."""
    missing_features = set(feature_columns) - set(df.columns)
    if missing_features:
        raise ValueError(f"data missing feature columns: {sorted(missing_features)}")
    if n_components < 1:
        raise ValueError("n_components must be positive")

    pipeline = _build_pipeline(method=method, n_components=n_components, seed=seed)
    coordinates = pipeline.fit_transform(df[feature_columns])
    embedding = pipeline.named_steps["embedding"]

    coordinate_df = df[_id_columns(df)].copy()
    for component_idx in range(n_components):
        coordinate_df[f"{method}_component_{component_idx + 1}"] = coordinates[:, component_idx]

    loadings = pd.DataFrame(
        embedding.components_.T,
        columns=[f"{method}_component_{idx + 1}" for idx in range(n_components)],
    )
    loadings.insert(0, "feature", feature_columns)

    metadata: dict[str, Any] = {
        "method": method,
        "n_components": n_components,
        "n_rows": int(len(df)),
        "feature_columns": list(feature_columns),
    }
    if hasattr(embedding, "explained_variance_ratio_"):
        metadata["explained_variance_ratio"] = [
            float(value) for value in embedding.explained_variance_ratio_
        ]
    if hasattr(embedding, "reconstruction_err_"):
        metadata["reconstruction_error"] = float(embedding.reconstruction_err_)
    return EmbeddingResult(coordinates=coordinate_df, loadings=loadings, metadata=metadata)


def empirical_coverage_by_group(
        predictions: pd.DataFrame,
        group_column: str = "category",
        probability_column: str = "oof_probability",
        threshold: float = 0.5,
    ) -> pd.DataFrame:
    """Summarize empirical predicted-solvable coverage by a metadata group."""
    if group_column not in predictions:
        raise ValueError(f"predictions missing group column {group_column}")
    if probability_column not in predictions:
        raise ValueError(f"predictions missing probability column {probability_column}")

    rows = []
    for group_value, group_df in predictions.groupby(group_column, sort=True):
        probabilities = group_df[probability_column].to_numpy(dtype=float)
        finite = np.isfinite(probabilities)
        if not np.any(finite):
            coverage = np.nan
            mean_probability = np.nan
        else:
            coverage = float(np.mean(probabilities[finite] >= threshold))
            mean_probability = float(np.mean(probabilities[finite]))
        rows.append(
            {
                group_column: group_value,
                "n_tasks": int(len(group_df)),
                "empirical_instance_coverage": coverage,
                "mean_probability": mean_probability,
                "threshold": float(threshold),
            }
        )
    return pd.DataFrame(rows)
