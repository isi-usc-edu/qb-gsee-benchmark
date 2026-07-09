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

"""Backfill B2b PySCF diagnostic columns into Hamiltonian_features.csv."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.benchmark_data import (
    canonical_problem_family,
    problem_instance_category_by_short_name,
)
from qb_gsee_benchmark.features.pyscf_diagnostics import (
    PYSCF_DIAGNOSTIC_FEATURE_COLUMNS,
    PYSCF_DIAGNOSTICS_VERSION,
    build_pyscf_feature_category_coverage,
    enrich_hamiltonian_features_with_pyscf_diagnostics,
    load_pyscf_solution_directory,
    pyscf_diagnostic_metadata_dataframe,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_csv",
        type=Path,
        help="Input Hamiltonian_features.csv file.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Output CSV path. Defaults to overwriting input_csv.",
    )
    parser.add_argument(
        "--pyscf-solutions-dir",
        type=Path,
        default=None,
        help="Directory containing top-level PySCF solution JSON files.",
    )
    parser.add_argument(
        "--problem-instances-dir",
        type=Path,
        default=None,
        help="Problem-instance root used to map short names to categories.",
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=None,
        help="Optional directory for B2b diagnostics artifacts and coverage report.",
    )
    return parser.parse_args()


def _default_repo_root(input_csv: Path) -> Path:
    if input_csv.parent.name == "scripts":
        return input_csv.parent.parent
    return Path.cwd()


def _add_group_columns(df: pd.DataFrame, problem_instances_dir: Path | None) -> pd.DataFrame:
    grouped = df.copy()
    grouped["family"] = grouped["problem_instance_short_name"].map(canonical_problem_family)
    if problem_instances_dir is None or not problem_instances_dir.exists():
        grouped["category"] = "unknown"
        return grouped
    category_by_short_name = problem_instance_category_by_short_name(str(problem_instances_dir))
    grouped["category"] = (
        grouped["problem_instance_short_name"].map(category_by_short_name).fillna("unknown")
    )
    return grouped


def _method_overlap_table(features: pd.DataFrame, solution_rows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    feature_tasks = set(features["task_uuid"])
    for method_slug, method_rows in solution_rows.groupby("method_slug", dropna=False):
        method_tasks = set(method_rows["task_uuid"].dropna())
        rows.append(
            {
                "method_slug": method_slug,
                "solution_rows": int(len(method_rows)),
                "unique_solution_tasks": int(len(method_tasks)),
                "current_feature_tasks_with_solution": int(len(feature_tasks & method_tasks)),
            }
        )
    return pd.DataFrame(rows).sort_values("method_slug")



def _markdown_table(df: pd.DataFrame) -> str:
    """Render a small dataframe as markdown without optional dependencies."""
    columns = list(df.columns)
    rows = ["| " + " | ".join(columns) + " |"]
    rows.append("|" + "|".join(["---"] * len(columns)) + "|")
    for _, row in df.iterrows():
        rows.append(
            "| "
            + " | ".join(str(row[column]) for column in columns)
            + " |"
        )
    return "\n".join(rows)

def _write_coverage_markdown(
        path: Path,
        features: pd.DataFrame,
        enriched_for_coverage: pd.DataFrame,
        solution_rows: pd.DataFrame,
        coverage: pd.DataFrame,
        method_overlap: pd.DataFrame,
    ) -> None:
    lines = [
        "# B2b PySCF diagnostics coverage",
        "",
        f"PySCF diagnostics version: `{PYSCF_DIAGNOSTICS_VERSION}`",
        f"Current Hamiltonian feature rows: {len(features)}",
        f"Parsed PySCF solution rows: {len(solution_rows)}",
        f"Unique parsed PySCF tasks: {solution_rows['task_uuid'].nunique(dropna=True)}",
        "",
        "## Method overlap with current feature table",
        "",
        _markdown_table(method_overlap),
        "",
        "## Feature coverage",
        "",
        "| feature | present / total | coverage | dominant missing reasons |",
        "|---|---:|---:|---|",
    ]
    for feature in PYSCF_DIAGNOSTIC_FEATURE_COLUMNS:
        total = len(enriched_for_coverage)
        present = int(enriched_for_coverage[feature].notna().sum())
        reason_counts = (
            enriched_for_coverage[f"{feature}_reason"]
            .value_counts(dropna=False)
            .to_dict()
        )
        reason_text = ", ".join(f"{key}: {value}" for key, value in reason_counts.items())
        lines.append(
            f"| `{feature}` | {present} / {total} | {present / total:.3f} | {reason_text} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The current PySCF solution JSON archive contains energies and runtimes, but the sampled and parsed `solution_details` fields are empty. Consequently HOMO-LUMO gaps, UHF `<S^2>`, and CCSD T1/D1/max-T2 diagnostics are represented as explicit NaN-with-reason columns rather than silent missing values.",
            "",
            "MP2 correlation energy is derived where both HF and MP2 energy rows overlap the current Hamiltonian feature table: `E_MP2 - E_HF`; the per-electron feature divides by `n_elec`.",
            "",
            "See `coverage_by_feature_category.csv` for the requested feature-by-instance-category matrix and `pyscf_diagnostics_long.csv` for the parsed per-method evidence rows.",
            "",
        ]
    )
    path.write_text("\n".join(lines))


def main() -> None:
    args = parse_args()
    output_csv = args.output_csv or args.input_csv
    repo_root = _default_repo_root(args.input_csv)
    solution_dir = args.pyscf_solutions_dir or repo_root / "solution_files" / "pyscf_solutions"
    problem_instances_dir = args.problem_instances_dir or repo_root / "problem_instances"

    features = pd.read_csv(args.input_csv)
    solution_rows = load_pyscf_solution_directory(solution_dir)
    enriched = enrich_hamiltonian_features_with_pyscf_diagnostics(
        features,
        solution_rows=solution_rows,
    )
    enriched.to_csv(output_csv, index=False)

    ok_count = int(enriched["mp2_corr_energy_per_electron"].notna().sum())
    print(
        f"wrote {output_csv} with {ok_count}/{len(enriched)} "
        "MP2 correlation-energy-per-electron values"
    )

    if args.analysis_dir is None:
        return

    args.analysis_dir.mkdir(parents=True, exist_ok=True)
    grouped = _add_group_columns(enriched, problem_instances_dir)
    coverage = build_pyscf_feature_category_coverage(grouped)
    method_overlap = _method_overlap_table(features, solution_rows)

    grouped.to_csv(args.analysis_dir / "Hamiltonian_features_b2b.csv", index=False)
    solution_rows.to_csv(args.analysis_dir / "pyscf_diagnostics_long.csv", index=False)
    coverage.to_csv(args.analysis_dir / "coverage_by_feature_category.csv", index=False)
    coverage.pivot(
        index="feature",
        columns="category",
        values="coverage_fraction",
    ).to_csv(args.analysis_dir / "coverage_matrix.csv")
    method_overlap.to_csv(args.analysis_dir / "method_overlap.csv", index=False)
    pyscf_diagnostic_metadata_dataframe().to_csv(
        args.analysis_dir / "feature_metadata.csv",
        index=False,
    )
    _write_coverage_markdown(
        args.analysis_dir / "coverage.md",
        features=features,
        enriched_for_coverage=grouped,
        solution_rows=solution_rows,
        coverage=coverage,
        method_overlap=method_overlap,
    )


if __name__ == "__main__":
    main()
