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

"""Double-factorization feature post-processing.

The original Hamiltonian feature pipeline stores the raw double-factorization
eigenvalue spectrum and size-extensive quantities.  These helpers derive the
B2a intensive features without re-reading FCIDUMPs.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DF_DECAY_EXPONENT = "df_eig_decay_exponent"
DF_DECAY_R2 = "df_eig_decay_r2"
DF_DECAY_NPOINTS = "df_eig_decay_npoints"
DF_DECAY_REASON = "df_eig_decay_fit_reason"
ONE_NORM_PER_ORBITAL = "one_norm_per_orbital"
DF_RANK_PER_ORBITAL = "df_rank_per_orbital"
FEATURES_VERSION = "features_version"
DF_FEATURES_VERSION = "b2a_df_features_v1"

FLOAT_PATTERN = re.compile(
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
)


DF_FEATURE_COLUMNS = [
    DF_DECAY_EXPONENT,
    DF_DECAY_R2,
    DF_DECAY_NPOINTS,
    DF_DECAY_REASON,
    ONE_NORM_PER_ORBITAL,
    DF_RANK_PER_ORBITAL,
]


DF_FEATURE_METADATA = {
    DF_DECAY_EXPONENT: {
        "scaling_tag": "intensive",
        "cost_class": "df_spectrum_postprocess",
        "description": "Power-law exponent alpha from lambda_l ~ l^-alpha tail fit.",
    },
    DF_DECAY_R2: {
        "scaling_tag": "diagnostic",
        "cost_class": "df_spectrum_postprocess",
        "description": "R^2 goodness of fit for the DF eigenvalue decay exponent.",
    },
    DF_DECAY_NPOINTS: {
        "scaling_tag": "diagnostic",
        "cost_class": "df_spectrum_postprocess",
        "description": "Number of tail eigenvalues used in the decay fit.",
    },
    DF_DECAY_REASON: {
        "scaling_tag": "diagnostic",
        "cost_class": "df_spectrum_postprocess",
        "description": "Status string for the DF eigenvalue decay fit.",
    },
    ONE_NORM_PER_ORBITAL: {
        "scaling_tag": "intensive",
        "cost_class": "csv_postprocess",
        "description": "Existing one_norm divided by n_orbs.",
    },
    DF_RANK_PER_ORBITAL: {
        "scaling_tag": "intensive",
        "cost_class": "csv_postprocess",
        "description": "Existing df_rank divided by n_orbs.",
    },
}


def df_feature_metadata_dataframe() -> pd.DataFrame:
    """Return metadata tags for the B2a DF-derived feature columns."""
    return pd.DataFrame(
        [
            {"feature": feature, **metadata}
            for feature, metadata in DF_FEATURE_METADATA.items()
        ]
    )


def parse_df_eigs(value: Any) -> np.ndarray:
    """Return a finite positive eigenvalue array from a CSV string or array."""
    if value is None:
        return np.array([], dtype=float)
    if isinstance(value, float) and math.isnan(value):
        return np.array([], dtype=float)
    if isinstance(value, np.ndarray):
        eigs = value.astype(float, copy=False)
    elif isinstance(value, (list, tuple)):
        eigs = np.asarray(value, dtype=float)
    else:
        text = str(value).strip()
        if not text:
            return np.array([], dtype=float)
        tokens = FLOAT_PATTERN.findall(text)
        if not tokens:
            return np.array([], dtype=float)
        eigs = np.asarray(tokens, dtype=float)
    return eigs[np.isfinite(eigs) & (eigs > 0.0)]


def load_cached_df_eigs(
        cache_dir: str | Path,
        instance_data_object_uuid: str
    ) -> np.ndarray:
    """Load cached DF eigenvalues for an instance-data UUID if present."""
    cache_dir = Path(cache_dir)
    candidates = [
        cache_dir / f"df_eigs.{instance_data_object_uuid}.bin",
        cache_dir / f"double_factorized_eigs.{instance_data_object_uuid}.bin",
    ]
    for path in candidates:
        if path.exists():
            return parse_df_eigs(np.fromfile(path, dtype=np.float64))
    return np.array([], dtype=float)


def fit_df_eig_decay(
        eigs: Any,
        tail_fraction: float = 0.5,
        min_points: int = 8
    ) -> dict[str, Any]:
    """Fit a power-law tail lambda_l ~ l^-alpha to DF eigenvalues.

    Eigenvalues are sorted from largest to smallest before fitting.  The fit uses
    the final ``tail_fraction`` of the ranked spectrum, with at least
    ``min_points`` values when available.
    """
    eigs = parse_df_eigs(eigs)
    if len(eigs) < min_points:
        return {
            DF_DECAY_EXPONENT: np.nan,
            DF_DECAY_R2: np.nan,
            DF_DECAY_NPOINTS: len(eigs),
            DF_DECAY_REASON: "too_few_positive_eigs",
        }

    sorted_eigs = np.sort(eigs)[::-1]
    n_tail = max(min_points, int(math.ceil(len(sorted_eigs) * tail_fraction)))
    n_tail = min(n_tail, len(sorted_eigs))
    tail_start = len(sorted_eigs) - n_tail
    ranks = np.arange(1, len(sorted_eigs) + 1, dtype=float)[tail_start:]
    values = sorted_eigs[tail_start:]

    log_ranks = np.log(ranks)
    log_values = np.log(values)
    slope, intercept = np.polyfit(log_ranks, log_values, deg=1)
    predicted = slope * log_ranks + intercept
    ss_res = float(np.sum((log_values - predicted) ** 2))
    ss_tot = float(np.sum((log_values - np.mean(log_values)) ** 2))
    r2 = np.nan if ss_tot == 0.0 else 1.0 - ss_res / ss_tot

    return {
        DF_DECAY_EXPONENT: float(-slope),
        DF_DECAY_R2: float(r2),
        DF_DECAY_NPOINTS: int(n_tail),
        DF_DECAY_REASON: "ok",
    }


def normalized_df_features(row: dict[str, Any] | pd.Series) -> dict[str, Any]:
    """Compute B2a normalized DF and one-norm features for one row."""
    n_orbs = row.get("n_orbs")
    try:
        n_orbs = float(n_orbs)
    except (TypeError, ValueError):
        n_orbs = np.nan

    try:
        one_norm = float(row.get("one_norm", np.nan))
    except (TypeError, ValueError):
        one_norm = np.nan
    try:
        df_rank = float(row.get("df_rank", np.nan))
    except (TypeError, ValueError):
        df_rank = np.nan

    if not np.isfinite(n_orbs) or n_orbs <= 0.0:
        one_norm_per_orbital = np.nan
        df_rank_per_orbital = np.nan
    else:
        one_norm_per_orbital = one_norm / n_orbs
        df_rank_per_orbital = df_rank / n_orbs

    return {
        ONE_NORM_PER_ORBITAL: one_norm_per_orbital,
        DF_RANK_PER_ORBITAL: df_rank_per_orbital,
    }


def compute_df_feature_columns(
        row: dict[str, Any] | pd.Series,
        df_eigs: Any | None = None
    ) -> dict[str, Any]:
    """Compute all B2a DF-derived feature columns for one row or feature dict."""
    features = {}
    if df_eigs is None:
        df_eigs = row.get("df_eigs")
    features.update(fit_df_eig_decay(df_eigs))
    features.update(normalized_df_features(row))
    return features


def add_df_feature_columns_to_record(record: dict[str, Any]) -> dict[str, Any]:
    """Mutate and return one feature record with B2a DF-derived columns."""
    record.update(compute_df_feature_columns(record))
    record[FEATURES_VERSION] = DF_FEATURES_VERSION
    return record


def enrich_hamiltonian_features_dataframe(
        df: pd.DataFrame,
        df_eigs_cache_dir: str | Path | None = None
    ) -> pd.DataFrame:
    """Return a copy of ``df`` with B2a DF-derived feature columns."""
    enriched = df.copy()
    cache_dir = Path(df_eigs_cache_dir) if df_eigs_cache_dir is not None else None
    feature_rows = []
    for _, row in enriched.iterrows():
        cached_eigs = None
        if cache_dir is not None and "instance_data_object_uuid" in row:
            cached_eigs = load_cached_df_eigs(
                cache_dir=cache_dir,
                instance_data_object_uuid=row["instance_data_object_uuid"]
            )
            if len(cached_eigs) == 0:
                cached_eigs = None
        feature_rows.append(compute_df_feature_columns(row, df_eigs=cached_eigs))
    feature_df = pd.DataFrame(feature_rows, index=enriched.index)
    for column in DF_FEATURE_COLUMNS:
        enriched[column] = feature_df[column]
    enriched[FEATURES_VERSION] = DF_FEATURES_VERSION
    return enriched
