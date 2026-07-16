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

"""Data assembly helpers for QB-GSEE ML v2 evaluations."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from qb_gsee_benchmark.benchmark_data import canonical_problem_family


LEGACY_FULL_FEATURES = [
    "max_vertex_degree",
    "min_vertex_degree",
    "mean_vertex_degree",
    "std_dev_vertex_degree",
    "max_weight",
    "min_weight",
    "mean_weight",
    "std_dev_weight",
    "max_edge_order",
    "mean_edge_order",
    "std_dev_edge_order",
    "one_norm",
    "log_fci_dim",
    "n_elec",
    "n_orbs",
    "df_gap",
]

SIZE_ONLY_FEATURES = ["n_elec", "n_orbs"]

B2_DF_FEATURES = [
    "df_eig_decay_exponent",
    "one_norm_per_orbital",
    "df_rank_per_orbital",
]

B2_PYSCF_FEATURES = ["mp2_corr_energy_per_electron"]

B2_STRUCTURE_PROXY_FEATURES = [
    "pauli_terms_per_orbital_quartic",
    "one_norm_per_pauli_term",
    "mean_vertex_degree_per_orbital",
    "max_vertex_degree_per_orbital",
    "vertex_degree_coefficient_of_variation",
    "edge_order_coefficient_of_variation",
]

B2_INTENSIVE_FEATURES = (
    B2_DF_FEATURES
    + B2_PYSCF_FEATURES
    + B2_STRUCTURE_PROXY_FEATURES
)


def ml_v2_feature_sets(df: pd.DataFrame) -> dict[str, list[str]]:
    """Return standard ML v2 feature sets available in ``df``."""
    feature_sets = {
        "full16": [feature for feature in LEGACY_FULL_FEATURES if feature in df],
        "size_only": [feature for feature in SIZE_ONLY_FEATURES if feature in df],
    }
    available_b2 = [feature for feature in B2_INTENSIVE_FEATURES if feature in df]
    if available_b2:
        feature_sets["b2_intensive"] = available_b2
        feature_sets["full16_plus_b2"] = feature_sets["full16"] + available_b2
    return {name: columns for name, columns in feature_sets.items() if columns}


def ml_v2_candidate_features(df: pd.DataFrame) -> list[str]:
    """Return all candidate ML v2 feature columns present in ``df``."""
    candidates = LEGACY_FULL_FEATURES + SIZE_ONLY_FEATURES + B2_INTENSIVE_FEATURES
    return sorted({feature for feature in candidates if feature in df})


def coerce_bool_series(series: pd.Series) -> pd.Series:
    """Coerce common CSV boolean encodings to a boolean Series."""
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
        raise ValueError(f"Cannot coerce values to bool: {bad_values}")
    return mapped.astype(bool)


def ensure_group_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with canonical ``family`` and ``category`` columns."""
    result = df.copy()
    task_columns = {"problem_instance_short_name", "task_uuid"}
    if task_columns.issubset(result):
        canonical = pd.Series(
            [
                canonical_problem_family(short_name, task_uuid=task_uuid)
                for short_name, task_uuid in zip(
                    result["problem_instance_short_name"],
                    result["task_uuid"],
                    strict=True,
                )
            ],
            index=result.index,
        )
        if "family" in result:
            mismatch = result["family"].notna() & result["family"].ne(canonical)
            if mismatch.any():
                raise ValueError("family column conflicts with canonical_families_v1")
        result["family"] = canonical
    elif "family" not in result:
        raise ValueError(
            "family derivation requires problem_instance_short_name and task_uuid"
        )
    if "category" not in result:
        result["category"] = "unknown"
    result["family"] = result["family"].fillna("unknown")
    result["category"] = result["category"].fillna("unknown")
    return result


def assemble_solver_ml_table(
        solver_labels: pd.DataFrame,
        hamiltonian_features: pd.DataFrame,
        feature_columns: Sequence[str],
        label_column: str = "label",
        attempted_only: bool = True,
        solver_uuid: str | None = None,
    ) -> pd.DataFrame:
    """Join solver labels with Hamiltonian features for one ML evaluation.

    The returned table keeps B1 grouping columns and contains only rows with
    available Hamiltonian features.  Boolean label columns are normalized for
    CSV-loaded inputs.
    """
    required_label_columns = {"task_uuid", label_column}
    missing_label_columns = required_label_columns - set(solver_labels.columns)
    if missing_label_columns:
        raise ValueError(f"solver_labels missing columns: {sorted(missing_label_columns)}")

    required_feature_columns = {"task_uuid", *feature_columns}
    missing_feature_columns = required_feature_columns - set(hamiltonian_features.columns)
    if missing_feature_columns:
        raise ValueError(f"hamiltonian_features missing columns: {sorted(missing_feature_columns)}")

    labels = solver_labels.copy()
    duplicate_feature_columns = [column for column in feature_columns if column in labels.columns]
    if duplicate_feature_columns:
        labels = labels.drop(columns=duplicate_feature_columns)
    if solver_uuid is not None:
        if "solver_uuid" not in labels:
            raise ValueError("solver_uuid filter requested but solver_uuid column is absent")
        labels = labels[labels["solver_uuid"] == solver_uuid].copy()
    if "curation_tier" in labels:
        labels = labels[labels["curation_tier"] != "test"].copy()
    if attempted_only and "attempted" in labels:
        labels["attempted"] = coerce_bool_series(labels["attempted"])
        labels = labels[labels["attempted"]].copy()
    labels[label_column] = coerce_bool_series(labels[label_column])
    labels = ensure_group_columns(labels)

    features = hamiltonian_features[["task_uuid", *feature_columns]].drop_duplicates(
        subset=["task_uuid"]
    )
    merged = labels.merge(features, on="task_uuid", how="inner", validate="many_to_one")
    if merged.empty:
        raise ValueError("No rows remain after joining solver labels and Hamiltonian features")
    return merged.reset_index(drop=True)
