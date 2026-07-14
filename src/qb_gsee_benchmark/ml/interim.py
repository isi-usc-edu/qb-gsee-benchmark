"""Pinned, deterministic interim ML-v2 evaluation.

This module implements the pre-mean-field protocol frozen by ML_GOALS.
It deliberately has no import-time I/O and never launches solver work.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import ConstantKernel, RBF
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, log_loss
from sklearn.model_selection import GridSearchCV, GroupKFold, LeaveOneGroupOut, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler
from sklearn.svm import SVC

FEATURE_TABLE_SHA256 = "21d5d671ff2f471a762bd241622b89c42a79aaeb61adb0b5ab4d73729979e62c"
METADATA_SHA256 = "e4bf0d1fe8265aa0a510ccb649d94460bcbfa7a5955f0380bd77a7c4056142b6"
SOURCE_OUTCOME_VOCABULARY = ("success", "miss", "indeterminate", "not_attempted")
MODEL_LABELS = ("success", "miss", "indeterminate")
PRIMARY_MODELS = ("ridge_logistic", "elastic_net_logistic")
SENSITIVITY_MODELS = ("rbf_gp", "rbf_svm", "hist_gradient_boosting")
MODEL_NAMES = PRIMARY_MODELS + SENSITIVITY_MODELS
BASELINE_NAMES = ("majority_class", "size_log_dimension", "size_spline_gate")
SEEDS = {"cv": 20260712, "model": 117, "bootstrap": 9041}
BOOTSTRAP_RESAMPLES = 1000
MIN_STRATUM_TASKS = 30
MIN_STRATUM_FAMILIES = 3
MIN_CLASS_COUNT = 2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_json_dump(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _finite_or_none(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def json_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {str(key): _finite_or_none(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def load_instance_tasks(problem_instances: Path) -> dict[str, dict[str, str]]:
    tasks: dict[str, dict[str, str]] = {}
    for path in sorted(problem_instances.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        family = path.parent.name
        for task in payload.get("tasks", []):
            task_uuid = str(task["task_uuid"])
            record = {
                "family": str(task.get("family") or family),
                "tier": str(task.get("curation_tier") or "unspecified"),
            }
            if task_uuid in tasks and tasks[task_uuid] != record:
                raise ValueError(f"Conflicting task metadata for {task_uuid}")
            tasks[task_uuid] = record
    return tasks


def load_pinned_inputs(repo_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    feature_path = repo_root / "scripts/Hamiltonian_features.csv"
    metadata_path = repo_root / "analysis/feature_schema/feature_column_metadata.csv"
    metrics_path = repo_root / "scripts/dashboard_data/metrics_v1_8.json"
    if sha256_file(feature_path) != FEATURE_TABLE_SHA256:
        raise ValueError("Pinned feature-table SHA-256 mismatch")
    if sha256_file(metadata_path) != METADATA_SHA256:
        raise ValueError("Pinned feature-metadata SHA-256 mismatch")
    features = pd.read_csv(feature_path, low_memory=False)
    metadata = pd.read_csv(metadata_path)
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if features.shape != (591, 253):
        raise ValueError(f"Pinned feature-table shape mismatch: {features.shape}")
    if metadata.shape[0] != 253 or set(metadata["column"]) != set(features.columns):
        raise ValueError("Feature metadata does not cover the table columns exactly")
    if metrics.get("metrics_spec_version") != "1.8":
        raise ValueError("Label bundle is not metrics spec v1.8")
    return features, metadata, metrics


def _screened_columns(metadata: pd.DataFrame) -> tuple[list[str], dict[str, int]]:
    eligible = metadata["model_eligible"].astype(bool)
    t3 = metadata["provenance_tier"].eq("T3")
    audit = metadata["role"].eq("audit-only")
    current = metadata["implementation_status"].eq("current")
    scientific_tier = metadata["provenance_tier"].isin(["T0", "T1", "T2"])
    selected = metadata.loc[
        eligible & ~t3 & ~audit & current & scientific_tier, "column"
    ].tolist()
    return selected, {
        "input_columns": int(len(metadata)),
        "model_eligible_false_dropped": int((~eligible).sum()),
        "t3_dropped": int(t3.sum()),
        "audit_only_dropped": int(audit.sum()),
        "not_current_dropped": int((~current).sum()),
        "selected_t0_t2_model_columns": int(len(selected)),
    }


def _block_for_column(column: str) -> str:
    if column in {"log_fci_dim", "n_elec", "n_orbs"}:
        return "a_size_dimension"
    if column.startswith("interaction_spectrum_"):
        return "c_two_electron_spectrum"
    if column.startswith(("det_coupling_", "random_det_")):
        return "d_determinant_coupling"
    if column.startswith(("cut_weight_", "interaction_graph_", "min_fill_", "mpo_pair_")):
        return "e_orderability_mpo"
    return "b_coefficient_sparsity"


def feature_contract(features: pd.DataFrame, metadata: pd.DataFrame) -> dict[str, Any]:
    selected, counts = _screened_columns(metadata)
    universal = [column for column in selected if features[column].notna().all()]
    blocks: dict[str, list[str]] = defaultdict(list)
    for column in universal:
        blocks[_block_for_column(column)].append(column)
    required_blocks = {
        "a_size_dimension", "b_coefficient_sparsity", "c_two_electron_spectrum",
        "d_determinant_coupling", "e_orderability_mpo",
    }
    if set(blocks) != required_blocks:
        raise ValueError(f"Universal core block mismatch: {sorted(blocks)}")
    task_order = features["task_uuid"].astype(str).tolist()
    by_mask: dict[tuple[bool, ...], list[str]] = defaultdict(list)
    for column in selected:
        if column not in universal:
            by_mask[tuple(features[column].notna().tolist())].append(column)
    extensions = []
    ordered_groups = sorted(by_mask.items(), key=lambda item: (-sum(item[0]), sorted(item[1])))
    for index, (mask, columns) in enumerate(ordered_groups, start=1):
        task_uuids = [task for task, keep in zip(task_order, mask) if keep]
        extensions.append({
            "name": f"extension_{index:02d}",
            "columns": sorted(columns),
            "n_feature_tasks": len(task_uuids),
            "task_uuids": sorted(task_uuids),
        })
    return {
        "screen_counts": counts,
        "model_eligible_t0_t2_columns": sorted(selected),
        "universal_core": {
            "definition": (
                "Model-eligible current T0-T2 columns populated on every one of "
                "the 591 pinned feature rows; no missing value is imputed."
            ),
            "columns": sorted(universal),
            "n_columns": len(universal),
            "blocks": {key: sorted(value) for key, value in sorted(blocks.items())},
        },
        "domain_extensions": extensions,
    }


def scored_label_frame(
    metrics: Mapping[str, Any], instance_tasks: Mapping[str, Mapping[str, str]]
) -> pd.DataFrame:
    rows = []
    for source in metrics["primitives"]:
        outcome = str(source["outcome"])
        if outcome not in MODEL_LABELS:
            raise ValueError(f"Unexpected scored outcome {outcome}")
        task_uuid = str(source["task_uuid"])
        authoritative = instance_tasks.get(task_uuid)
        if authoritative is None:
            raise ValueError(f"Scored task {task_uuid} is absent from instance JSONs")
        if authoritative["tier"] == "test":
            raise ValueError(f"Test-tier task {task_uuid} leaked into scored labels")
        if str(source["tier"]) != authoritative["tier"]:
            raise ValueError(f"Tier mismatch for {task_uuid}")
        if str(source["family"]) != authoritative["family"]:
            raise ValueError(f"Family mismatch for {task_uuid}")
        rows.append({
            "task_uuid": task_uuid,
            "solver": str(source["solver"]),
            "campaign": str(source["campaign"]),
            "family": authoritative["family"],
            "tier": authoritative["tier"],
            "outcome": outcome,
        })
    frame = pd.DataFrame(rows).sort_values(
        ["solver", "campaign", "task_uuid"], kind="stable"
    )
    if frame.duplicated(["solver", "campaign", "task_uuid"]).any():
        raise ValueError("Duplicate solver/campaign/task label")
    return frame.reset_index(drop=True)


def _git_code_version(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
    ).strip()


def build_manifest(repo_root: Path) -> dict[str, Any]:
    features, metadata, metrics = load_pinned_inputs(repo_root)
    instance_tasks = load_instance_tasks(repo_root / "problem_instances")
    labels = scored_label_frame(metrics, instance_tasks)
    contract = feature_contract(features, metadata)
    feature_tasks = set(features["task_uuid"].astype(str))
    label_tasks = set(labels["task_uuid"])
    if not label_tasks <= feature_tasks:
        raise ValueError("Some scored label tasks lack pinned feature rows")
    cells = []
    for (solver, campaign), group in labels.groupby(["solver", "campaign"], sort=True):
        counts = Counter(group["outcome"])
        family_counts = Counter(group["family"])
        cells.append({
            "solver": solver,
            "campaign": campaign,
            "n_scored_tasks": int(len(group)),
            "label_counts": {label: int(counts.get(label, 0)) for label in MODEL_LABELS},
            "family_counts": dict(sorted(family_counts.items())),
        })
    families = {
        family: sorted(group["task_uuid"].unique().tolist())
        for family, group in labels.groupby("family", sort=True)
    }
    return {
        "manifest_version": "ml-v2-interim-1",
        "interim": True,
        "interim_label": "INTERIM (pre-mean-field feature set)",
        "inputs": {
            "feature_table": {
                "path": "scripts/Hamiltonian_features.csv",
                "sha256": FEATURE_TABLE_SHA256,
                "shape": [591, 253],
            },
            "feature_metadata": {
                "stated_path_in_ml_goals": "scripts/feature_column_metadata.csv",
                "resolved_committed_path": "analysis/feature_schema/feature_column_metadata.csv",
                "sha256": METADATA_SHA256,
                "source_commit": "6b9e879",
            },
            "labels": {
                "path": "scripts/dashboard_data/metrics_v1_8.json",
                "sha256": sha256_file(repo_root / "scripts/dashboard_data/metrics_v1_8.json"),
                "metrics_spec_version": metrics["metrics_spec_version"],
                "source_outcome_vocabulary": list(SOURCE_OUTCOME_VOCABULARY),
                "model_label_vocabulary": list(MODEL_LABELS),
                "not_attempted_is_label": False,
                "solver_campaign_cells": cells,
            },
        },
        "features": contract,
        "tasks": {
            "test_tier_exclusion": "curation_tier == test",
            "n_feature_tasks_after_test_exclusion": int(
                sum(row["tier"] != "test" for row in instance_tasks.values())
            ),
            "n_scored_tasks": len(label_tasks),
            "scored_task_uuids": sorted(label_tasks),
            "family_to_scored_task_uuids": families,
        },
        "validation": {
            "headline": "leave_one_family_out",
            "headline_definition": "Exact leave-one-family-out grouped outer CV.",
            "random_fold": "random_5fold_leakage_diagnostic_only",
            "family_bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "family_balanced_metrics": ["brier", "log_loss", "average_precision"],
            "calibration": "one-vs-rest equal-width probability bins",
            "preprocessing": "fit inside every outer fold",
            "inner_cv": "GroupKFold by family whenever tuning is enabled",
        },
        "models": {
            "primary": list(PRIMARY_MODELS),
            "sensitivity_only": list(SENSITIVITY_MODELS),
            "hyperparameter_grids": {
                "ridge_logistic": {"model__C": [0.1, 1.0, 10.0]},
                "elastic_net_logistic": {
                    "model__C": [0.1, 1.0, 10.0],
                    "model__l1_ratio": [0.25, 0.5, 0.75],
                },
                "rbf_gp": {},
                "rbf_svm": {"model__C": [1.0], "model__gamma": ["scale"]},
                "hist_gradient_boosting": {
                    "model__learning_rate": [0.05],
                    "model__max_leaf_nodes": [15],
                },
            },
        },
        "baselines": {
            "majority_class": "Fold-local empirical class probabilities.",
            "size_log_dimension": "Multinomial ridge model on log_fci_dim.",
            "size_spline_gate": (
                "Multinomial ridge model on n_elec and n_orbs with cubic "
                "SplineTransformer(n_knots=4), fit inside each outer fold."
            ),
        },
        "domain_extension_floor": {
            "minimum_tasks": MIN_STRATUM_TASKS,
            "minimum_families": MIN_STRATUM_FAMILIES,
            "minimum_count_per_observed_class": MIN_CLASS_COUNT,
            "below_floor_status": "insufficient_data",
            "evaluation_models": list(PRIMARY_MODELS),
            "evaluation_protocol": "leave_one_family_out",
        },
        "seeds": SEEDS,
        "code_version": _git_code_version(repo_root),
    }


def _model_pipeline(name: str, seed: int) -> Pipeline:
    if name == "ridge_logistic":
        model = LogisticRegression(
            penalty="l2", solver="lbfgs", max_iter=4000, random_state=seed
        )
        return Pipeline([("scale", StandardScaler()), ("model", model)])
    if name == "elastic_net_logistic":
        model = LogisticRegression(
            penalty="elasticnet", solver="saga", max_iter=6000,
            random_state=seed, tol=1e-4,
        )
        return Pipeline([("scale", StandardScaler()), ("model", model)])
    if name == "rbf_gp":
        kernel = ConstantKernel(1.0, constant_value_bounds="fixed") * RBF(
            1.0, length_scale_bounds="fixed"
        )
        return Pipeline([
            ("scale", StandardScaler()),
            ("model", GaussianProcessClassifier(kernel=kernel, random_state=seed)),
        ])
    if name == "rbf_svm":
        return Pipeline([
            ("scale", StandardScaler()),
            ("model", SVC(probability=True, class_weight="balanced", random_state=seed)),
        ])
    if name == "hist_gradient_boosting":
        return Pipeline([("model", HistGradientBoostingClassifier(
            max_iter=100, learning_rate=0.05, max_leaf_nodes=15,
            random_state=seed,
        ))])
    if name == "size_log_dimension":
        return Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=4000, random_state=seed)),
        ])
    if name == "size_spline_gate":
        transform = ColumnTransformer([(
            "spline",
            SplineTransformer(n_knots=4, degree=3, include_bias=False),
            ["n_elec", "n_orbs"],
        )], remainder="drop")
        return Pipeline([
            ("spline", transform),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=4000, random_state=seed)),
        ])
    raise ValueError(f"Unknown model {name}")


def _align_probabilities(probabilities: np.ndarray, classes: Sequence[str]) -> np.ndarray:
    aligned = np.zeros((len(probabilities), len(MODEL_LABELS)), dtype=float)
    for source_index, label in enumerate(classes):
        aligned[:, MODEL_LABELS.index(str(label))] = probabilities[:, source_index]
    row_sum = aligned.sum(axis=1)
    aligned[row_sum == 0.0] = 1.0 / len(MODEL_LABELS)
    aligned /= aligned.sum(axis=1, keepdims=True)
    return aligned


def _splits(data: pd.DataFrame, protocol: str) -> list[tuple[np.ndarray, np.ndarray]]:
    y = data["outcome"].to_numpy()
    if protocol == "leave_one_family_out":
        return list(LeaveOneGroupOut().split(data, y, data["family"]))
    if protocol == "random_5fold_leakage_diagnostic_only":
        counts = Counter(y)
        n_splits = min(5, min(counts.values()))
        if n_splits < 2:
            return []
        return list(StratifiedKFold(
            n_splits=n_splits, shuffle=True, random_state=SEEDS["cv"]
        ).split(data, y))
    raise ValueError(f"Unknown protocol {protocol}")


def _fixed_label_neg_log_loss(
    estimator: Any, x_test: pd.DataFrame, y_test: Sequence[str]
) -> float:
    """Score an inner family fold whose held-out labels may be single-class."""
    return -float(log_loss(
        y_test,
        estimator.predict_proba(x_test),
        labels=list(estimator.classes_),
    ))

class _FeasibleGroupKFold:
    """GroupKFold with training sides that retain at least two classes."""

    def __init__(self, n_splits: int):
        self.n_splits = n_splits

    def split(
        self, x_data: Any, y_data: Sequence[str], groups: Sequence[str]
    ):
        labels = np.asarray(y_data)
        splitter = GroupKFold(n_splits=self.n_splits)
        for train_index, test_index in splitter.split(x_data, labels, groups):
            if len(np.unique(labels[train_index])) >= 2:
                yield train_index, test_index

    def get_n_splits(
        self,
        x_data: Any = None,
        y_data: Sequence[str] | None = None,
        groups: Sequence[str] | None = None,
    ) -> int:
        if x_data is None or y_data is None or groups is None:
            return self.n_splits
        return sum(1 for _ in self.split(x_data, y_data, groups))



def oof_probabilities(
    data: pd.DataFrame,
    feature_columns: Sequence[str],
    model_name: str,
    protocol: str,
    param_grid: Mapping[str, Sequence[Any]] | None,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    probabilities = np.full((len(data), len(MODEL_LABELS)), np.nan)
    folds = []
    for fold, (train_index, test_index) in enumerate(_splits(data, protocol)):
        train = data.iloc[train_index]
        test = data.iloc[test_index]
        counts = Counter(train["outcome"])
        if len(counts) < 2:
            prior = np.array([counts.get(label, 0) for label in MODEL_LABELS], dtype=float)
            probabilities[test_index] = prior / prior.sum()
            tuned = False
            best_params: dict[str, Any] = {}
        else:
            estimator = _model_pipeline(model_name, SEEDS["model"] + fold)
            grid = dict(param_grid or {})
            tuned = False
            best_params = {}
            if grid and model_name in PRIMARY_MODELS:
                n_groups = train["family"].nunique()
                if n_groups >= 2:
                    search = GridSearchCV(
                        estimator, grid, scoring=_fixed_label_neg_log_loss,
                        cv=_FeasibleGroupKFold(n_splits=min(3, n_groups)),
                        refit=True, error_score="raise", n_jobs=1,
                    )
                    search.fit(
                        train[list(feature_columns)], train["outcome"],
                        groups=train["family"],
                    )
                    estimator = search.best_estimator_
                    best_params = dict(sorted(search.best_params_.items()))
                    tuned = True
                else:
                    estimator.fit(train[list(feature_columns)], train["outcome"])
            else:
                estimator.fit(train[list(feature_columns)], train["outcome"])
            raw = estimator.predict_proba(test[list(feature_columns)])
            probabilities[test_index] = _align_probabilities(raw, estimator.classes_)
        folds.append({
            "fold": fold,
            "n_train": len(train),
            "n_test": len(test),
            "held_out_families": sorted(test["family"].unique().tolist())
            if protocol == "leave_one_family_out" else [],
            "tuned": tuned,
            "best_params": best_params,
        })
    return probabilities, folds


def majority_oof(data: pd.DataFrame, protocol: str) -> np.ndarray:
    probabilities = np.full((len(data), len(MODEL_LABELS)), np.nan)
    for train_index, test_index in _splits(data, protocol):
        counts = Counter(data.iloc[train_index]["outcome"])
        prior = np.array([counts.get(label, 0) for label in MODEL_LABELS], dtype=float)
        probabilities[test_index] = prior / prior.sum()
    return probabilities


def _family_weights(families: Sequence[str]) -> np.ndarray:
    counts = Counter(map(str, families))
    n_families = len(counts)
    return np.array([1.0 / (n_families * counts[str(item)]) for item in families])


def family_balanced_scores(data: pd.DataFrame, probabilities: np.ndarray) -> dict[str, float]:
    y = data["outcome"].to_numpy()
    weights = _family_weights(data["family"].tolist())
    truth = np.zeros_like(probabilities)
    for index, label in enumerate(y):
        truth[index, MODEL_LABELS.index(str(label))] = 1.0
    brier = float(np.sum(weights * np.sum((probabilities - truth) ** 2, axis=1)))
    clipped = np.clip(probabilities, 1e-15, 1.0)
    loss = float(-np.sum(weights[:, None] * truth * np.log(clipped)))
    per_class = []
    for class_index in range(len(MODEL_LABELS)):
        if truth[:, class_index].min() == truth[:, class_index].max():
            continue
        per_class.append(average_precision_score(
            truth[:, class_index], probabilities[:, class_index], sample_weight=weights
        ))
    average_precision = float(np.mean(per_class)) if per_class else float("nan")
    return {"brier": brier, "log_loss": loss, "average_precision": average_precision}


def family_bootstrap(
    data: pd.DataFrame, probabilities: np.ndarray, resamples: int = BOOTSTRAP_RESAMPLES
) -> dict[str, dict[str, float | None]]:
    families = sorted(data["family"].unique().tolist())
    rng = np.random.default_rng(SEEDS["bootstrap"])
    samples: dict[str, list[float]] = defaultdict(list)
    positions = {
        family: np.flatnonzero(data["family"].to_numpy() == family)
        for family in families
    }
    for _ in range(resamples):
        drawn = rng.choice(families, size=len(families), replace=True)
        indexes = np.concatenate([positions[family] for family in drawn])
        boot = data.iloc[indexes].copy()
        boot["family"] = [
            f"{family}__draw_{index}"
            for index, family in enumerate(drawn)
            for _ in positions[family]
        ]
        score = family_balanced_scores(boot, probabilities[indexes])
        for metric, value in score.items():
            if math.isfinite(value):
                samples[metric].append(value)
    result = {}
    for metric in ("brier", "log_loss", "average_precision"):
        values = samples[metric]
        result[metric] = {
            "lower": float(np.quantile(values, 0.025)) if values else None,
            "upper": float(np.quantile(values, 0.975)) if values else None,
            "resamples": len(values),
        }
    return result


def calibration_records(
    data: pd.DataFrame, probabilities: np.ndarray, bins: int = 10
) -> list[dict[str, Any]]:
    records = []
    y = data["outcome"].to_numpy()
    edges = np.linspace(0.0, 1.0, bins + 1)
    for class_index, label in enumerate(MODEL_LABELS):
        scores = probabilities[:, class_index]
        truth = y == label
        assigned = np.minimum(np.searchsorted(edges, scores, side="right") - 1, bins - 1)
        for bin_index in range(bins):
            mask = assigned == bin_index
            records.append({
                "outcome": label,
                "bin": bin_index,
                "lower": float(edges[bin_index]),
                "upper": float(edges[bin_index + 1]),
                "n": int(mask.sum()),
                "mean_probability": float(scores[mask].mean()) if mask.any() else None,
                "observed_rate": float(truth[mask].mean()) if mask.any() else None,
            })
    return records


def stratum_status(data: pd.DataFrame) -> tuple[str, dict[str, Any]]:
    counts = Counter(data["outcome"])
    evidence = {
        "n_tasks": int(len(data)),
        "n_families": int(data["family"].nunique()),
        "label_counts": {label: int(counts.get(label, 0)) for label in MODEL_LABELS},
    }
    enough = (
        evidence["n_tasks"] >= MIN_STRATUM_TASKS
        and evidence["n_families"] >= MIN_STRATUM_FAMILIES
        and all(value >= MIN_CLASS_COUNT for value in counts.values())
        and len(counts) >= 2
    )
    return ("ok" if enough else "insufficient_data"), evidence
