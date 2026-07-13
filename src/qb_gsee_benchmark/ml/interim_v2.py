"""Predeclared ML-3 robustness statistics for the interim ML-v2 study."""

from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

from qb_gsee_benchmark.ml.interim import MODEL_LABELS, SEEDS

MACRO_AP_MIN_POSITIVES = 5
IDENTIFIER_F1_THRESHOLD = 0.95
PAIRED_BOOTSTRAP_RESAMPLES = 1000
SHUFFLE_PERMUTATIONS = 10
MULTIPLICITY_ALPHA = 0.05
INTERIM_STATEMENT = (
    "On the completed a–e feature blocks, models do not demonstrate "
    "out-of-family predictive skill beyond size-only baselines under paired "
    "family-bootstrap separation (4/315 separations, below chance); features "
    "carry real descriptive structure (family separability) and one candidate "
    "per-task signal (SHCI_var miss ranking) under investigation."
)


def _selected_probabilities(
    probabilities: np.ndarray, labels: Sequence[str]
) -> np.ndarray:
    indexes = [MODEL_LABELS.index(label) for label in labels]
    selected = probabilities[:, indexes].astype(float, copy=True)
    totals = selected.sum(axis=1)
    selected[totals == 0.0] = 1.0 / len(labels)
    selected /= selected.sum(axis=1, keepdims=True)
    return selected


def family_balanced_scores_v2(
    data: pd.DataFrame,
    probabilities: np.ndarray,
    *,
    labels: Sequence[str] = MODEL_LABELS,
    min_ap_positives: int = MACRO_AP_MIN_POSITIVES,
) -> dict[str, Any]:
    """Score predictions with equal total weight per represented family."""
    labels = tuple(labels)
    selected = _selected_probabilities(probabilities, labels)
    y = data["outcome"].astype(str).to_numpy()
    counts = Counter(y)
    family_counts = Counter(data["family"].astype(str))
    weights = np.array(
        [
            1.0 / (len(family_counts) * family_counts[str(family)])
            for family in data["family"]
        ]
    )
    truth = np.zeros_like(selected)
    for row, label in enumerate(y):
        truth[row, labels.index(label)] = 1.0
    brier = float(np.sum(weights * np.sum((selected - truth) ** 2, axis=1)))
    clipped = np.clip(selected, 1e-15, 1.0)
    loss = float(-np.sum(weights[:, None] * truth * np.log(clipped)))
    included = [
        label
        for label in labels
        if counts[label] >= min_ap_positives and counts[label] < len(data)
    ]
    per_class = {
        label: float(
            average_precision_score(
                truth[:, labels.index(label)],
                selected[:, labels.index(label)],
                sample_weight=weights,
            )
        )
        for label in included
    }
    return {
        "brier": brier,
        "log_loss": loss,
        "average_precision": (
            float(np.mean(list(per_class.values()))) if per_class else None
        ),
        "average_precision_class_floor": {
            "minimum_positives": min_ap_positives,
            "included_classes": included,
            "excluded_classes": [label for label in labels if label not in included],
            "positive_counts": {label: int(counts[label]) for label in labels},
            "per_class": per_class,
        },
    }


