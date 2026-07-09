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

"""PySCF solution-file diagnostic feature extraction.

The B2b feature pass consumes existing PySCF solution JSON files.  Current
archive files reliably contain energies and runtimes; more detailed PySCF
solution diagnostics are parsed opportunistically when future JSONs include
them in ``solution_details``.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


HOMO_LUMO_GAP = "pyscf_homo_lumo_gap"
UHF_S2 = "pyscf_uhf_s2"
MP2_CORR_ENERGY = "mp2_corr_energy"
MP2_CORR_ENERGY_PER_ELECTRON = "mp2_corr_energy_per_electron"
CCSD_T1_DIAGNOSTIC = "ccsd_t1_diagnostic"
CCSD_D1_DIAGNOSTIC = "ccsd_d1_diagnostic"
CCSD_MAX_T2 = "ccsd_max_t2"
PYSCF_DIAGNOSTICS_VERSION_COLUMN = "pyscf_diagnostics_version"
PYSCF_DIAGNOSTICS_VERSION = "b2b_pyscf_diagnostics_v1"

PYSCF_DIAGNOSTIC_FEATURE_COLUMNS = [
    HOMO_LUMO_GAP,
    UHF_S2,
    MP2_CORR_ENERGY,
    MP2_CORR_ENERGY_PER_ELECTRON,
    CCSD_T1_DIAGNOSTIC,
    CCSD_D1_DIAGNOSTIC,
    CCSD_MAX_T2,
]

PYSCF_DIAGNOSTIC_REASON_COLUMNS = [
    f"{feature}_reason" for feature in PYSCF_DIAGNOSTIC_FEATURE_COLUMNS
]

PYSCF_DIAGNOSTIC_COLUMNS = (
    PYSCF_DIAGNOSTIC_FEATURE_COLUMNS
    + PYSCF_DIAGNOSTIC_REASON_COLUMNS
    + [PYSCF_DIAGNOSTICS_VERSION_COLUMN]
)

PYSCF_DIAGNOSTIC_METADATA = {
    HOMO_LUMO_GAP: {
        "scaling_tag": "intensive",
        "cost_class": "pyscf_solution_postprocess",
        "description": "HOMO-LUMO gap parsed from PySCF HF solution details when present.",
    },
    UHF_S2: {
        "scaling_tag": "diagnostic",
        "cost_class": "pyscf_solution_postprocess",
        "description": "UHF spin expectation value <S^2> parsed from solution details when present.",
    },
    MP2_CORR_ENERGY: {
        "scaling_tag": "extensive",
        "cost_class": "pyscf_solution_postprocess",
        "description": "MP2 total correlation energy E(MP2) - E(HF) from PySCF solutions.",
    },
    MP2_CORR_ENERGY_PER_ELECTRON: {
        "scaling_tag": "intensive",
        "cost_class": "pyscf_solution_postprocess",
        "description": "MP2 correlation energy per electron from PySCF solutions.",
    },
    CCSD_T1_DIAGNOSTIC: {
        "scaling_tag": "diagnostic",
        "cost_class": "pyscf_solution_postprocess",
        "description": "CCSD T1 diagnostic parsed from PySCF solution details when present.",
    },
    CCSD_D1_DIAGNOSTIC: {
        "scaling_tag": "diagnostic",
        "cost_class": "pyscf_solution_postprocess",
        "description": "CCSD D1 diagnostic parsed from PySCF solution details when present.",
    },
    CCSD_MAX_T2: {
        "scaling_tag": "diagnostic",
        "cost_class": "pyscf_solution_postprocess",
        "description": "Maximum absolute CCSD T2 amplitude parsed from solution details when present.",
    },
}

METHOD_SLUGS = {
    "hf": "hf",
    "rhf": "hf",
    "uhf": "hf",
    "rohf": "hf",
    "mp2": "mp2",
    "cisd": "cisd",
    "ccsd": "ccsd",
    "ccsdt": "ccsd_t",
    "ccsd_t": "ccsd_t",
}

DETAIL_ALIASES = {
    HOMO_LUMO_GAP: {
        "homo_lumo_gap",
        "homolumogap",
        "homo-lumo gap",
        "homo_lumo_gap_hartree",
        "hf_homo_lumo_gap",
        "mo_gap",
        "orbital_gap",
    },
    UHF_S2: {
        "s2",
        "S2",
        "<S^2>",
        "spin_square",
        "spin_squared",
        "uhf_s2",
        "spin_square_expectation",
    },
    CCSD_T1_DIAGNOSTIC: {
        "t1",
        "T1",
        "t1_diagnostic",
        "ccsd_t1_diagnostic",
    },
    CCSD_D1_DIAGNOSTIC: {
        "d1",
        "D1",
        "d1_diagnostic",
        "ccsd_d1_diagnostic",
    },
    CCSD_MAX_T2: {
        "max_t2",
        "max_t2_amplitude",
        "max_abs_t2",
        "max_abs_t2_amplitude",
        "ccsd_max_t2",
    },
}

PARSED_DETAIL_COLUMNS = {
    HOMO_LUMO_GAP: "parsed_homo_lumo_gap",
    UHF_S2: "parsed_uhf_s2",
    CCSD_T1_DIAGNOSTIC: "parsed_ccsd_t1_diagnostic",
    CCSD_D1_DIAGNOSTIC: "parsed_ccsd_d1_diagnostic",
    CCSD_MAX_T2: "parsed_ccsd_max_t2",
}

_KEY_NORMALIZER = re.compile(r"[^a-z0-9]+")


def pyscf_diagnostic_metadata_dataframe() -> pd.DataFrame:
    """Return metadata tags for the B2b PySCF diagnostic feature columns."""
    return pd.DataFrame(
        [
            {"feature": feature, **metadata}
            for feature, metadata in PYSCF_DIAGNOSTIC_METADATA.items()
        ]
    )


def normalize_method_name(method_name: Any) -> str | None:
    """Return a stable method slug such as ``hf`` or ``ccsd_t``."""
    if method_name is None:
        return None
    normalized = str(method_name).strip().lower()
    normalized = normalized.replace("(t)", "t")
    normalized = _KEY_NORMALIZER.sub("_", normalized).strip("_")
    normalized_compact = normalized.replace("_", "")
    return METHOD_SLUGS.get(normalized) or METHOD_SLUGS.get(normalized_compact)


def coerce_float(value: Any) -> float | None:
    """Return a finite float when ``value`` is scalar numeric, else ``None``."""
    if value is None:
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        result = float(value)
        return result if math.isfinite(result) else None
    if isinstance(value, str):
        try:
            result = float(value.strip())
        except ValueError:
            return None
        return result if math.isfinite(result) else None
    return None


def _normalize_detail_key(key: Any) -> str:
    return _KEY_NORMALIZER.sub("", str(key).lower())


def _normalized_aliases(aliases: Iterable[str]) -> set[str]:
    return {_normalize_detail_key(alias) for alias in aliases}


def find_numeric_detail(solution_details: Any, aliases: Iterable[str]) -> float | None:
    """Find the first finite numeric value whose key matches one alias.

    The scan is recursive and tolerant of dictionaries such as
    ``{"t1_diagnostic": {"value": 0.03}}``.  Numeric values under unrelated
    keys are intentionally ignored.
    """
    target_aliases = _normalized_aliases(aliases)

    def first_scalar(value: Any) -> float | None:
        scalar = coerce_float(value)
        if scalar is not None:
            return scalar
        if isinstance(value, dict):
            for child in value.values():
                scalar = first_scalar(child)
                if scalar is not None:
                    return scalar
        elif isinstance(value, (list, tuple)):
            for child in value:
                scalar = first_scalar(child)
                if scalar is not None:
                    return scalar
        return None

    def search(value: Any) -> float | None:
        if isinstance(value, dict):
            for key, child in value.items():
                if _normalize_detail_key(key) in target_aliases:
                    matched = first_scalar(child)
                    if matched is not None:
                        return matched
            for child in value.values():
                matched = search(child)
                if matched is not None:
                    return matched
        elif isinstance(value, (list, tuple)):
            for child in value:
                matched = search(child)
                if matched is not None:
                    return matched
        return None

    return search(solution_details)


def _seconds_from_duration(value: Any) -> float | None:
    scalar = coerce_float(value)
    if scalar is not None:
        return scalar
    if not isinstance(value, dict):
        return None
    for key_path in (("overall_time", "seconds"), ("seconds",)):
        current = value
        for key in key_path:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]
        scalar = coerce_float(current)
        if scalar is not None:
            return scalar
    return None


def load_pyscf_solution_file(path: str | Path) -> list[dict[str, Any]]:
    """Load one PySCF solution JSON file into flat per-task rows."""
    path = Path(path)
    with path.open("r") as file:
        solution = json.load(file)

    solver_details = solution.get("solver_details", {}) or {}
    solver_short_name = (
        solver_details.get("solver_short_name")
        or solver_details.get("solver_name")
        or solver_details.get("method")
    )
    method_slug = normalize_method_name(solver_short_name)

    rows = []
    for solution_data in solution.get("solution_data", []) or []:
        details = solution_data.get("solution_details") or {}
        row = {
            "source_file": path.name,
            "problem_instance_uuid": solution.get("problem_instance_uuid"),
            "solution_uuid": solution.get("solution_uuid"),
            "solver_short_name": solver_short_name,
            "method_slug": method_slug,
            "task_uuid": solution_data.get("task_uuid"),
            "energy": coerce_float(solution_data.get("energy")),
            "energy_units": solution_data.get("energy_units"),
            "run_time_seconds": _seconds_from_duration(solution_data.get("run_time")),
            "run_time_cpu_seconds": _seconds_from_duration(solution_data.get("run_time_cpu")),
            "solution_details_present": bool(details),
        }
        for feature, parsed_column in PARSED_DETAIL_COLUMNS.items():
            row[parsed_column] = find_numeric_detail(details, DETAIL_ALIASES[feature])
        rows.append(row)
    return rows


def load_pyscf_solution_directory(solution_dir: str | Path) -> pd.DataFrame:
    """Load all top-level PySCF solution JSON files into a flat dataframe."""
    solution_dir = Path(solution_dir)
    rows = []
    for path in sorted(solution_dir.glob("*.json")):
        rows.extend(load_pyscf_solution_file(path))
    return pd.DataFrame(rows)


def _first_numeric(
        solution_rows: pd.DataFrame,
        task_uuid: Any,
        method_slug: str,
        column: str
    ) -> float | None:
    if solution_rows.empty:
        return None
    subset = solution_rows[
        (solution_rows["task_uuid"] == task_uuid)
        & (solution_rows["method_slug"] == method_slug)
    ]
    if subset.empty or column not in subset:
        return None
    for value in subset[column]:
        scalar = coerce_float(value)
        if scalar is not None:
            return scalar
    return None


def _has_method_solution(
        solution_rows: pd.DataFrame,
        task_uuid: Any,
        method_slug: str
    ) -> bool:
    if solution_rows.empty:
        return False
    subset = solution_rows[
        (solution_rows["task_uuid"] == task_uuid)
        & (solution_rows["method_slug"] == method_slug)
    ]
    return not subset.empty


def _add_value_with_reason(
        result: dict[str, Any],
        feature: str,
        value: float | None,
        reason: str
    ) -> None:
    result[feature] = np.nan if value is None else value
    result[f"{feature}_reason"] = reason


def compute_pyscf_diagnostic_columns(
        row: dict[str, Any] | pd.Series,
        solution_rows: pd.DataFrame
    ) -> dict[str, Any]:
    """Compute B2b PySCF diagnostic columns for one Hamiltonian-feature row."""
    task_uuid = row.get("task_uuid")
    result: dict[str, Any] = {}

    hf_energy = _first_numeric(solution_rows, task_uuid, "hf", "energy")
    mp2_energy = _first_numeric(solution_rows, task_uuid, "mp2", "energy")
    try:
        n_elec = float(row.get("n_elec"))
    except (TypeError, ValueError):
        n_elec = np.nan

    if hf_energy is None and mp2_energy is None:
        _add_value_with_reason(result, MP2_CORR_ENERGY, None, "missing_hf_and_mp2_solution")
        _add_value_with_reason(result, MP2_CORR_ENERGY_PER_ELECTRON, None, "missing_hf_and_mp2_solution")
    elif hf_energy is None:
        _add_value_with_reason(result, MP2_CORR_ENERGY, None, "missing_hf_solution")
        _add_value_with_reason(result, MP2_CORR_ENERGY_PER_ELECTRON, None, "missing_hf_solution")
    elif mp2_energy is None:
        _add_value_with_reason(result, MP2_CORR_ENERGY, None, "missing_mp2_solution")
        _add_value_with_reason(result, MP2_CORR_ENERGY_PER_ELECTRON, None, "missing_mp2_solution")
    else:
        corr_energy = mp2_energy - hf_energy
        _add_value_with_reason(result, MP2_CORR_ENERGY, corr_energy, "ok")
        if np.isfinite(n_elec) and n_elec > 0.0:
            _add_value_with_reason(
                result,
                MP2_CORR_ENERGY_PER_ELECTRON,
                corr_energy / n_elec,
                "ok",
            )
        else:
            _add_value_with_reason(result, MP2_CORR_ENERGY_PER_ELECTRON, None, "missing_n_elec")

    hf_feature_map = {
        HOMO_LUMO_GAP: PARSED_DETAIL_COLUMNS[HOMO_LUMO_GAP],
        UHF_S2: PARSED_DETAIL_COLUMNS[UHF_S2],
    }
    for feature, parsed_column in hf_feature_map.items():
        if not _has_method_solution(solution_rows, task_uuid, "hf"):
            _add_value_with_reason(result, feature, None, "missing_hf_solution")
            continue
        value = _first_numeric(solution_rows, task_uuid, "hf", parsed_column)
        reason = "ok" if value is not None else "not_present_in_solution_json"
        _add_value_with_reason(result, feature, value, reason)

    ccsd_feature_map = {
        CCSD_T1_DIAGNOSTIC: PARSED_DETAIL_COLUMNS[CCSD_T1_DIAGNOSTIC],
        CCSD_D1_DIAGNOSTIC: PARSED_DETAIL_COLUMNS[CCSD_D1_DIAGNOSTIC],
        CCSD_MAX_T2: PARSED_DETAIL_COLUMNS[CCSD_MAX_T2],
    }
    for feature, parsed_column in ccsd_feature_map.items():
        if not _has_method_solution(solution_rows, task_uuid, "ccsd"):
            _add_value_with_reason(result, feature, None, "missing_ccsd_solution")
            continue
        value = _first_numeric(solution_rows, task_uuid, "ccsd", parsed_column)
        reason = "ok" if value is not None else "not_present_in_solution_json"
        _add_value_with_reason(result, feature, value, reason)

    result[PYSCF_DIAGNOSTICS_VERSION_COLUMN] = PYSCF_DIAGNOSTICS_VERSION
    return result


def enrich_hamiltonian_features_with_pyscf_diagnostics(
        df: pd.DataFrame,
        solution_dir: str | Path | None = None,
        solution_rows: pd.DataFrame | None = None
    ) -> pd.DataFrame:
    """Return a copy of ``df`` with B2b PySCF diagnostic columns."""
    if solution_rows is None:
        if solution_dir is None:
            raise ValueError("Either solution_dir or solution_rows must be provided.")
        solution_rows = load_pyscf_solution_directory(solution_dir)
    enriched = df.copy()
    feature_rows = [
        compute_pyscf_diagnostic_columns(row, solution_rows)
        for _, row in enriched.iterrows()
    ]
    feature_df = pd.DataFrame(feature_rows, index=enriched.index)
    for column in PYSCF_DIAGNOSTIC_COLUMNS:
        enriched[column] = feature_df[column]
    return enriched


def build_pyscf_feature_category_coverage(
        enriched_features: pd.DataFrame,
        category_column: str = "category"
    ) -> pd.DataFrame:
    """Return a long feature-by-category coverage dataframe."""
    if category_column not in enriched_features:
        categories = pd.Series(["unknown"] * len(enriched_features), index=enriched_features.index)
    else:
        categories = enriched_features[category_column].fillna("unknown")

    rows = []
    for feature in PYSCF_DIAGNOSTIC_FEATURE_COLUMNS:
        reason_column = f"{feature}_reason"
        for category, idx in categories.groupby(categories).groups.items():
            subset = enriched_features.loc[idx]
            total = int(len(subset))
            present = int(subset[feature].notna().sum())
            reasons = {}
            if reason_column in subset:
                reasons = subset[reason_column].value_counts(dropna=False).to_dict()
            rows.append(
                {
                    "feature": feature,
                    "category": category,
                    "total_tasks": total,
                    "present_tasks": present,
                    "missing_tasks": total - present,
                    "coverage_fraction": present / total if total else np.nan,
                    "reason_counts": json.dumps(reasons, sort_keys=True),
                }
            )
    return pd.DataFrame(rows)
