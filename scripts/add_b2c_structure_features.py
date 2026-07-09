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

"""Backfill B2c structural proxy columns into Hamiltonian_features.csv."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.benchmark_data import (
    canonical_problem_family,
    problem_instance_category_by_short_name,
)
from qb_gsee_benchmark.features.structure_features import (
    STRUCTURE_PROXY_FEATURE_COLUMNS,
    STRUCTURE_PROXY_VERSION,
    build_structure_proxy_category_coverage,
    enrich_hamiltonian_features_with_structure_proxies,
    structure_proxy_coverage,
    structure_proxy_metadata_dataframe,
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
        "--problem-instances-dir",
        type=Path,
        default=None,
        help="Problem-instance root used to map short names to categories.",
    )
    parser.add_argument(
        "--analysis-dir",
        type=Path,
        default=None,
        help="Optional directory for B2c structural-proxy artifacts and coverage report.",
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


def _markdown_table(df: pd.DataFrame) -> str:
    columns = list(df.columns)
    rows = ["| " + " | ".join(columns) + " |"]
    rows.append("|" + "|".join(["---"] * len(columns)) + "|")
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(rows)


def _write_coverage_markdown(
        path: Path,
        enriched: pd.DataFrame,
        coverage: pd.DataFrame,
    ) -> None:
    lines = [
        "# B2c structural proxy feature coverage",
        "",
        f"Structural proxy version: `{STRUCTURE_PROXY_VERSION}`",
        f"Current Hamiltonian feature rows: {len(enriched)}",
        "",
        "## Whole-table coverage",
        "",
        _markdown_table(
            coverage.assign(
                coverage_fraction=coverage["coverage_fraction"].map(lambda value: f"{value:.3f}"),
                min=coverage["min"].map(lambda value: f"{value:.6g}"),
                median=coverage["median"].map(lambda value: f"{value:.6g}"),
                max=coverage["max"].map(lambda value: f"{value:.6g}"),
            )
        ),
        "",
        "## Scope and limitations",
        "",
        "These columns are deterministic post-processing of the current Hamiltonian feature table. They provide Pauli-term sparsity and interaction-hypergraph heterogeneity proxies that are useful for B2 block ablations, but they do not replace the remaining raw-FCIDUMP/local-orbital calculations.",
        "",
        "Still open for item 3b: post-BLISS one-norm ratio, thresholded raw integral sparsity, localized-exchange bandwidth from an orbital-localized K matrix, and MP2 natural-occupation entropy.",
        "",
        "Generated files:",
        "- `Hamiltonian_features_b2c.csv`: enriched feature table with family/category labels for auditing.",
        "- `structure_proxy_summary.csv`: whole-table coverage and distribution summaries.",
        "- `coverage_by_feature_category.csv`: feature coverage by problem-instance category.",
        "- `coverage_matrix.csv`: feature-by-category coverage pivot.",
        "- `feature_metadata.csv`: scaling/cost/representation tags for the new B2c columns.",
        "",
    ]
    path.write_text("\n".join(lines))


def write_analysis_artifacts(
        analysis_dir: Path,
        enriched: pd.DataFrame,
        problem_instances_dir: Path | None,
    ) -> None:
    analysis_dir.mkdir(parents=True, exist_ok=True)
    grouped = _add_group_columns(enriched, problem_instances_dir)
    coverage = structure_proxy_coverage(grouped)
    category_coverage = build_structure_proxy_category_coverage(grouped)

    grouped.to_csv(analysis_dir / "Hamiltonian_features_b2c.csv", index=False)
    coverage.to_csv(analysis_dir / "structure_proxy_summary.csv", index=False)
    category_coverage.to_csv(analysis_dir / "coverage_by_feature_category.csv", index=False)
    category_coverage.pivot(
        index="feature",
        columns="category",
        values="coverage_fraction",
    ).to_csv(analysis_dir / "coverage_matrix.csv")
    structure_proxy_metadata_dataframe().to_csv(
        analysis_dir / "feature_metadata.csv",
        index=False,
    )
    _write_coverage_markdown(
        analysis_dir / "coverage.md",
        enriched=grouped,
        coverage=coverage,
    )


def main() -> None:
    args = parse_args()
    output_csv = args.output_csv or args.input_csv
    repo_root = _default_repo_root(args.input_csv)
    problem_instances_dir = args.problem_instances_dir or repo_root / "problem_instances"

    features = pd.read_csv(args.input_csv)
    enriched = enrich_hamiltonian_features_with_structure_proxies(features)
    enriched.to_csv(output_csv, index=False)

    present_all = int(enriched[STRUCTURE_PROXY_FEATURE_COLUMNS].notna().all(axis=1).sum())
    print(
        f"wrote {output_csv} with {present_all}/{len(enriched)} rows populated "
        "for all B2c structural proxy features"
    )

    if args.analysis_dir is not None:
        write_analysis_artifacts(args.analysis_dir, enriched, problem_instances_dir)


if __name__ == "__main__":
    main()