def paired_family_bootstrap(
    data: pd.DataFrame,
    model_probabilities: np.ndarray,
    baseline_probabilities: Mapping[str, np.ndarray],
    *,
    labels: Sequence[str] = MODEL_LABELS,
    resamples: int = PAIRED_BOOTSTRAP_RESAMPLES,
    seed: int = SEEDS["bootstrap"],
) -> dict[str, Any]:
    """Return oriented model improvements using identical family draws."""
    baseline_names = tuple(sorted(baseline_probabilities))
    point_model = family_balanced_scores_v2(data, model_probabilities, labels=labels)
    point_baselines = {
        name: family_balanced_scores_v2(data, value, labels=labels)
        for name, value in baseline_probabilities.items()
    }
    families = sorted(data["family"].astype(str).unique())
    positions = {
        family: np.flatnonzero(data["family"].astype(str).to_numpy() == family)
        for family in families
    }
    samples: dict[str, dict[str, list[float]]] = {
        baseline: defaultdict(list) for baseline in baseline_names
    }
    composite_ap: list[float] = []
    rng = np.random.default_rng(seed)
    for _ in range(resamples):
        drawn = rng.choice(families, size=len(families), replace=True)
        indexes = np.concatenate([positions[family] for family in drawn])
        boot = data.iloc[indexes].copy()
        boot["family"] = [
            f"{family}__draw_{draw}"
            for draw, family in enumerate(drawn)
            for _ in positions[family]
        ]
        model_score = family_balanced_scores_v2(
            boot, model_probabilities[indexes], labels=labels
        )
        baseline_scores = {
            name: family_balanced_scores_v2(
                boot, baseline_probabilities[name][indexes], labels=labels
            )
            for name in baseline_names
        }
        for name in baseline_names:
            for metric in ("average_precision", "brier", "log_loss"):
                model_value = model_score[metric]
                baseline_value = baseline_scores[name][metric]
                if model_value is None or baseline_value is None:
                    continue
                delta = (
                    model_value - baseline_value
                    if metric == "average_precision"
                    else baseline_value - model_value
                )
                samples[name][metric].append(float(delta))
        model_ap = model_score["average_precision"]
        size_aps = [
            baseline_scores[name]["average_precision"]
            for name in ("size_log_dimension", "size_spline_gate")
        ]
        if model_ap is not None and all(value is not None for value in size_aps):
            composite_ap.append(float(model_ap - max(size_aps)))

    def summarize(values: Sequence[float], point: float | None) -> dict[str, Any]:
        if not values or point is None:
            return {
                "point_improvement": point,
                "lower_95": None,
                "upper_95": None,
                "two_sided_p": None,
                "resamples": len(values),
            }
        array = np.asarray(values)
        left = (np.count_nonzero(array <= 0.0) + 1) / (len(array) + 1)
        right = (np.count_nonzero(array >= 0.0) + 1) / (len(array) + 1)
        return {
            "point_improvement": float(point),
            "lower_95": float(np.quantile(array, 0.025)),
            "upper_95": float(np.quantile(array, 0.975)),
            "two_sided_p": float(min(1.0, 2.0 * min(left, right))),
            "resamples": len(values),
        }

    comparisons: dict[str, Any] = {}
    for name in baseline_names:
        comparisons[name] = {}
        for metric in ("average_precision", "brier", "log_loss"):
            model_value = point_model[metric]
            baseline_value = point_baselines[name][metric]
            point = (
                None
                if model_value is None or baseline_value is None
                else (
                    model_value - baseline_value
                    if metric == "average_precision"
                    else baseline_value - model_value
                )
            )
            comparisons[name][metric] = summarize(samples[name][metric], point)
    point_ap = point_model["average_precision"]
    point_size = [
        point_baselines[name]["average_precision"]
        for name in ("size_log_dimension", "size_spline_gate")
    ]
    composite_point = (
        None
        if point_ap is None or any(value is None for value in point_size)
        else float(point_ap - max(point_size))
    )
    return {
        "orientation": "positive values favor the model",
        "identical_family_draws": True,
        "labels": list(labels),
        "model_scores": point_model,
        "baseline_scores": point_baselines,
        "comparisons": comparisons,
        "size_composite_average_precision": summarize(composite_ap, composite_point),
    }


def holm_bonferroni(
    records: Sequence[dict[str, Any]], *, alpha: float = MULTIPLICITY_ALPHA
) -> list[dict[str, Any]]:
    """Attach deterministic Holm adjusted p-values and decisions."""
    usable = [record for record in records if record.get("two_sided_p") is not None]
    ordered = sorted(
        usable,
        key=lambda row: (float(row["two_sided_p"]), str(row["comparison_id"])),
    )
    running = 0.0
    adjusted: dict[str, float] = {}
    total = len(ordered)
    for rank, record in enumerate(ordered):
        running = max(running, (total - rank) * float(record["two_sided_p"]))
        adjusted[str(record["comparison_id"])] = min(1.0, running)
    output = []
    for record in records:
        row = dict(record)
        value = adjusted.get(str(row["comparison_id"]))
        row["holm_adjusted_p"] = value
        row["passes_multiplicity"] = bool(value is not None and value < alpha)
        row["passes_paired_gate"] = bool(
            row["passes_multiplicity"]
            and row.get("lower_95") is not None
            and float(row["lower_95"]) > 0.0
        )
        output.append(row)
    return output


