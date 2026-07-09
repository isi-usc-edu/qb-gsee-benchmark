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

"""Compact report/JSON summaries for ML v2 evaluation artifacts."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


PRIMARY_MODEL = "logistic_l2"
PRIMARY_PROTOCOL_PREFIX = "family_groupkfold"
PRIMARY_FEATURE_SET = "full16_plus_b2"
LEGACY_FULL_FEATURE_SET = "full16"
SIZE_ONLY_FEATURE_SET = "size_only"


def json_safe_value(value: Any) -> Any:
    """Convert pandas/numpy scalars and NaN values to JSON-safe Python values."""
    if value is None:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, np.ndarray):
        return [json_safe_value(item) for item in value.tolist()]
    if pd.isna(value):
        return None
    return value


def dataframe_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return dataframe records with JSON-safe scalar values."""
    return [
        {key: json_safe_value(value) for key, value in record.items()}
        for record in df.to_dict(orient="records")
    ]


def primary_family_grouped_row(results: pd.DataFrame) -> dict[str, Any] | None:
    """Pick the primary family-grouped logistic row for report headline use."""
    if results.empty:
        return None
    grouped = results[
        results["protocol"].astype(str).str.startswith(PRIMARY_PROTOCOL_PREFIX)
        & (results["model"] == PRIMARY_MODEL)
    ]
    if grouped.empty:
        return None
    preferred = grouped[grouped["feature_set"] == PRIMARY_FEATURE_SET]
    if preferred.empty:
        preferred = grouped[grouped["feature_set"] == LEGACY_FULL_FEATURE_SET]
    if preferred.empty:
        preferred = grouped
    return {
        key: json_safe_value(value)
        for key, value in preferred.iloc[0].to_dict().items()
    }


def family_grouped_feature_comparison(results: pd.DataFrame) -> dict[str, Any]:
    """Summarize family-grouped AP deltas between feature sets."""
    if results.empty:
        return {}
    grouped = results[
        results["protocol"].astype(str).str.startswith(PRIMARY_PROTOCOL_PREFIX)
        & (results["model"] == PRIMARY_MODEL)
    ]
    if grouped.empty:
        return {}
    ap_by_feature_set = {
        row["feature_set"]: json_safe_value(row["average_precision"])
        for _, row in grouped.iterrows()
    }

    def delta(feature_set: str, baseline: str = SIZE_ONLY_FEATURE_SET) -> float | None:
        left = ap_by_feature_set.get(feature_set)
        right = ap_by_feature_set.get(baseline)
        if left is None or right is None:
            return None
        return json_safe_value(float(left) - float(right))

    return {
        "protocol": json_safe_value(grouped.iloc[0]["protocol"]),
        "average_precision_by_feature_set": ap_by_feature_set,
        "full16_minus_size_only_average_precision": delta(LEGACY_FULL_FEATURE_SET),
        "full16_plus_b2_minus_size_only_average_precision": delta(PRIMARY_FEATURE_SET),
    }


def random_vs_grouped_leakage(results: pd.DataFrame) -> list[dict[str, Any]]:
    """Return random split AP overstatement for matching feature/model rows."""
    if results.empty:
        return []
    grouped = results[
        results["protocol"].astype(str).str.startswith(PRIMARY_PROTOCOL_PREFIX)
        & (results["model"] == PRIMARY_MODEL)
    ]
    random = results[
        results["protocol"].astype(str).str.startswith("random_")
        & (results["model"] == PRIMARY_MODEL)
    ]
    if grouped.empty or random.empty:
        return []
    merged = grouped.merge(
        random,
        on=["solver_short_name", "solver_uuid", "model", "feature_set"],
        suffixes=("_grouped", "_random"),
    )
    rows = []
    for _, row in merged.iterrows():
        grouped_ap = row["average_precision_grouped"]
        random_ap = row["average_precision_random"]
        delta = None
        if pd.notna(grouped_ap) and pd.notna(random_ap):
            delta = float(random_ap) - float(grouped_ap)
        rows.append(
            {
                "feature_set": json_safe_value(row["feature_set"]),
                "grouped_protocol": json_safe_value(row["protocol_grouped"]),
                "random_protocol": json_safe_value(row["protocol_random"]),
                "average_precision_grouped": json_safe_value(grouped_ap),
                "average_precision_random": json_safe_value(random_ap),
                "average_precision_random_minus_grouped": json_safe_value(delta),
            }
        )
    return rows


def summarize_calibration(calibration: pd.DataFrame) -> list[dict[str, Any]]:
    """Keep compact calibration rows for the primary model only."""
    if calibration.empty:
        return []
    primary = calibration[
        calibration["protocol"].astype(str).str.startswith(PRIMARY_PROTOCOL_PREFIX)
        & (calibration["model"] == PRIMARY_MODEL)
        & (calibration["feature_set"].isin([PRIMARY_FEATURE_SET, LEGACY_FULL_FEATURE_SET]))
    ]
    return dataframe_records(primary)


