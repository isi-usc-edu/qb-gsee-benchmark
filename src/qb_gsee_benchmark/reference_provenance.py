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

"""Utilities for auditing reference-energy provenance metadata."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROVENANCE_FIELDS = [
    "category",
    "problem_instance_short_name",
    "problem_instance_uuid",
    "task_uuid",
    "reference_energy",
    "reference_energy_units",
    "reference_energy_source",
    "reference_energy_method",
    "reference_energy_provenance",
    "reference_energy_cross_validation_methods",
    "reference_energy_independent_of_shci_family",
    "reference_energy_note",
    "reference_provenance_grade",
    "curation_tier",
    "reference_independence_from_solvers",
    "model_hamiltonian_downfolded",
    "source_defect_documented",
    "planting_mechanism",
]


def _csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return value


def collect_reference_provenance_rows(
    problem_instances_directory: str | Path,
) -> list[dict[str, Any]]:
    """Collect one reference-provenance row per task."""
    problem_instances_directory = Path(problem_instances_directory)
    rows: list[dict[str, Any]] = []
    for instance_path in sorted(problem_instances_directory.rglob("*.json")):
        with instance_path.open() as file:
            instance = json.load(file)
        category = instance_path.parent.name
        for task in instance.get("tasks", []):
            requirements = task.get("requirements", {})
            row = {
                "category": category,
                "problem_instance_short_name": instance.get("short_name"),
                "problem_instance_uuid": instance.get("problem_instance_uuid"),
                "task_uuid": task.get("task_uuid"),
                "reference_energy": requirements.get("reference_energy"),
                "reference_energy_units": requirements.get("reference_energy_units"),
                "reference_energy_source": requirements.get("reference_energy_source"),
                "reference_energy_method": requirements.get("reference_energy_method"),
                "reference_energy_provenance": requirements.get(
                    "reference_energy_provenance"
                ),
                "reference_energy_cross_validation_methods": requirements.get(
                    "reference_energy_cross_validation_methods"
                ),
                "reference_energy_independent_of_shci_family": requirements.get(
                    "reference_energy_independent_of_shci_family"
                ),
                "reference_energy_note": requirements.get("reference_energy_note"),
                "reference_provenance_grade": task.get("reference_provenance_grade"),
                "curation_tier": task.get("curation_tier"),
                "reference_independence_from_solvers": task.get("reference_independence_from_solvers"),
                "model_hamiltonian_downfolded": task.get("model_hamiltonian_downfolded"),
                "source_defect_documented": task.get("source_defect_documented"),
                "planting_mechanism": task.get("planting_mechanism"),
            }
            rows.append(row)
    return rows


def reference_provenance_summary(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Summarize task counts by category and provenance label."""
    counts = Counter(
        (row["category"], row.get("reference_energy_provenance") or "unlabeled")
        for row in rows
    )
    return [
        {"category": category, "reference_energy_provenance": provenance, "tasks": tasks}
        for (category, provenance), tasks in sorted(counts.items())
    ]


def write_reference_provenance_report(
    rows: list[dict[str, Any]],
    output_directory: str | Path,
) -> None:
    """Write CSV and markdown artifacts for reference provenance coverage."""
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    rows_csv = output_directory / "reference_provenance_tasks.csv"
    with rows_csv.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=PROVENANCE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in PROVENANCE_FIELDS})

    summary_rows = reference_provenance_summary(rows)
    summary_csv = output_directory / "reference_provenance_by_category.csv"
    with summary_csv.open("w", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=["category", "reference_energy_provenance", "tasks"]
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    provenance_counts = Counter(
        row.get("reference_energy_provenance") or "unlabeled" for row in rows
    )
    unlabeled = [
        row
        for row in rows
        if not row.get("reference_energy_provenance")
    ]

    lines = [
        "# Reference Provenance Coverage",
        "",
        f"Total tasks: {len(rows)}",
        "",
        "## By Provenance",
        "",
        "| provenance | tasks |",
        "|---|---:|",
    ]
    for provenance, tasks in sorted(provenance_counts.items()):
        lines.append(f"| {provenance} | {tasks} |")

    lines.extend([
        "",
        "## By Category",
        "",
        "| category | provenance | tasks |",
        "|---|---|---:|",
    ])
    for row in summary_rows:
        lines.append(
            f"| {row['category']} | {row['reference_energy_provenance']} | {row['tasks']} |"
        )

    lines.extend([
        "",
        "## Unlabeled Tasks",
        "",
    ])
    if unlabeled:
        lines.append(f"Unlabeled tasks: {len(unlabeled)}. First 25 are listed below.")
        lines.extend([
            "",
            "| category | instance | task_uuid |",
            "|---|---|---|",
        ])
        for row in unlabeled[:25]:
            lines.append(
                "| "
                f"{row['category']} | "
                f"{row['problem_instance_short_name']} | "
                f"{row['task_uuid']} |"
            )
    else:
        lines.append("All tasks have `reference_energy_provenance` metadata.")

    (output_directory / "summary.md").write_text("\n".join(lines) + "\n")