def detect_family_identifier_columns(
    features: pd.DataFrame,
    families: Sequence[str],
    columns: Sequence[str],
    *,
    threshold: float = IDENTIFIER_F1_THRESHOLD,
) -> dict[str, Any]:
    """Detect columns that identify any family with a single decision split."""
    family_array = np.asarray(list(map(str, families)))
    ledger = []
    identifiers = set()
    for column in sorted(columns):
        values = features[column].to_numpy(dtype=float)
        matches = []
        best_overall = {"family": None, "f1": 0.0, "threshold": None, "side": None}
        for family in sorted(set(family_array)):
            truth = family_array == family
            order = np.argsort(values, kind="stable")
            sorted_values = values[order]
            sorted_truth = truth[order]
            boundaries = np.flatnonzero(sorted_values[:-1] < sorted_values[1:])
            total_positives = int(sorted_truth.sum())
            cumulative_positives = np.cumsum(sorted_truth)
            candidates = []
            for index in boundaries:
                left_count = int(index + 1)
                left_true = int(cumulative_positives[index])
                right_count = len(sorted_truth) - left_count
                right_true = total_positives - left_true
                for side, true_positives, predicted_positives in (
                    ("less_than_or_equal", left_true, left_count),
                    ("greater_than", right_true, right_count),
                ):
                    denominator = predicted_positives + total_positives
                    score = (
                        0.0 if denominator == 0 else 2.0 * true_positives / denominator
                    )
                    candidates.append(
                        {
                            "family": family,
                            "f1": float(score),
                            "threshold": float(sorted_values[index]),
                            "side": side,
                        }
                    )
            best = max(
                candidates,
                key=lambda row: (row["f1"], -row["threshold"], row["side"]),
                default={
                    "family": family,
                    "f1": 0.0,
                    "threshold": None,
                    "side": None,
                },
            )
            if best["f1"] > best_overall["f1"]:
                best_overall = best
            if best["f1"] >= threshold:
                matches.append(best)
        if matches:
            identifiers.add(column)
        ledger.append(
            {
                "column": column,
                "max_one_vs_rest_f1": best_overall["f1"],
                "best_one_vs_rest_split": best_overall,
                "threshold_matches": matches,
                "is_family_identifier": bool(matches),
            }
        )
    return {
        "procedure": (
            "For each universal-core column and family, exhaustively evaluate "
            "every observed single-threshold split in both directions against "
            "the one-vs-rest family label; flag the column if the maximum "
            "full-corpus F1 is at least the frozen threshold."
        ),
        "threshold": threshold,
        "n_columns_screened": len(columns),
        "identifier_columns": sorted(identifiers),
        "ledger": ledger,
    }