def _boolean_series(series: pd.Series) -> pd.Series:
    """Coerce bool-like pandas values used in CSV-backed prediction artifacts."""
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    mapped = (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
    )
    if mapped.isna().any():
        bad_values = sorted(series[mapped.isna()].astype(str).unique())
        raise ValueError(f"Cannot coerce prediction values to bool: {bad_values}")
    return mapped.astype(bool)


def _safe_ratio(numerator: float, denominator: float) -> float:
    return math.nan if denominator == 0 else float(numerator) / float(denominator)


def prediction_group_breakdown(
        predictions: pd.DataFrame,
        group_columns: tuple[str, ...] = ("category", "family"),
        protocol_prefix: str = PRIMARY_PROTOCOL_PREFIX,
        model: str = PRIMARY_MODEL,
        feature_set: str = PRIMARY_FEATURE_SET,
        threshold: float = 0.5,
    ) -> pd.DataFrame:
    """Summarize out-of-fold prediction quality by category and family.

    The output is intentionally group-local: rank metrics such as AUROC/AP are
    omitted because many held-out families are small or single-class. Precision,
    recall, F1, Brier, and calibration-style observed/predicted rates remain
    well-defined for the paper's per-family and per-category audit tables.
    """
    required = {
        "solver_short_name",
        "solver_uuid",
        "protocol",
        "model",
        "feature_set",
        "label",
        "oof_probability",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"predictions missing columns: {sorted(missing)}")

    filtered = predictions[
        predictions["protocol"].astype(str).str.startswith(protocol_prefix)
        & (predictions["model"] == model)
        & (predictions["feature_set"] == feature_set)
    ].copy()
    if filtered.empty:
        return pd.DataFrame()

    filtered["label"] = _boolean_series(filtered["label"])
    filtered["oof_probability"] = pd.to_numeric(filtered["oof_probability"], errors="coerce")
    filtered = filtered[filtered["oof_probability"].notna()].copy()
    filtered["threshold_prediction"] = filtered["oof_probability"] >= threshold

    rows: list[dict[str, Any]] = []
    for group_column in group_columns:
        if group_column not in filtered:
            continue
        by_columns = ["solver_short_name", "solver_uuid", group_column]
        for group_key, group in filtered.groupby(by_columns, dropna=False, sort=True):
            solver_short_name, solver_uuid, group_value = group_key
            y_true = group["label"].to_numpy(dtype=bool)
            y_pred = group["threshold_prediction"].to_numpy(dtype=bool)
            y_score = group["oof_probability"].to_numpy(dtype=float)
            tp = int(np.sum(y_true & y_pred))
            fp = int(np.sum(~y_true & y_pred))
            tn = int(np.sum(~y_true & ~y_pred))
            fn = int(np.sum(y_true & ~y_pred))
            precision = _safe_ratio(tp, tp + fp)
            recall = _safe_ratio(tp, tp + fn)
            if tp == 0:
                f1 = 0.0 if fp + fn > 0 else math.nan
            else:
                f1 = 2.0 * precision * recall / (precision + recall)
            rows.append(
                {
                    "solver_short_name": solver_short_name,
                    "solver_uuid": solver_uuid,
                    "protocol": str(group["protocol"].iloc[0]),
                    "model": model,
                    "feature_set": feature_set,
                    "group_type": group_column,
                    "group": str(group_value),
                    "n_tasks": int(len(group)),
                    "positive_labels": int(np.sum(y_true)),
                    "negative_labels": int(len(group) - np.sum(y_true)),
                    "predicted_positive": int(np.sum(y_pred)),
                    "true_positive": tp,
                    "false_positive": fp,
                    "true_negative": tn,
                    "false_negative": fn,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "accuracy": float(np.mean(y_true == y_pred)) if len(group) else math.nan,
                    "brier": float(np.mean((y_score - y_true.astype(float)) ** 2)) if len(group) else math.nan,
                    "observed_positive_rate": float(np.mean(y_true)) if len(group) else math.nan,
                    "predicted_positive_rate": float(np.mean(y_pred)) if len(group) else math.nan,
                    "mean_probability": float(np.mean(y_score)) if len(group) else math.nan,
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["solver_short_name", "solver_uuid", "group_type", "group"]
    ).reset_index(drop=True)


def outcome_counts(labels: pd.DataFrame) -> dict[str, int]:
    """Return B1 two-channel outcome counts when available."""
    if "outcome" in labels:
        return {
            str(key): int(value)
            for key, value in labels["outcome"].value_counts(dropna=False).items()
        }
    return {}


def build_ml_v2_report_summary(
        results: pd.DataFrame,
        calibration: pd.DataFrame,
        labels: pd.DataFrame,
    ) -> dict[str, Any]:
    """Build the compact ``ml_metrics.ml_v2`` payload for one solver."""
    return {
        "ml_metrics_calculator_version": 2,
        "evaluation_protocol": "out_of_fold_cross_validation",
        "primary_model": PRIMARY_MODEL,
        "primary_result": primary_family_grouped_row(results),
        "results": dataframe_records(results),
        "family_grouped_feature_comparison": family_grouped_feature_comparison(results),
        "random_vs_grouped_leakage": random_vs_grouped_leakage(results),
        "calibration": summarize_calibration(calibration),
        "two_channel_outcome_counts": outcome_counts(labels),
    }
