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

"""Coverage helpers for quantum resource-estimate solution files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qb_gsee_benchmark.benchmark_data import canonical_problem_family
from qb_gsee_benchmark.benchmark_data import problem_instance_category_by_short_name


QRE_REPRESENTATION_ORDER = ["DF_QPE", "THC_QPE", "THC_BLISS_QPE", "TOPQAD"]


def qre_representation(solver_short_name: str | None, source_dir: str | None = None) -> str:
    """Return a coarse QRE representation label for coverage summaries."""
    text = " ".join(str(value or "") for value in [solver_short_name, source_dir]).lower()
    if "thc_bliss" in text or "thc-bliss" in text:
        return "THC_BLISS_QPE"
    if "thc" in text:
        return "THC_QPE"
    if "topqad" in text:
        return "TOPQAD"
    if "df_qpe" in text or "pre_solution" in text or "double factor" in text:
        return "DF_QPE"
    return "unknown"


def nested_get(mapping: dict[str, Any] | None, path: list[str]) -> Any:
    """Return a nested value from dictionaries, or ``None`` when absent."""
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _source_dir_label(path: Path, solution_root: Path) -> str:
    try:
        rel_parent = path.parent.relative_to(solution_root)
    except ValueError:
        return path.parent.name
    if rel_parent == Path("."):
        return solution_root.name
    return str(Path(solution_root.name) / rel_parent)


def load_qre_solution_file(path: str | Path, solution_root: str | Path | None = None) -> list[dict[str, Any]]:
    """Load one resource-estimate solution JSON into flat per-task rows."""
    path = Path(path)
    solution_root = Path(solution_root) if solution_root is not None else path.parents[1]
    with path.open("r") as file:
        payload = json.load(file)

    solver_details = payload.get("solver_details", {}) or {}
    solver_short_name = solver_details.get("solver_short_name") or solver_details.get("solver_name")
    solver_uuid = solver_details.get("solver_uuid")
    hardware = solver_details.get("quantum_hardware_details", {}) or {}
    hardware_params = hardware.get("quantum_hardware_parameters", {}) or {}
    algorithm_details = solver_details.get("algorithm_details", {}) or {}
    algorithm_params = algorithm_details.get("algorithm_parameters", {}) or {}
    source_dir = _source_dir_label(path, solution_root)
    representation = qre_representation(solver_short_name, source_dir)

    rows = []
    for solution_data in payload.get("solution_data", []) or []:
        quantum_resources = solution_data.get("quantum_resources", {}) or {}
        solution_details = solution_data.get("solution_details", {}) or {}
        row = {
            "source_dir": source_dir,
            "source_file": path.name,
            "representation": representation,
            "solver_short_name": solver_short_name,
            "solver_uuid": solver_uuid,
            "solution_uuid": payload.get("solution_uuid"),
            "problem_instance_uuid": payload.get("problem_instance_uuid"),
            "task_uuid": solution_data.get("task_uuid"),
            "is_resource_estimate": bool(payload.get("is_resource_estimate")),
            "confidence_level": solution_data.get("confidence_level"),
            "error_bound": solution_data.get("error_bound"),
            "hardware_description": hardware.get("quantum_hardware_description"),
            "physical_error_rate": hardware_params.get("physical_error_rate"),
            "cycle_time_microseconds": hardware_params.get("cycle_time_microseconds"),
            "num_factories": hardware_params.get("num_factories"),
            "parallelize_shots": hardware_params.get("parallelize_shots"),
            "algorithm_description": algorithm_details.get("algorithm_description") or algorithm_details.get("description"),
            "sf_threshold": algorithm_params.get("sf_threshold"),
            "df_threshold": algorithm_params.get("df_threshold"),
            "max_orbitals": algorithm_params.get("max_orbitals"),
            "num_logical_qubits": nested_get(quantum_resources, ["logical", "num_logical_qubits"]),
            "num_T_gates_per_shot": nested_get(quantum_resources, ["logical", "num_T_gates_per_shot"]),
            "num_toffoli_gates_per_shot": nested_get(quantum_resources, ["logical", "num_toffoli_gates_per_shot"]),
            "num_shots": nested_get(quantum_resources, ["logical", "num_shots"]),
            "hardware_failure_tolerance_per_shot": nested_get(quantum_resources, ["logical", "hardware_failure_tolerance_per_shot"]),
            "num_physical_qubits": nested_get(quantum_resources, ["physical", "num_physical_qubits"]),
            "data_code_distance": nested_get(quantum_resources, ["physical", "data_code_distance"]),
            "num_logical_compiled_qubits": nested_get(quantum_resources, ["physical", "num_logical_compiled_qubits"]),
            "num_qpus": nested_get(quantum_resources, ["physical", "num_qpus"]),
            "preprocessing_time_seconds": nested_get(solution_data.get("run_time"), ["preprocessing_time", "seconds"]),
            "algorithm_run_time_seconds": nested_get(solution_data.get("run_time"), ["algorithm_run_time", "seconds"]),
            "overall_time_seconds": nested_get(solution_data.get("run_time"), ["overall_time", "seconds"]),
            "overlap": solution_details.get("overlap"),
            "block_encoding_alpha": nested_get(solution_details, ["block_encoding_details", "alpha"]),
            "decomposition_l1_norm_hartree": solution_details.get("decomposition_l1_norm_hartree"),
            "decomposition_error_l2_norm_hartree": solution_details.get("decomposition_error_l2_norm_hartree"),
            "decomposition_ccsd_t_error_millihartree": solution_details.get("decomposition_ccsd_t_error_millihartree"),
            "thc_rank": solution_details.get("thc_rank"),
            "thc_bliss_penalty_parameter": solution_details.get("thc_bliss_penalty_parameter"),
        }
        rows.append(row)
    return rows


def load_qre_solution_roots(solution_roots: list[str | Path]) -> pd.DataFrame:
    """Load all JSON rows under a list of solution roots."""
    rows: list[dict[str, Any]] = []
    for root in solution_roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                rows.extend(load_qre_solution_file(path, solution_root=root))
            except Exception as exc:
                rows.append({"source_dir": str(root), "source_file": path.name, "parse_error": str(exc)})
    return pd.DataFrame(rows)


def add_task_metadata(
        qre_rows: pd.DataFrame,
        hamiltonian_features: pd.DataFrame,
        problem_instances_dir: str | Path | None = None,
    ) -> pd.DataFrame:
    """Join QRE rows to current Hamiltonian feature/task metadata."""
    metadata_columns = [
        "task_uuid",
        "problem_instance_uuid",
        "problem_instance_short_name",
        "n_elec",
        "n_orbs",
        "log_fci_dim",
    ]
    available = [column for column in metadata_columns if column in hamiltonian_features]
    metadata = hamiltonian_features[available].drop_duplicates(subset=["task_uuid"])
    enriched = qre_rows.merge(
        metadata,
        on="task_uuid",
        how="left",
        suffixes=("", "_current"),
    )
    if "problem_instance_uuid_current" in enriched:
        enriched["problem_instance_uuid"] = enriched["problem_instance_uuid_current"].combine_first(
            enriched["problem_instance_uuid"]
        )
        enriched = enriched.drop(columns=["problem_instance_uuid_current"])
    if {"problem_instance_short_name", "task_uuid"}.issubset(enriched):
        enriched["family"] = [
            (
                canonical_problem_family(short_name, task_uuid=task_uuid)
                if pd.notna(short_name)
                else "not_current_task"
            )
            for short_name, task_uuid in zip(
                enriched["problem_instance_short_name"],
                enriched["task_uuid"],
                strict=True,
            )
        ]
    else:
        enriched["family"] = "unknown"
    if problem_instances_dir is not None and "problem_instance_short_name" in enriched:
        categories = problem_instance_category_by_short_name(str(problem_instances_dir))
        enriched["category"] = enriched["problem_instance_short_name"].map(categories).fillna("not_current_task")
    else:
        enriched["category"] = "unknown"
    enriched["in_current_hamiltonian_features"] = enriched["problem_instance_short_name"].notna()
    return enriched


def task_coverage_matrix(current_tasks: pd.DataFrame, qre_rows: pd.DataFrame) -> pd.DataFrame:
    """Return current-task coverage booleans by QRE representation."""
    base_columns = [
        "task_uuid",
        "problem_instance_uuid",
        "problem_instance_short_name",
    ]
    optional = [column for column in ["category", "family", "n_elec", "n_orbs", "log_fci_dim"] if column in current_tasks]
    coverage = current_tasks[base_columns + optional].drop_duplicates(subset=["task_uuid"]).copy()
    for representation in QRE_REPRESENTATION_ORDER:
        covered_tasks = set(qre_rows.loc[qre_rows["representation"] == representation, "task_uuid"].dropna())
        column = f"has_{representation.lower()}"
        coverage[column] = coverage["task_uuid"].isin(covered_tasks)
    coverage["has_any_qre"] = coverage[[column for column in coverage.columns if column.startswith("has_")]].any(axis=1)
    return coverage


def coverage_by_solver(current_tasks: pd.DataFrame, qre_rows: pd.DataFrame) -> pd.DataFrame:
    """Summarize current-task coverage by source/solver/hardware variant."""
    current_task_set = set(current_tasks["task_uuid"])
    rows = []
    group_columns = [
        "representation",
        "source_dir",
        "solver_short_name",
        "solver_uuid",
        "physical_error_rate",
        "cycle_time_microseconds",
        "num_factories",
        "parallelize_shots",
    ]
    if qre_rows.empty:
        return pd.DataFrame(columns=group_columns)
    for key, group in qre_rows.groupby(group_columns, dropna=False):
        covered = set(group["task_uuid"].dropna()) & current_task_set
        rows.append(
            {
                **dict(zip(group_columns, key)),
                "solution_rows": int(len(group)),
                "unique_solution_tasks": int(group["task_uuid"].nunique(dropna=True)),
                "current_tasks_covered": int(len(covered)),
                "current_tasks_total": int(len(current_task_set)),
                "coverage_fraction": len(covered) / len(current_task_set) if current_task_set else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["representation", "source_dir", "solver_short_name"],
        na_position="last",
    )


def coverage_by_category(task_coverage: pd.DataFrame) -> pd.DataFrame:
    """Summarize representation coverage by instance category."""
    rows = []
    representation_columns = [column for column in task_coverage.columns if column.startswith("has_")]
    for category, category_df in task_coverage.groupby("category", dropna=False, sort=True):
        total = len(category_df)
        for column in representation_columns:
            covered = int(category_df[column].sum())
            rows.append(
                {
                    "category": category,
                    "coverage_column": column,
                    "tasks_total": int(total),
                    "tasks_covered": covered,
                    "tasks_missing": int(total - covered),
                    "coverage_fraction": covered / total if total else np.nan,
                }
            )
    return pd.DataFrame(rows)


def missing_thc_instances(task_coverage: pd.DataFrame) -> pd.DataFrame:
    """Return current problem instances that still need THC/THC-BLISS QRE rows."""
    rows = []
    for (problem_uuid, short_name), group in task_coverage.groupby(
        ["problem_instance_uuid", "problem_instance_short_name"],
        dropna=False,
        sort=True,
    ):
        n_tasks = int(len(group))
        has_thc = int(group.get("has_thc_qpe", pd.Series(False, index=group.index)).sum())
        has_thc_bliss = int(group.get("has_thc_bliss_qpe", pd.Series(False, index=group.index)).sum())
        rows.append(
            {
                "problem_instance_uuid": problem_uuid,
                "problem_instance_short_name": short_name,
                "category": group["category"].iloc[0] if "category" in group else "unknown",
                "n_current_tasks": n_tasks,
                "thc_tasks_covered": has_thc,
                "thc_tasks_missing": n_tasks - has_thc,
                "thc_bliss_tasks_covered": has_thc_bliss,
                "thc_bliss_tasks_missing": n_tasks - has_thc_bliss,
                "needs_thc_qre": has_thc < n_tasks,
                "needs_thc_bliss_qre": has_thc_bliss < n_tasks,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["needs_thc_qre", "needs_thc_bliss_qre", "category", "problem_instance_short_name"],
        ascending=[False, False, True, True],
    )


def hardware_assumption_table(qre_rows: pd.DataFrame) -> pd.DataFrame:
    """Return distinct hardware/model assumption rows for QRE solver variants."""
    columns = [
        "representation",
        "source_dir",
        "solver_short_name",
        "solver_uuid",
        "physical_error_rate",
        "cycle_time_microseconds",
        "num_factories",
        "parallelize_shots",
        "hardware_description",
        "algorithm_description",
        "sf_threshold",
        "df_threshold",
        "max_orbitals",
    ]
    available = [column for column in columns if column in qre_rows]
    if not available:
        return pd.DataFrame(columns=columns)
    return qre_rows[available].drop_duplicates().sort_values(
        [column for column in ["representation", "source_dir", "solver_short_name"] if column in available]
    )
