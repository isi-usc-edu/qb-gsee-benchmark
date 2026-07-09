#!/usr/bin/env python3
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

"""Generate P2 quantum-resource-estimate coverage artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.benchmark_data import canonical_problem_family
from qb_gsee_benchmark.benchmark_data import problem_instance_category_by_short_name
from qb_gsee_benchmark.qre_coverage import (
    add_task_metadata,
    coverage_by_category,
    coverage_by_solver,
    hardware_assumption_table,
    load_qre_solution_roots,
    missing_thc_instances,
    task_coverage_matrix,
)


DEFAULT_QRE_ROOTS = [
    "solution_files/PRE_solution_files_20260406_0.000001_0.1us",
    "solution_files/PRE_solution_files_20260406_0.000001_1us",
    "solution_files/PRE_solution_files_20260406_0.0001_0.1us",
    "solution_files/PRE_solution_files_20260406_0.0001_1us",
    "solution_files/PRE_solution_files_20260406_0.0001_1us_parallel",
    "solution_files/PRE_solution_files_20250304_benchq",
    "solution_files/PRE_TopQAD",
    "solution_files/thc_qre",
    "solution_files/thc_bliss_qre",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ham-features",
        type=Path,
        default=Path("scripts/Hamiltonian_features.csv"),
        help="Current Hamiltonian feature CSV, relative to repo root unless absolute.",
    )
    parser.add_argument(
        "--problem-instances-dir",
        type=Path,
        default=Path("problem_instances"),
        help="Problem-instance root for category lookup.",
    )
    parser.add_argument(
        "--qre-root",
        type=Path,
        action="append",
        default=None,
        help="QRE solution root. Can be repeated. Defaults to known DF/TopQAD/THC roots.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../analysis/p2_qre_coverage"),
        help="Output directory, relative to repo root unless absolute.",
    )
    return parser.parse_args()


def resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    if df.empty:
        return "(no rows)"
    columns = list(df.columns)
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("|" + "|".join(["---"] * len(columns)) + "|")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines)


def _current_tasks_with_groups(
        hamiltonian_features: pd.DataFrame,
        problem_instances_dir: Path,
    ) -> pd.DataFrame:
    current = hamiltonian_features.copy()
    if "family" not in current and "problem_instance_short_name" in current:
        current["family"] = current["problem_instance_short_name"].map(canonical_problem_family)
    if "category" not in current and "problem_instance_short_name" in current:
        categories = problem_instance_category_by_short_name(str(problem_instances_dir))
        current["category"] = current["problem_instance_short_name"].map(categories).fillna("unknown")
    return current


def _write_coverage_markdown(
        output_dir: Path,
        current_tasks: pd.DataFrame,
        qre_rows: pd.DataFrame,
        by_solver: pd.DataFrame,
        by_category: pd.DataFrame,
        missing_instances: pd.DataFrame,
        hardware: pd.DataFrame,
    ) -> None:
    representation_summary = (
        qre_rows[qre_rows["in_current_hamiltonian_features"]]
        .groupby("representation")
        .agg(
            solution_rows=("task_uuid", "size"),
            current_tasks_covered=("task_uuid", "nunique"),
            problem_instances_covered=("problem_instance_uuid", "nunique"),
        )
        .reset_index()
    )
    representation_summary["current_tasks_total"] = len(current_tasks)
    representation_summary["coverage_fraction"] = (
        representation_summary["current_tasks_covered"] / len(current_tasks)
        if len(current_tasks)
        else 0.0
    )

    missing_thc = missing_instances[missing_instances["needs_thc_qre"]]
    missing_bliss = missing_instances[missing_instances["needs_thc_bliss_qre"]]
    hardware_focus = hardware[
        hardware["representation"].isin(["DF_QPE", "THC_QPE", "THC_BLISS_QPE"])
    ][[
        "representation",
        "source_dir",
        "solver_short_name",
        "physical_error_rate",
        "cycle_time_microseconds",
        "num_factories",
        "parallelize_shots",
    ]].drop_duplicates()

    lines = [
        "# P2 QRE Coverage Report",
        "",
        f"Current Hamiltonian feature tasks: {len(current_tasks)}",
        f"Parsed QRE solution rows: {len(qre_rows)}",
        f"Parsed current-task QRE rows: {int(qre_rows['in_current_hamiltonian_features'].sum())}",
        "",
        "## Representation Coverage",
        "",
        _markdown_table(representation_summary),
        "",
        "## Hardware Assumptions",
        "",
        "These rows are the evidence for the DF-vs-THC apples-to-apples check. The current archive has several DF hardware variants, while THC/THC-BLISS use their own 1 mHa hardware assumption rows; direct comparisons should select matching physical-error-rate and cycle-time assumptions where possible.",
        "",
        _markdown_table(hardware_focus, max_rows=30),
        "",
        "## Category Coverage",
        "",
        _markdown_table(by_category, max_rows=80),
        "",
        "## THC Follow-Up List",
        "",
        f"Problem instances with missing THC_QPE tasks: {len(missing_thc)} / {missing_instances['problem_instance_uuid'].nunique()}",
        f"Problem instances with missing THC_BLISS_QPE tasks: {len(missing_bliss)} / {missing_instances['problem_instance_uuid'].nunique()}",
        "",
        "See `qre_missing_thc_instances.csv` for the full task-count list. Top rows:",
        "",
        _markdown_table(missing_instances.head(25)),
        "",
        "## Artifact Index",
        "",
        "- `qre_solution_rows.csv`: parsed per-task QRE rows with resource counts and hardware metadata.",
        "- `qre_task_coverage.csv`: current task coverage booleans by QRE representation.",
        "- `qre_coverage_by_solver.csv`: coverage by solver/source/hardware variant.",
        "- `qre_coverage_by_category.csv`: feature-category matrix for QRE representations.",
        "- `qre_missing_thc_instances.csv`: instance-level list of missing THC and THC-BLISS tasks.",
        "- `qre_hardware_assumptions.csv`: distinct hardware/algorithm assumption rows.",
        "",
    ]
    (output_dir / "coverage.md").write_text("\n".join(lines))


def main() -> None:
    args = parse_args()
    repo_root = Path.cwd()
    ham_features_path = resolve_path(repo_root, args.ham_features)
    problem_instances_dir = resolve_path(repo_root, args.problem_instances_dir)
    output_dir = resolve_path(repo_root, args.output_dir)
    qre_roots = args.qre_root or [Path(root) for root in DEFAULT_QRE_ROOTS]
    qre_roots = [resolve_path(repo_root, root) for root in qre_roots]

    output_dir.mkdir(parents=True, exist_ok=True)
    hamiltonian_features = pd.read_csv(ham_features_path)
    current_tasks = _current_tasks_with_groups(hamiltonian_features, problem_instances_dir)
    qre_rows = load_qre_solution_roots(qre_roots)
    qre_rows = add_task_metadata(qre_rows, current_tasks, problem_instances_dir)
    task_coverage = task_coverage_matrix(current_tasks, qre_rows)
    by_solver = coverage_by_solver(current_tasks, qre_rows)
    by_category = coverage_by_category(task_coverage)
    missing_instances = missing_thc_instances(task_coverage)
    hardware = hardware_assumption_table(qre_rows)

    qre_rows.to_csv(output_dir / "qre_solution_rows.csv", index=False)
    task_coverage.to_csv(output_dir / "qre_task_coverage.csv", index=False)
    by_solver.to_csv(output_dir / "qre_coverage_by_solver.csv", index=False)
    by_category.to_csv(output_dir / "qre_coverage_by_category.csv", index=False)
    missing_instances.to_csv(output_dir / "qre_missing_thc_instances.csv", index=False)
    hardware.to_csv(output_dir / "qre_hardware_assumptions.csv", index=False)
    _write_coverage_markdown(
        output_dir=output_dir,
        current_tasks=current_tasks,
        qre_rows=qre_rows,
        by_solver=by_solver,
        by_category=by_category,
        missing_instances=missing_instances,
        hardware=hardware,
    )
    print(f"wrote QRE coverage artifacts to {output_dir}")


if __name__ == "__main__":
    main()