def build_manifest_v2(repo_root: Any) -> dict[str, Any]:
    """Build ML-3's pre-run manifest without fitting an outcome model."""
    from pathlib import Path

    from qb_gsee_benchmark.ml.interim import (
        PRIMARY_MODELS,
        build_manifest,
        load_instance_tasks,
        load_pinned_inputs,
        scored_label_frame,
        sha256_file,
    )

    root = Path(repo_root)
    base = build_manifest(root)
    features, _, metrics = load_pinned_inputs(root)
    task_metadata = load_instance_tasks(root / "problem_instances")
    families = [task_metadata[str(task)]["family"] for task in features["task_uuid"]]
    full_corpus_screen = detect_family_identifier_columns(
        features,
        families,
        base["features"]["universal_core"]["columns"],
    )
    scored = scored_label_frame(metrics, task_metadata)[
        ["task_uuid", "family"]
    ].drop_duplicates()
    scored_features = scored.merge(features, on="task_uuid", validate="one_to_one")
    scored_task_screen = detect_family_identifier_columns(
        scored_features,
        scored_features["family"],
        base["features"]["universal_core"]["columns"],
    )
    identifier_columns = sorted(
        set(full_corpus_screen["identifier_columns"])
        | set(scored_task_screen["identifier_columns"])
    )
    identifier_screen = {
        "procedure": (
            "Apply the exhaustive single-threshold one-vs-rest family F1 screen "
            "to both the complete 591-row pinned feature corpus and the 202 "
            "unique tasks represented in scored metrics-v1.8 primitives, then "
            "take the union; outcome values are never read by the detector."
        ),
        "threshold": IDENTIFIER_F1_THRESHOLD,
        "identifier_columns": identifier_columns,
        "n_identifier_columns": len(identifier_columns),
        "populations": {
            "full_feature_corpus": full_corpus_screen,
            "unique_scored_tasks": scored_task_screen,
        },
    }
    prior_results_path = root / "analysis/ml_v2/results.json"
    prior_predictions_path = root / "analysis/ml_v2/predictions.json"
    prior_results = json.loads(prior_results_path.read_text(encoding="utf-8"))
    historical_gate_count = sum(
        row.get("status") == "ok" and row.get("protocol") == "leave_one_family_out"
        for row in prior_results
    )
    shci_cells = [
        {"solver": cell["solver"], "campaign": cell["campaign"]}
        for cell in base["inputs"]["labels"]["solver_campaign_cells"]
        if str(cell["solver"]).startswith("SHCI_var_")
    ]
    shci_comparison_count = len(shci_cells) * len(PRIMARY_MODELS) * 2 * 2
    code_version = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    return {
        "manifest_version": "ml-v2-interim-2",
        "interim": True,
        "interim_label": base["interim_label"],
        "parent_manifest": {
            "path": "analysis/ml_v2/manifest.json",
            "sha256": sha256_file(root / "analysis/ml_v2/manifest.json"),
            "accepted_goals": ["ML-1", "ML-2"],
            "goals_review": 13,
        },
        "inputs": base["inputs"],
        "features": base["features"],
        "tasks": base["tasks"],
        "models": base["models"],
        "baselines": base["baselines"],
        "seeds": base["seeds"] | {"shuffle": 20260713},
        "prior_artifacts": {
            "results": {
                "path": "analysis/ml_v2/results.json",
                "sha256": sha256_file(prior_results_path),
            },
            "predictions": {
                "path": "analysis/ml_v2/predictions.json",
                "sha256": sha256_file(prior_predictions_path),
            },
        },
        "macro_average_precision": {
            "minimum_positives_per_class": MACRO_AP_MIN_POSITIVES,
            "rule": (
                "Within each scored cell and class treatment, exclude a class "
                "from macro-AP when it has fewer than 5 positive examples; "
                "record included/excluded classes and counts."
            ),
        },
        "paired_delta_gate": {
            "metric": "family_balanced_macro_average_precision",
            "bootstrap_unit": "family",
            "resamples": PAIRED_BOOTSTRAP_RESAMPLES,
            "identical_draws": True,
            "interval": "two-sided percentile 95%",
            "comparison": (
                "model AP minus max(size_log_dimension AP, size_spline_gate AP) "
                "within every identical bootstrap draw"
            ),
            "multiplicity_method": "Holm-Bonferroni FWER",
            "alpha": MULTIPLICITY_ALPHA,
            "historical_family": {
                "definition": (
                    "Every previously scored status=ok, non-diagnostic exact-LOFO "
                    "record, one composite size comparison per record."
                ),
                "comparison_count": historical_gate_count,
            },
            "shci_confirmatory_family": {
                "definition": (
                    "All SHCI_var cells x two primary models x full-class and "
                    "success+miss treatments x with/without identifier columns."
                ),
                "comparison_count": shci_comparison_count,
            },
            "pass_rule": (
                "The raw paired 95% lower bound is >0 and the Holm-adjusted "
                "two-sided bootstrap p-value is <0.05."
            ),
        },
        "family_identifier_screen": identifier_screen,
        "sensitivity_plan": {
            "identifier_column_sets": ["with_identifiers", "without_identifiers"],
            "class_treatments": {
                "full_class": list(MODEL_LABELS),
                "success_plus_miss": ["success", "miss"],
            },
            "shci_var_cells": shci_cells,
            "models": list(PRIMARY_MODELS),
        },
        "shuffle_null": {
            "permutations": SHUFFLE_PERMUTATIONS,
            "procedure": (
                "For every paired-gate survivor, independently permute outcome "
                "labels within each family, refit the same outer/inner grouped "
                "pipeline, and recompute the composite size AP improvement."
            ),
            "survival_rule": (
                "A gate survivor survives the shuffle null only when its observed "
                "point improvement exceeds all permutation improvements."
            ),
        },
        "adjudication": {
            "goals_review": 13,
            "legacy_flag_disposition": "VALID AS FILED; NOT PIVOTAL",
            "interim_statement": INTERIM_STATEMENT,
        },
        "code_version": code_version,
    }
