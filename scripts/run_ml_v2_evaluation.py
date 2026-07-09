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

"""Run ML v2 grouped-CV evaluation artifacts on current benchmark data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.benchmark_data import problem_instance_category_by_short_name
from qb_gsee_benchmark.ml.data import (
    B2_INTENSIVE_FEATURES,
    LEGACY_FULL_FEATURES,
    SIZE_ONLY_FEATURES,
    assemble_solver_ml_table,
    coerce_bool_series,
    ml_v2_candidate_features,
    ml_v2_feature_sets,
)
from qb_gsee_benchmark.ml.evaluation import evaluate_standard_comparators, make_default_protocols
from qb_gsee_benchmark.ml.importance import grouped_permutation_importance
from qb_gsee_benchmark.ml.maps import fit_feature_embedding
from qb_gsee_benchmark.ml.models import MODEL_LOGISTIC_L2, MODEL_NAMES
from qb_gsee_benchmark.ml.reporting import prediction_group_breakdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all-data",
        type=Path,
        default=Path("scripts/all_data_20260514.csv"),
        help="Solver label CSV, relative to repo root unless absolute.",
    )
    parser.add_argument(
        "--ham-features",
        type=Path,
        default=Path("scripts/Hamiltonian_features.csv"),
        help="Hamiltonian feature CSV, relative to repo root unless absolute.",
    )
    parser.add_argument(
        "--problem-instances-dir",
        type=Path,
        default=Path("problem_instances"),
        help="Problem-instance root for category lookup.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../analysis/ml_v2"),
        help="Output artifact directory, relative to repo root unless absolute.",
    )
    parser.add_argument("--seed", type=int, default=20260702)
    parser.add_argument("--bootstrap-resamples", type=int, default=0)
    parser.add_argument("--min-attempted", type=int, default=15)
    parser.add_argument("--max-solvers", type=int, default=None)
    parser.add_argument(
        "--hyperparameter-tuning",
        action="store_true",
        help="Enable grouped inner GridSearchCV for model-based evaluations.",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=[MODEL_LOGISTIC_L2],
        choices=MODEL_NAMES,
        help="Model comparators to evaluate.",
    )
    parser.add_argument(
        "--importance-solvers",
        type=int,
        default=0,
        help="Number of eligible solvers to run grouped permutation importance for.",
    )
    parser.add_argument(
        "--include-family-logo",
        action="store_true",
        help=(
            "Also run exact leave-one-family-out evaluations. This is slower "
            "than the default family GroupKFold run and is intended for paper artifacts."
        ),
    )
    return parser.parse_args()


def resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def add_category_column(labels: pd.DataFrame, problem_instances_dir: Path) -> pd.DataFrame:
    result = labels.copy()
    if "category" in result:
        return result
    mapping = problem_instance_category_by_short_name(str(problem_instances_dir))
    result["category"] = result["problem_instance_short_name"].map(mapping).fillna("unknown")
    return result


def eligible_solver_groups(
        labels: pd.DataFrame,
        min_attempted: int,
    ) -> tuple[list[tuple[tuple[str, str], pd.DataFrame]], pd.DataFrame]:
    eligible = []
    skipped = []
    labels = labels.copy()
    labels["attempted"] = coerce_bool_series(labels["attempted"])
    labels["label"] = coerce_bool_series(labels["label"])
    for solver_key, solver_df in labels.groupby(["solver_short_name", "solver_uuid"], sort=True):
        attempted = solver_df[solver_df["attempted"]].copy()
        n_rows = len(attempted)
        n_positive = int(attempted["label"].sum())
        reason = None
        if n_rows < min_attempted:
            reason = "fewer_than_min_attempted_tasks"
        elif attempted["label"].nunique() < 2:
            reason = "single_label_class"
        if reason is not None:
            skipped.append(
                {
                    "solver_short_name": solver_key[0],
                    "solver_uuid": solver_key[1],
                    "attempted_tasks": n_rows,
                    "positive_labels": n_positive,
                    "negative_labels": n_rows - n_positive,
                    "reason": reason,
                }
            )
            continue
        eligible.append((solver_key, solver_df.reset_index(drop=True)))
    return eligible, pd.DataFrame(skipped)


def write_summary(
        output_dir: Path,
        results: pd.DataFrame,
        skipped: pd.DataFrame,
        include_family_logo: bool = False,
    ) -> None:
    lines = [
        "# ML v2 evaluation summary",
        "",
        f"Generated at UTC: {datetime.now(timezone.utc).isoformat()}",
        f"Eligible solver UUIDs: {results['solver_uuid'].nunique() if not results.empty else 0}",
        f"Skipped solver UUIDs: {len(skipped)}",
        "",
    ]
    if not results.empty:
        grouped = results[results["protocol"].str.startswith("family_groupkfold")]
        logistic = grouped[grouped["model"] == MODEL_LOGISTIC_L2]
        pivot = logistic.pivot_table(
            index=["solver_short_name", "solver_uuid"],
            columns="feature_set",
            values="average_precision",
            aggfunc="first",
        )
        if {"full16", "size_only"}.issubset(pivot.columns):
            pivot["full16_minus_size_only_ap"] = pivot["full16"] - pivot["size_only"]
        if {"full16_plus_b2", "size_only"}.issubset(pivot.columns):
            pivot["full16_plus_b2_minus_size_only_ap"] = (
                pivot["full16_plus_b2"] - pivot["size_only"]
            )
        pivot = pivot.reset_index()
        pivot.to_csv(output_dir / "ml_v2_family_grouped_feature_comparison.csv", index=False)
        lines.extend(
            [
                "## Family-grouped feature comparison",
                "",
                "See `ml_v2_family_grouped_feature_comparison.csv` for per-solver AP deltas.",
                "",
            ]
        )

        random = results[results["protocol"].str.startswith("random_")]
        leakage = logistic.merge(
            random[random["model"] == MODEL_LOGISTIC_L2],
            on=["solver_short_name", "solver_uuid", "model", "feature_set"],
            suffixes=("_grouped", "_random"),
        )
        if not leakage.empty:
            leakage["average_precision_random_minus_grouped"] = (
                leakage["average_precision_random"] - leakage["average_precision_grouped"]
            )
            leakage.to_csv(output_dir / "ml_v2_random_vs_grouped_leakage.csv", index=False)
            lines.extend(
                [
                    "## Random-vs-grouped leakage",
                    "",
                    "See `ml_v2_random_vs_grouped_leakage.csv` for random split overstatement.",
                    "",
                ]
            )
    companion_summaries = [
        (
            "Held-out-family summary",
            "heldout_summary.md",
            "aggregate grouped-validation, size-baseline, and leakage numbers used in the draft",
        ),
        (
            "Held-out group breakdown summary",
            "group_breakdown_summary.md",
            "per-category and per-family precision, recall, F1, Brier, and calibration-style rates",
        ),
        (
            "Feature importance summary",
            "importance_summary.md",
            "grouped permutation-importance results used in the draft interpretability text",
        ),
        (
            "Feature-set upgrade summary",
            "feature_set_upgrade_summary.md",
            "B2 feature coverage and block-ablation results",
        ),
    ]
    if include_family_logo:
        companion_summaries.append(
            (
                "Exact leave-one-family-out summary",
                "family_logo_summary.md",
                "leave-one-family-out metrics and group breakdowns for the paper held-out experiment",
            )
        )
    for title, filename, description in companion_summaries:
        if (output_dir / filename).exists():
            lines.extend([f"## {title}", "", f"See `{filename}` for {description}.", ""])

    (output_dir / "summary.md").write_text("\n".join(lines) + "\n")


def _format_markdown_value(value: object) -> str:
    if pd.isna(value):
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "No rows."
    rows = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for _, row in df[columns].iterrows():
        rows.append("| " + " | ".join(_format_markdown_value(row[column]) for column in columns) + " |")
    return "\n".join(rows)


def write_group_breakdown_summary(output_dir: Path, group_breakdown: pd.DataFrame) -> None:
    """Write a compact markdown view of primary held-out group metrics."""
    lines = [
        "# ML-v2 held-out group breakdown",
        "",
        "Source artifact: `ml_v2_group_breakdown.csv`.",
        "",
        "Rows summarize primary family-grouped, `logistic_l2`, `full16_plus_b2` out-of-fold predictions. Per-group rank metrics are intentionally omitted because many families are small or single-class; precision, recall, F1, Brier, observed positive rate, predicted positive rate, and mean probability are reported instead.",
        "",
    ]
    if group_breakdown.empty:
        lines.extend(["No primary group-breakdown rows were generated.", ""])
        (output_dir / "group_breakdown_summary.md").write_text("\n".join(lines))
        return

    category = group_breakdown[group_breakdown["group_type"] == "category"].copy()
    family = group_breakdown[group_breakdown["group_type"] == "family"].copy()
    lines.extend(
        [
            f"Category rows: {len(category)}. Family rows: {len(family)}.",
            "",
            "## Category Metrics for Key Solvers",
            "",
        ]
    )
    key_solvers = [
        "SHCI_var_2e-4",
        "SHCI_var_1e-4",
        "SHCI_opt",
        "DMRG_Niagara_cluster_lowest_energy",
        "CCSD(T)",
        "CCSD",
        "CISD",
    ]
    key_category = category[category["solver_short_name"].isin(key_solvers)].copy()
    key_category["solver_sort"] = key_category["solver_short_name"].map(
        {name: idx for idx, name in enumerate(key_solvers)}
    )
    key_category = key_category.sort_values(["solver_sort", "group"]).drop(columns=["solver_sort"])
    lines.append(
        _markdown_table(
            key_category,
            [
                "solver_short_name",
                "group",
                "n_tasks",
                "positive_labels",
                "precision",
                "recall",
                "f1",
                "brier",
                "observed_positive_rate",
                "mean_probability",
            ],
        )
    )

    lines.extend(["", "## Lowest-F1 Family Rows", ""])
    family_with_signal = family[(family["n_tasks"] >= 3) & (family["positive_labels"] > 0)].copy()
    family_with_signal["f1_sort"] = family_with_signal["f1"].fillna(-1.0)
    low_family = family_with_signal.sort_values(
        ["f1_sort", "n_tasks", "solver_short_name", "group"], ascending=[True, False, True, True]
    ).head(25)
    if not low_family.empty:
        low_family = low_family.drop(columns=["f1_sort"])
    lines.append(
        _markdown_table(
            low_family,
            [
                "solver_short_name",
                "group",
                "n_tasks",
                "positive_labels",
                "precision",
                "recall",
                "f1",
                "brier",
                "mean_probability",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The CSV is the authoritative per-family/per-category table for the paper. The category view is compact enough for an appendix table; the low-F1 family rows identify where held-out predictions are currently weakest and should be compared against reference provenance and solver-attempt coverage before making chemical claims.",
            "",
        ]
    )
    (output_dir / "group_breakdown_summary.md").write_text("\n".join(lines))


def write_family_logo_summary(
        output_dir: Path,
        results: pd.DataFrame,
        predictions: pd.DataFrame,
    ) -> pd.DataFrame:
    """Write exact leave-one-family-out metrics and compact summaries."""
    logo = results[
        (results["protocol"] == "leave_one_family_out")
        & (results["model"] == MODEL_LOGISTIC_L2)
    ].copy()
    if logo.empty:
        (output_dir / "family_logo_summary.md").write_text(
            "# Exact leave-one-family-out summary\n\nNo leave-one-family-out rows were generated.\n"
        )
        return pd.DataFrame()

    pivot = logo.pivot_table(
        index=["solver_short_name", "solver_uuid"],
        columns="feature_set",
        values="average_precision",
        aggfunc="first",
    )
    if {"full16", "size_only"}.issubset(pivot.columns):
        pivot["full16_minus_size_only_ap"] = pivot["full16"] - pivot["size_only"]
    if {"full16_plus_b2", "size_only"}.issubset(pivot.columns):
        pivot["full16_plus_b2_minus_size_only_ap"] = pivot["full16_plus_b2"] - pivot["size_only"]
    comparison = pivot.reset_index()
    comparison.to_csv(output_dir / "ml_v2_family_logo_feature_comparison.csv", index=False)

    logo_breakdown = prediction_group_breakdown(
        predictions,
        protocol_prefix="leave_one_family_out",
    )
    logo_breakdown.to_csv(output_dir / "ml_v2_family_logo_group_breakdown.csv", index=False)

    primary = logo[logo["feature_set"] == "full16_plus_b2"].copy()
    if primary.empty:
        primary = logo[logo["feature_set"] == "full16"].copy()
    key_solvers = [
        "SHCI_var_2e-4",
        "SHCI_var_1e-4",
        "SHCI_opt",
        "DMRG_Niagara_cluster_lowest_energy",
        "CCSD(T)",
        "CCSD",
        "CISD",
    ]
    key_rows = primary[primary["solver_short_name"].isin(key_solvers)].copy()
    key_rows["solver_sort"] = key_rows["solver_short_name"].map(
        {name: idx for idx, name in enumerate(key_solvers)}
    )
    key_rows = key_rows.sort_values(["solver_sort", "solver_uuid"]).drop(columns=["solver_sort"])

    delta_col = "full16_plus_b2_minus_size_only_ap"
    delta = comparison[delta_col].dropna() if delta_col in comparison else pd.Series(dtype=float)
    lines = [
        "# Exact leave-one-family-out summary",
        "",
        "Source artifacts: `ml_v2_results.csv`, `ml_v2_family_logo_feature_comparison.csv`, and `ml_v2_family_logo_group_breakdown.csv`.",
        "",
        "Protocol: `leave_one_family_out`; each fold holds out exactly one canonical molecular family. This is stricter than the default `family_groupkfold_5` artifact and is intended for the paper's held-out-family audit.",
        "",
        f"Eligible solver UUIDs with exact family-LOO rows: {primary['solver_uuid'].nunique()}.",
    ]
    if not delta.empty:
        lines.extend(
            [
                f"Primary `full16_plus_b2` beats size-only by >0.05 AP for {int((delta > 0.05).sum())} solver UUIDs, is within +/-0.05 for {int((delta.abs() <= 0.05).sum())}, and trails size-only by >0.05 for {int((delta < -0.05).sum())}.",
                f"Mean AP delta vs size-only: {delta.mean():.3f}; median: {delta.median():.3f}.",
            ]
        )
    lines.extend(["", "## Key solver metrics", ""])
    lines.append(
        _markdown_table(
            key_rows,
            [
                "solver_short_name",
                "n_tasks",
                "positive_labels",
                "average_precision",
                "auroc",
                "mcc",
                "brier",
                "empirical_instance_coverage",
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Group-breakdown coverage",
            "",
            f"Exact LOO group-breakdown rows: {len(logo_breakdown)}.",
            "",
            "Interpretation: use this artifact when a reviewer asks for literal leave-one-family-out evidence. The default GroupKFold artifact remains the faster, lower-variance headline validation used by the standard report, while this exact LOO table is the strictest held-out-family stress test.",
            "",
        ]
    )
    (output_dir / "family_logo_summary.md").write_text("\n".join(lines))
    return logo_breakdown


def main() -> None:
    args = parse_args()
    repo_root = Path.cwd()
    all_data_path = resolve_path(repo_root, args.all_data)
    ham_features_path = resolve_path(repo_root, args.ham_features)
    problem_instances_dir = resolve_path(repo_root, args.problem_instances_dir)
    output_dir = resolve_path(repo_root, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels = pd.read_csv(all_data_path)
    labels = add_category_column(labels, problem_instances_dir)
    features = pd.read_csv(ham_features_path)
    present_feature_columns = ml_v2_candidate_features(features)

    eligible, skipped = eligible_solver_groups(labels, args.min_attempted)
    if args.max_solvers is not None:
        eligible = eligible[:args.max_solvers]

    result_frames = []
    prediction_frames = []
    fold_frames = []
    calibration_frames = []
    importance_frames = []

    for solver_idx, (solver_key, solver_labels) in enumerate(eligible):
        table = assemble_solver_ml_table(
            solver_labels=solver_labels,
            hamiltonian_features=features,
            feature_columns=present_feature_columns,
            solver_uuid=solver_key[1],
        )
        y = table["label"].to_numpy(dtype=bool)
        protocols = make_default_protocols(
            table,
            y,
            seed=args.seed,
            include_family_leave_one_out=args.include_family_logo,
        )
        feature_sets = ml_v2_feature_sets(table)
        results, predictions, folds, calibration = evaluate_standard_comparators(
            data=table,
            feature_sets=feature_sets,
            protocols=protocols,
            model_names=args.models,
            bootstrap_resamples=args.bootstrap_resamples,
            seed=args.seed,
            hyperparameter_tuning=args.hyperparameter_tuning,
        )
        result_frames.append(results)
        prediction_frames.append(predictions)
        fold_frames.append(folds)
        calibration_frames.append(calibration)

        if solver_idx < args.importance_solvers and protocols:
            importance = grouped_permutation_importance(
                data=table,
                feature_columns=feature_sets.get("full16_plus_b2", feature_sets["full16"]),
                protocol=protocols[0],
                model_name=MODEL_LOGISTIC_L2,
                n_repeats=3,
                seed=args.seed,
            )
            importance.insert(0, "solver_uuid", solver_key[1])
            importance.insert(0, "solver_short_name", solver_key[0])
            importance_frames.append(importance)

    results = pd.concat(result_frames, ignore_index=True) if result_frames else pd.DataFrame()
    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    folds = pd.concat(fold_frames, ignore_index=True) if fold_frames else pd.DataFrame()
    calibration = pd.concat(calibration_frames, ignore_index=True) if calibration_frames else pd.DataFrame()
    importance = pd.concat(importance_frames, ignore_index=True) if importance_frames else pd.DataFrame()
    group_breakdown = prediction_group_breakdown(predictions) if not predictions.empty else pd.DataFrame()
    family_logo_breakdown = (
        write_family_logo_summary(output_dir, results, predictions)
        if args.include_family_logo
        else pd.DataFrame()
    )

    results.to_csv(output_dir / "ml_v2_results.csv", index=False)
    predictions.to_csv(output_dir / "ml_v2_oof_predictions.csv", index=False)
    folds.to_csv(output_dir / "ml_v2_folds.csv", index=False)
    calibration.to_csv(output_dir / "ml_v2_calibration.csv", index=False)
    group_breakdown.to_csv(output_dir / "ml_v2_group_breakdown.csv", index=False)
    write_group_breakdown_summary(output_dir, group_breakdown)
    skipped.to_csv(output_dir / "ml_v2_skipped_solvers.csv", index=False)
    if not importance.empty:
        importance.to_csv(output_dir / "ml_v2_permutation_importance.csv", index=False)

    embedding_columns = [column for column in LEGACY_FULL_FEATURES + B2_INTENSIVE_FEATURES if column in features]
    if embedding_columns:
        map_features = features.copy()
        if "family" not in map_features and "problem_instance_short_name" in map_features:
            from qb_gsee_benchmark.benchmark_data import canonical_problem_family
            map_features["family"] = map_features["problem_instance_short_name"].map(canonical_problem_family)
        if "category" not in map_features and "problem_instance_short_name" in map_features:
            mapping = problem_instance_category_by_short_name(str(problem_instances_dir))
            map_features["category"] = map_features["problem_instance_short_name"].map(mapping).fillna("unknown")
        for method in ["pca", "nnmf"]:
            embedding = fit_feature_embedding(map_features, embedding_columns, method=method, seed=args.seed)
            embedding.coordinates.to_csv(output_dir / f"ml_v2_{method}_coordinates.csv", index=False)
            embedding.loadings.to_csv(output_dir / f"ml_v2_{method}_loadings.csv", index=False)
            (output_dir / f"ml_v2_{method}_metadata.json").write_text(
                json.dumps(embedding.metadata, indent=2) + "\n"
            )

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "all_data": str(all_data_path),
        "ham_features": str(ham_features_path),
        "seed": args.seed,
        "bootstrap_resamples": args.bootstrap_resamples,
        "hyperparameter_tuning": args.hyperparameter_tuning,
        "include_family_logo": args.include_family_logo,
        "eligible_solver_uuid_count": len(eligible),
        "skipped_solver_uuid_count": len(skipped),
        "family_logo_group_breakdown_rows": int(len(family_logo_breakdown)),
    }
    (output_dir / "ml_v2_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    write_summary(output_dir, results, skipped, include_family_logo=args.include_family_logo)
    print(f"wrote ML v2 artifacts for {len(eligible)} solver UUIDs to {output_dir}")


if __name__ == "__main__":
    main()
