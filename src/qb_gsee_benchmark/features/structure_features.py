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

"""Derived structural proxy features for QB-GSEE Hamiltonian rows.

These helpers operate on the existing Hamiltonian feature CSV.  They do not
re-read FCIDUMPs or localize orbitals; the resulting columns are intentionally
named as Pauli/hypergraph structural proxies rather than raw integral sparsity
or localized-exchange bandwidth measurements.
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
import pandas as pd


PAULI_TERMS_PER_ORBITAL_QUARTIC = "pauli_terms_per_orbital_quartic"
ONE_NORM_PER_PAULI_TERM = "one_norm_per_pauli_term"
MEAN_VERTEX_DEGREE_PER_ORBITAL = "mean_vertex_degree_per_orbital"
MAX_VERTEX_DEGREE_PER_ORBITAL = "max_vertex_degree_per_orbital"
VERTEX_DEGREE_COEFFICIENT_OF_VARIATION = "vertex_degree_coefficient_of_variation"
EDGE_ORDER_COEFFICIENT_OF_VARIATION = "edge_order_coefficient_of_variation"
STRUCTURE_PROXY_VERSION_COLUMN = "structure_proxy_features_version"
STRUCTURE_PROXY_VERSION = "b2c_structure_proxy_features_v1"

STRUCTURE_PROXY_FEATURE_COLUMNS = [
    PAULI_TERMS_PER_ORBITAL_QUARTIC,
    ONE_NORM_PER_PAULI_TERM,
    MEAN_VERTEX_DEGREE_PER_ORBITAL,
    MAX_VERTEX_DEGREE_PER_ORBITAL,
    VERTEX_DEGREE_COEFFICIENT_OF_VARIATION,
    EDGE_ORDER_COEFFICIENT_OF_VARIATION,
]

STRUCTURE_PROXY_COLUMNS = STRUCTURE_PROXY_FEATURE_COLUMNS + [
    STRUCTURE_PROXY_VERSION_COLUMN,
]

STRUCTURE_PROXY_METADATA = {
    PAULI_TERMS_PER_ORBITAL_QUARTIC: {
        "scaling_tag": "intensive",
        "cost_class": "csv_postprocess",
        "representation": "qubit_pauli_proxy",
        "description": "Number of Pauli terms divided by n_orbs^4; a current-CSV sparsity proxy, not a thresholded FCIDUMP integral count.",
    },
    ONE_NORM_PER_PAULI_TERM: {
        "scaling_tag": "intensive",
        "cost_class": "csv_postprocess",
        "representation": "qubit_pauli_proxy",
        "description": "Existing one_norm divided by number_of_terms to separate average term scale from Hamiltonian size.",
    },
    MEAN_VERTEX_DEGREE_PER_ORBITAL: {
        "scaling_tag": "intensive",
        "cost_class": "csv_postprocess",
        "representation": "interaction_hypergraph_proxy",
        "description": "Mean interaction-hypergraph vertex degree divided by n_orbs.",
    },
    MAX_VERTEX_DEGREE_PER_ORBITAL: {
        "scaling_tag": "intensive",
        "cost_class": "csv_postprocess",
        "representation": "interaction_hypergraph_proxy",
        "description": "Maximum interaction-hypergraph vertex degree divided by n_orbs.",
    },
    VERTEX_DEGREE_COEFFICIENT_OF_VARIATION: {
        "scaling_tag": "intensive",
        "cost_class": "csv_postprocess",
        "representation": "interaction_hypergraph_proxy",
        "description": "std_dev_vertex_degree divided by mean_vertex_degree; a degree-heterogeneity proxy for nonuniform interaction structure.",
    },
    EDGE_ORDER_COEFFICIENT_OF_VARIATION: {
        "scaling_tag": "intensive",
        "cost_class": "csv_postprocess",
        "representation": "interaction_hypergraph_proxy",
        "description": "std_dev_edge_order divided by mean_edge_order; a proxy for edge-order heterogeneity in the current feature table.",
    },
}


def structure_proxy_metadata_dataframe() -> pd.DataFrame:
    """Return metadata tags for the B2c structural proxy feature columns."""
    return pd.DataFrame(
        [
            {"feature": feature, **metadata}
            for feature, metadata in STRUCTURE_PROXY_METADATA.items()
        ]
    )


def _finite_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result if math.isfinite(result) else np.nan


def _safe_divide(numerator: Any, denominator: Any) -> float:
    numerator_value = _finite_float(numerator)
    denominator_value = _finite_float(denominator)
    if not np.isfinite(numerator_value):
        return np.nan
    if not np.isfinite(denominator_value) or denominator_value <= 0.0:
        return np.nan
    return numerator_value / denominator_value


def compute_structure_proxy_columns(row: dict[str, Any] | pd.Series) -> dict[str, Any]:
    """Compute B2c structural proxy columns for one Hamiltonian-feature row."""
    n_orbs = _finite_float(row.get("n_orbs"))
    orbital_quartic = n_orbs ** 4 if np.isfinite(n_orbs) and n_orbs > 0.0 else np.nan
    result = {
        PAULI_TERMS_PER_ORBITAL_QUARTIC: _safe_divide(
            row.get("number_of_terms"),
            orbital_quartic,
        ),
        ONE_NORM_PER_PAULI_TERM: _safe_divide(
            row.get("one_norm"),
            row.get("number_of_terms"),
        ),
        MEAN_VERTEX_DEGREE_PER_ORBITAL: _safe_divide(
            row.get("mean_vertex_degree"),
            n_orbs,
        ),
        MAX_VERTEX_DEGREE_PER_ORBITAL: _safe_divide(
            row.get("max_vertex_degree"),
            n_orbs,
        ),
        VERTEX_DEGREE_COEFFICIENT_OF_VARIATION: _safe_divide(
            row.get("std_dev_vertex_degree"),
            row.get("mean_vertex_degree"),
        ),
        EDGE_ORDER_COEFFICIENT_OF_VARIATION: _safe_divide(
            row.get("std_dev_edge_order"),
            row.get("mean_edge_order"),
        ),
    }
    result[STRUCTURE_PROXY_VERSION_COLUMN] = STRUCTURE_PROXY_VERSION
    return result


def add_structure_proxy_columns_to_record(record: dict[str, Any]) -> dict[str, Any]:
    """Mutate and return one feature record with B2c structural proxy columns."""
    record.update(compute_structure_proxy_columns(record))
    return record


def enrich_hamiltonian_features_with_structure_proxies(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with B2c structural proxy columns."""
    enriched = df.copy()
    feature_rows = [compute_structure_proxy_columns(row) for _, row in enriched.iterrows()]
    feature_df = pd.DataFrame(feature_rows, index=enriched.index)
    for column in STRUCTURE_PROXY_COLUMNS:
        enriched[column] = feature_df[column]
    return enriched


def structure_proxy_coverage(enriched_features: pd.DataFrame) -> pd.DataFrame:
    """Return whole-table coverage and simple distribution summaries."""
    rows = []
    total = int(len(enriched_features))
    for feature in STRUCTURE_PROXY_FEATURE_COLUMNS:
        values = pd.to_numeric(enriched_features[feature], errors="coerce")
        present = int(values.notna().sum())
        rows.append(
            {
                "feature": feature,
                "total_tasks": total,
                "present_tasks": present,
                "missing_tasks": total - present,
                "coverage_fraction": present / total if total else np.nan,
                "min": float(values.min()) if present else np.nan,
                "median": float(values.median()) if present else np.nan,
                "max": float(values.max()) if present else np.nan,
            }
        )
    return pd.DataFrame(rows)


def build_structure_proxy_category_coverage(
        enriched_features: pd.DataFrame,
        category_column: str = "category",
    ) -> pd.DataFrame:
    """Return a long feature-by-category coverage dataframe."""
    if category_column not in enriched_features:
        categories = pd.Series(["unknown"] * len(enriched_features), index=enriched_features.index)
    else:
        categories = enriched_features[category_column].fillna("unknown")

    rows = []
    for feature in STRUCTURE_PROXY_FEATURE_COLUMNS:
        values = pd.to_numeric(enriched_features[feature], errors="coerce")
        for category, idx in categories.groupby(categories).groups.items():
            subset = values.loc[idx]
            total = int(len(subset))
            present = int(subset.notna().sum())
            rows.append(
                {
                    "feature": feature,
                    "category": category,
                    "total_tasks": total,
                    "present_tasks": present,
                    "missing_tasks": total - present,
                    "coverage_fraction": present / total if total else np.nan,
                    "summary": json.dumps(
                        {
                            "min": float(subset.min()) if present else None,
                            "median": float(subset.median()) if present else None,
                            "max": float(subset.max()) if present else None,
                        },
                        sort_keys=True,
                    ),
                }
            )
    return pd.DataFrame(rows)
