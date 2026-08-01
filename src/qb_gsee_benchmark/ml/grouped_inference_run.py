"""Deterministic target-dependent grouped inference for ML-9D."""

from __future__ import annotations

import json
import platform
import shutil
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.metrics import r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.instance_space import coordinate_preprocessing


FAMILY_TARGETS = ("dmrg", "ipie_afqmc", "shci", "trimci")
ESTIMATOR_ORDER = ("random_forest", "extra_trees")
TARGET_GATE_SUPERSESSION = Path(
    "analysis/ml9_grouped_inference/target_gate_supersession_v3.json"
)


@dataclass(frozen=True)
class PreparedInference:
    task_ids: tuple[str, ...]
    canonical_families: np.ndarray
    features: np.ndarray
    feature_names: tuple[str, ...]
    baseline_indices: np.ndarray
    contrasts: tuple[dict[str, Any], ...]
    primary_target: np.ndarray
    binary_targets: Mapping[str, np.ndarray]
    gate_evidence: Mapping[str, Any]


@dataclass(frozen=True)
class FittedComparison:
    target_kind: str
    target: str
    contrast_id: str
    contrast_group_id: str
    contrast_group_name: str
    contrast_anchor: str
    estimator: str
    baseline_feature_count: int
    added_feature_count: int
    observed: np.ndarray
    baseline_prediction: np.ndarray | None
    augmented_prediction: np.ndarray | None
    folds: np.ndarray
    gradeable: bool
    status: str


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_hash(path: Path, expected: str, label: str) -> str:
    _require(path.is_file(), f"missing ML-9D {label}: {path}")
    digest = sha256_file(path)
    _require(digest == expected, f"changed ML-9D {label}: {path}")
    return digest


def _bool_series(values: pd.Series, label: str) -> np.ndarray:
    if pd.api.types.is_bool_dtype(values):
        return values.to_numpy(dtype=bool)
    normalized = values.astype(str).str.lower()
    _require(
        bool(normalized.isin(["true", "false"]).all()),
        f"invalid boolean values in ML-9D {label}",
    )
    return normalized.eq("true").to_numpy(dtype=bool)


def verify_target_gate(
    root: Path, preregistration_path: Path, execution_contract_path: Path
) -> dict[str, Any]:
    """Verify every gate artifact before either target CSV is parsed."""

    preregistration = _read_json(preregistration_path)
    contract = _read_json(execution_contract_path)
    _require(
        preregistration.get("artifact_id")
        == "ml9d_grouped_inference_preregistration_v1",
        "wrong ML-9D preregistration",
    )
    _require(
        contract.get("artifact_id") == "ml9d_grouped_inference_execution_contract_v1",
        "wrong ML-9D execution contract",
    )
    _require(
        contract.get("frozen_before_target_access") is True,
        "ML-9D execution contract was not frozen before target access",
    )

    pinned: dict[str, str] = {}
    for path_key, hash_key, label in (
        ("preregistration_path", "preregistration_sha256", "preregistration"),
        (
            "target_gate_amendment_path",
            "target_gate_amendment_sha256",
            "target-gate amendment",
        ),
        (
            "outcome_blind_preflight_manifest_path",
            "outcome_blind_preflight_manifest_sha256",
            "outcome-blind preflight manifest",
        ),
    ):
        path = root / str(contract[path_key])
        pinned[label] = _verify_hash(path, str(contract[hash_key]), label)

    amendment = _read_json(root / str(contract["target_gate_amendment_path"]))
    _require(
        amendment.get("frozen_before_target_access") is True,
        "ML-9D target-gate amendment is not frozen",
    )
    for path_key, hash_key, label in (
        (
            "original_preregistration_path",
            "original_preregistration_sha256",
            "amendment preregistration source",
        ),
        (
            "recovery_preregistration_path",
            "recovery_preregistration_sha256",
            "ML-9C recovery preregistration",
        ),
    ):
        path = root / str(amendment[path_key])
        pinned[label] = _verify_hash(path, str(amendment[hash_key]), label)

    supersession_path = root / TARGET_GATE_SUPERSESSION
    _require(
        supersession_path.is_file(), "ML-9D target-gate supersession is unavailable"
    )
    supersession = _read_json(supersession_path)
    _require(
        supersession.get("frozen_before_target_access") is True,
        "ML-9D target-gate supersession is not frozen",
    )
    pinned["target-gate supersession"] = sha256_file(supersession_path)
    for path_key, hash_key, label in (
        (
            "prior_target_gate_amendment_path",
            "prior_target_gate_amendment_sha256",
            "supersession target-gate source",
        ),
        (
            "execution_contract_path",
            "execution_contract_sha256",
            "supersession execution-contract source",
        ),
        (
            "recovery_preregistration_path",
            "recovery_preregistration_sha256",
            "ML-9C nonnegative recovery preregistration",
        ),
    ):
        path = root / str(supersession[path_key])
        pinned[label] = _verify_hash(path, str(supersession[hash_key]), label)
    _require(
        supersession["prior_target_gate_amendment_path"]
        == contract["target_gate_amendment_path"],
        "ML-9D supersession does not extend the frozen target-gate amendment",
    )
    _require(
        supersession["execution_contract_path"]
        == str(execution_contract_path.relative_to(root)),
        "ML-9D supersession names the wrong execution contract",
    )

    gate = supersession["target_gate_change"]
    final_handoff = root / str(gate["promoted_primary_path_unchanged"])
    final_manifest = root / str(gate["promoted_manifest_path_unchanged"])
    recovery_identity = root / str(gate["accepted_recovery_identity_path"])
    _require(final_handoff.is_file(), "ML-9C promoted handoff is unavailable")
    _require(final_manifest.is_file(), "ML-9C promoted manifest is unavailable")
    _require(recovery_identity.is_file(), "ML-9C recovery identity is unavailable")

    identity = _read_json(recovery_identity)
    manifest = _read_json(final_manifest)
    report_path = final_manifest.parent / "report.json"
    _require(report_path.is_file(), "ML-9C promoted report is unavailable")
    report = _read_json(report_path)
    _require(identity.get("status") == "pass", "ML-9C recovery identity failed")
    _require(identity.get("byte_identical") is True, "ML-9C recovery is not exact")
    _require(
        identity.get("promoted") == "analysis/ml9_bayesian_irt/final_v1",
        "ML-9C recovery promoted the wrong path",
    )
    _require(
        identity.get("binary_handoff_unchanged") is True,
        "ML-9C binary handoff changed during recovery",
    )
    _require(
        manifest.get("status") == "complete_internal_posterior_estimate",
        "ML-9C promoted manifest is incomplete",
    )
    _require(
        manifest.get("all_recovery_diagnostics_pass") is True,
        "ML-9C promoted diagnostics failed",
    )
    _require(
        report.get("all_recovery_diagnostics_pass") is True,
        "ML-9C promoted report diagnostics failed",
    )

    for relative, expected in sorted(identity["file_hashes"].items()):
        _verify_hash(final_manifest.parent / relative, str(expected), "promoted file")

    recovery_preregistration = _read_json(
        root / str(supersession["recovery_preregistration_path"])
    )
    handoff_hash = _verify_hash(
        final_handoff,
        str(recovery_preregistration["binary_rasch"]["required_handoff_sha256"]),
        "promoted primary handoff",
    )

    secondary = preregistration["target_inputs"]["secondary"]
    secondary_path = root / str(secondary["path"])
    secondary_hash = _verify_hash(
        secondary_path, str(secondary["sha256"]), "secondary target"
    )
    _verify_hash(
        root / str(secondary["manifest_path"]),
        str(secondary["manifest_sha256"]),
        "secondary target manifest",
    )

    preflight_manifest_path = root / str(
        contract["outcome_blind_preflight_manifest_path"]
    )
    preflight_manifest = _read_json(preflight_manifest_path)
    _require(
        preflight_manifest.get("status") == "pass_outcome_blind_groups_frozen",
        "ML-9D outcome-blind preflight failed",
    )
    _require(
        preflight_manifest.get("scientific_targets_consumed") is False,
        "ML-9D group preflight consumed a target",
    )
    for record in preflight_manifest["files"]:
        _verify_hash(
            preflight_manifest_path.parent / str(record["path"]),
            str(record["sha256"]),
            "outcome-blind preflight file",
        )

    return {
        "artifact_id": "ml9d_target_gate_evidence_v1",
        "status": "pass_target_access_authorized",
        "primary_target_access_authorized": True,
        "secondary_target_access_authorized": True,
        "target_gate_supersession_sha256": sha256_file(supersession_path),
        "ml9c_recovery_identity_sha256": sha256_file(recovery_identity),
        "ml9c_promoted_manifest_sha256": sha256_file(final_manifest),
        "primary_handoff_sha256": handoff_hash,
        "secondary_target_sha256": secondary_hash,
        "pinned_control_hashes": pinned,
        "retained_raw_handoff_used": False,
    }


def prepare_inference(
    root: Path, preregistration_path: Path, execution_contract_path: Path
) -> PreparedInference:
    """Open the targets only after the complete deterministic gate passes."""

    gate_evidence = verify_target_gate(
        root, preregistration_path, execution_contract_path
    )
    preregistration = _read_json(preregistration_path)

    preflight = root / "analysis/ml9_grouped_inference/preflight_v1"
    feature_groups = pd.read_csv(preflight / "feature_groups.csv")
    feature_names = tuple(feature_groups["feature"].astype(str))
    _require(len(feature_names) == 193, "ML-9D feature-group census changed")
    _require(len(set(feature_names)) == 193, "duplicate ML-9D grouped feature")

    outcome_inputs = preregistration["outcome_blind_inputs"]
    features = pd.read_csv(
        root / outcome_inputs["feature_table"]["path"], low_memory=False
    )
    panel = pd.read_csv(root / outcome_inputs["panel_of_record"]["path"])
    features["task_uuid"] = features["task_uuid"].astype(str)
    panel["task_uuid"] = panel["task_uuid"].astype(str)
    task_ids = tuple(panel["task_uuid"])
    raw = (
        features.set_index("task_uuid")
        .reindex(task_ids)[list(feature_names)]
        .apply(pd.to_numeric, errors="coerce")
    )
    transformed, parameters = coordinate_preprocessing(raw)
    expected_parameters = pd.read_csv(
        preflight / "feature_preprocessing.csv"
    ).set_index("feature")
    _require(
        list(expected_parameters.index.astype(str)) == list(feature_names),
        "ML-9D preprocessing feature order changed",
    )
    for column in parameters.columns:
        expected = pd.to_numeric(
            expected_parameters[column], errors="coerce"
        ).to_numpy()
        observed = pd.to_numeric(parameters[column], errors="coerce").to_numpy()
        _require(
            np.allclose(observed, expected, rtol=0.0, atol=1e-14, equal_nan=True),
            f"ML-9D preprocessing parameter changed: {column}",
        )

    baseline_mask = _bool_series(feature_groups["baseline_component"], "baseline")
    baseline_indices = np.flatnonzero(baseline_mask)
    _require(len(baseline_indices) == 8, "ML-9D baseline feature count changed")
    additions = preregistration["prespecified_contrasts"]["additions"]
    contrasts: list[dict[str, Any]] = []
    for order, addition in enumerate(additions, start=1):
        contrast_id = str(addition["id"])
        rows = feature_groups.loc[feature_groups["contrast_id"] == contrast_id]
        _require(not rows.empty, f"missing ML-9D contrast group: {contrast_id}")
        _require(rows["group_id"].nunique() == 1, "ML-9D contrast spans groups")
        indices = np.array(
            [feature_names.index(name) for name in rows["feature"].astype(str)],
            dtype=int,
        )
        _require(
            not np.intersect1d(indices, baseline_indices).size,
            f"ML-9D contrast overlaps baseline: {contrast_id}",
        )
        contrasts.append(
            {
                "order": order,
                "contrast_id": contrast_id,
                "anchor": str(addition["anchor"]),
                "group_id": str(rows["group_id"].iloc[0]),
                "group_name": str(rows["group_name"].iloc[0]),
                "indices": indices,
            }
        )

    primary_spec = preregistration["target_inputs"]["primary"]
    primary = pd.read_csv(root / str(primary_spec["path"]))
    primary["task_uuid"] = primary["task_uuid"].astype(str)
    _require(primary["task_uuid"].is_unique, "duplicate ML-9D primary task")
    primary = primary.set_index("task_uuid").reindex(task_ids)
    _require(primary.index.notna().all(), "missing ML-9D primary task")
    primary_target = pd.to_numeric(
        primary["binary_difficulty_mean"], errors="coerce"
    ).to_numpy(dtype=float)
    _require(np.isfinite(primary_target).all(), "non-finite ML-9D primary target")

    canonical_families = primary["canonical_family"].astype(str).to_numpy()
    canonical_payload = _read_json(root / outcome_inputs["canonical_families"]["path"])
    canonical_map = {
        str(row["task_uuid"]): str(row["canonical_family_recommended"])
        for row in canonical_payload["tasks"]
    }
    expected_families = np.array([canonical_map[task] for task in task_ids])
    _require(
        np.array_equal(canonical_families, expected_families),
        "ML-9D primary canonical families changed",
    )

    secondary_spec = preregistration["target_inputs"]["secondary"]
    labels = pd.read_csv(root / str(secondary_spec["path"]))
    labels["task_uuid"] = labels["task_uuid"].astype(str)
    labels = labels.loc[
        np.isclose(
            pd.to_numeric(labels["threshold_factor"], errors="coerce"),
            float(secondary_spec["threshold_factor"]),
        )
        & labels["target"].astype(str).isin(FAMILY_TARGETS)
    ].copy()
    _require(
        len(labels) == len(task_ids) * len(FAMILY_TARGETS), "wrong ML-9D label census"
    )
    _require(
        not labels.duplicated(["task_uuid", "target"]).any(),
        "duplicate ML-9D secondary label",
    )
    binary_targets: dict[str, np.ndarray] = {}
    for family in FAMILY_TARGETS:
        rows = labels.loc[labels["target"].astype(str) == family].set_index("task_uuid")
        rows = rows.reindex(task_ids)
        binary_targets[family] = _bool_series(rows["solvable"], family)

    return PreparedInference(
        task_ids=task_ids,
        canonical_families=canonical_families,
        features=transformed.loc[:, list(feature_names)].to_numpy(dtype=float),
        feature_names=feature_names,
        baseline_indices=baseline_indices,
        contrasts=tuple(contrasts),
        primary_target=primary_target,
        binary_targets=binary_targets,
        gate_evidence=gate_evidence,
    )


def _continuous_folds(groups: np.ndarray, folds: int) -> np.ndarray:
    assignment = np.full(len(groups), -1, dtype=int)
    splitter = GroupKFold(n_splits=folds)
    for fold, (_, test) in enumerate(
        splitter.split(np.zeros(len(groups)), groups=groups)
    ):
        assignment[test] = fold
    _require(bool((assignment >= 0).all()), "incomplete ML-9D continuous folds")
    return assignment


def _binary_folds(
    y: np.ndarray, groups: np.ndarray, folds: int, seed: int
) -> tuple[np.ndarray, bool]:
    assignment = np.full(len(groups), -1, dtype=int)
    splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    try:
        splits = list(splitter.split(np.zeros(len(groups)), y, groups))
    except ValueError:
        return assignment, False
    gradeable = True
    for fold, (train, test) in enumerate(splits):
        assignment[test] = fold
        if len(np.unique(y[train])) != 2 or len(np.unique(y[test])) != 2:
            gradeable = False
    if not bool((assignment >= 0).all()):
        gradeable = False
    return assignment, gradeable


def _estimator(kind: str, name: str, settings: Mapping[str, Any]):
    common = {
        "n_estimators": int(settings["n_estimators"]),
        "max_features": settings["max_features"],
        "min_samples_leaf": int(settings["min_samples_leaf"]),
        "n_jobs": int(settings["n_jobs"]),
        "random_state": int(settings["random_state"]),
    }
    if kind == "continuous":
        cls = RandomForestRegressor if name == "random_forest" else ExtraTreesRegressor
        return cls(**common)
    common["class_weight"] = settings["class_weight"]
    cls = RandomForestClassifier if name == "random_forest" else ExtraTreesClassifier
    return cls(**common)


def _fit_oof(
    x: np.ndarray,
    y: np.ndarray,
    feature_indices: np.ndarray,
    folds: np.ndarray,
    kind: str,
    estimator_name: str,
    settings: Mapping[str, Any],
) -> np.ndarray:
    prediction = np.full(len(y), np.nan, dtype=float)
    for fold in sorted(set(folds)):
        train = np.flatnonzero(folds != fold)
        test = np.flatnonzero(folds == fold)
        model = _estimator(kind, estimator_name, settings)
        model.fit(x[np.ix_(train, feature_indices)], y[train])
        if kind == "continuous":
            prediction[test] = model.predict(x[np.ix_(test, feature_indices)])
        else:
            class_index = list(model.classes_).index(True)
            prediction[test] = model.predict_proba(x[np.ix_(test, feature_indices)])[
                :, class_index
            ]
    _require(np.isfinite(prediction).all(), "non-finite ML-9D OOF prediction")
    return prediction


def fit_comparisons(
    prepared: PreparedInference, preregistration: Mapping[str, Any]
) -> tuple[list[FittedComparison], list[dict[str, Any]]]:
    inference = preregistration["inference"]
    fold_count = int(inference["folds"])
    continuous_folds = _continuous_folds(prepared.canonical_families, fold_count)
    binary_fold_map = {
        family: _binary_folds(
            target,
            prepared.canonical_families,
            fold_count,
            int(inference["secondary_estimator"]["random_state"]),
        )
        for family, target in prepared.binary_targets.items()
    }
    fold_rows: list[dict[str, Any]] = []
    for target_kind, target, assignments, gradeable in [
        ("continuous", "task_difficulty", continuous_folds, True),
        *[
            ("binary", family, binary_fold_map[family][0], binary_fold_map[family][1])
            for family in FAMILY_TARGETS
        ],
    ]:
        for index, task_id in enumerate(prepared.task_ids):
            fold_rows.append(
                {
                    "target_kind": target_kind,
                    "target": target,
                    "task_uuid": task_id,
                    "canonical_family": prepared.canonical_families[index],
                    "fold": None if assignments[index] < 0 else int(assignments[index]),
                    "target_gradeable": gradeable,
                    "output_kind": "prespecified_cross_validation_assignment",
                }
            )

    comparisons: list[FittedComparison] = []
    targets: list[tuple[str, str, np.ndarray, np.ndarray, bool]] = [
        (
            "continuous",
            "task_difficulty",
            prepared.primary_target,
            continuous_folds,
            True,
        )
    ]
    targets.extend(
        (
            "binary",
            family,
            prepared.binary_targets[family],
            binary_fold_map[family][0],
            binary_fold_map[family][1],
        )
        for family in FAMILY_TARGETS
    )
    for target_kind, target_name, observed, folds, target_gradeable in targets:
        settings = inference[
            (
                "primary_estimator"
                if target_kind == "continuous"
                else "secondary_estimator"
            )
        ]
        for contrast in prepared.contrasts:
            augmented_indices = np.unique(
                np.concatenate([prepared.baseline_indices, contrast["indices"]])
            )
            for estimator_name in ESTIMATOR_ORDER:
                if not target_gradeable:
                    comparisons.append(
                        FittedComparison(
                            target_kind,
                            target_name,
                            contrast["contrast_id"],
                            contrast["group_id"],
                            contrast["group_name"],
                            contrast["anchor"],
                            estimator_name,
                            len(prepared.baseline_indices),
                            len(contrast["indices"]),
                            observed,
                            None,
                            None,
                            folds,
                            False,
                            "non_gradeable_degenerate_binary_fold",
                        )
                    )
                    continue
                baseline_prediction = _fit_oof(
                    prepared.features,
                    observed,
                    prepared.baseline_indices,
                    folds,
                    target_kind,
                    estimator_name,
                    settings,
                )
                augmented_prediction = _fit_oof(
                    prepared.features,
                    observed,
                    augmented_indices,
                    folds,
                    target_kind,
                    estimator_name,
                    settings,
                )
                comparisons.append(
                    FittedComparison(
                        target_kind,
                        target_name,
                        contrast["contrast_id"],
                        contrast["group_id"],
                        contrast["group_name"],
                        contrast["anchor"],
                        estimator_name,
                        len(prepared.baseline_indices),
                        len(contrast["indices"]),
                        observed,
                        baseline_prediction,
                        augmented_prediction,
                        folds,
                        True,
                        "estimated_internal_oof_comparison",
                    )
                )
    return comparisons, fold_rows


def _metric(kind: str, observed: np.ndarray, prediction: np.ndarray) -> float:
    if kind == "continuous":
        return float(r2_score(observed, prediction))
    return float(roc_auc_score(observed, prediction))


def _bootstrap_indices(groups: np.ndarray, draws: int, seed: int) -> list[np.ndarray]:
    unique = np.array(sorted(set(groups.astype(str))))
    members = {group: np.flatnonzero(groups == group) for group in unique}
    rng = np.random.default_rng(seed)
    output = []
    for _ in range(draws):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        output.append(np.concatenate([members[group] for group in sampled]))
    return output


def _score_comparisons(
    comparisons: Sequence[FittedComparison],
    groups: np.ndarray,
    contract: Mapping[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[tuple[str, str, str, str], np.ndarray],
]:
    execution = contract["execution"]
    draws = _bootstrap_indices(
        groups, int(execution["bootstrap_draws"]), int(execution["bootstrap_seed"])
    )
    estimate_rows: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    deltas_by_key: dict[tuple[str, str, str, str], np.ndarray] = {}
    for comparison in comparisons:
        key = (
            comparison.target_kind,
            comparison.target,
            comparison.estimator,
            comparison.contrast_id,
        )
        if not comparison.gradeable:
            deltas_by_key[key] = np.full(len(draws), np.nan)
            estimate_rows.append(
                {
                    "target_kind": comparison.target_kind,
                    "target": comparison.target,
                    "contrast_id": comparison.contrast_id,
                    "contrast_group_id": comparison.contrast_group_id,
                    "contrast_group_name": comparison.contrast_group_name,
                    "contrast_anchor": comparison.contrast_anchor,
                    "estimator": comparison.estimator,
                    "baseline_feature_count": comparison.baseline_feature_count,
                    "added_feature_count": comparison.added_feature_count,
                    "augmented_feature_count": comparison.baseline_feature_count
                    + comparison.added_feature_count,
                    "tasks": len(comparison.observed),
                    "canonical_families": len(set(groups)),
                    "gradeable": False,
                    "status": comparison.status,
                    "output_kind": "cross_fitted_estimate",
                    "baseline_score": None,
                    "augmented_score": None,
                    "delta_score": None,
                    "bootstrap_gradeable_draws": 0,
                    "bootstrap_ci_2_5pct": None,
                    "bootstrap_ci_97_5pct": None,
                    "selection_frequency": None,
                }
            )
            continue
        assert comparison.baseline_prediction is not None
        assert comparison.augmented_prediction is not None
        baseline_score = _metric(
            comparison.target_kind, comparison.observed, comparison.baseline_prediction
        )
        augmented_score = _metric(
            comparison.target_kind, comparison.observed, comparison.augmented_prediction
        )
        delta_values = np.full(len(draws), np.nan)
        for replicate, indices in enumerate(draws):
            observed = comparison.observed[indices]
            gradeable = (
                comparison.target_kind == "continuous" or len(np.unique(observed)) == 2
            )
            if gradeable:
                baseline = _metric(
                    comparison.target_kind,
                    observed,
                    comparison.baseline_prediction[indices],
                )
                augmented = _metric(
                    comparison.target_kind,
                    observed,
                    comparison.augmented_prediction[indices],
                )
                delta_values[replicate] = augmented - baseline
            bootstrap_rows.append(
                {
                    "target_kind": comparison.target_kind,
                    "target": comparison.target,
                    "contrast_id": comparison.contrast_id,
                    "estimator": comparison.estimator,
                    "replicate": replicate,
                    "gradeable": gradeable,
                    "baseline_score": None if not gradeable else baseline,
                    "augmented_score": None if not gradeable else augmented,
                    "delta_score": None if not gradeable else augmented - baseline,
                    "output_kind": "family_block_bootstrap_estimate",
                }
            )
        deltas_by_key[key] = delta_values
        finite = delta_values[np.isfinite(delta_values)]
        interval_gradeable = len(finite) >= 2
        estimate_rows.append(
            {
                "target_kind": comparison.target_kind,
                "target": comparison.target,
                "contrast_id": comparison.contrast_id,
                "contrast_group_id": comparison.contrast_group_id,
                "contrast_group_name": comparison.contrast_group_name,
                "contrast_anchor": comparison.contrast_anchor,
                "estimator": comparison.estimator,
                "baseline_feature_count": comparison.baseline_feature_count,
                "added_feature_count": comparison.added_feature_count,
                "augmented_feature_count": comparison.baseline_feature_count
                + comparison.added_feature_count,
                "tasks": len(comparison.observed),
                "canonical_families": len(set(groups)),
                "gradeable": True,
                "status": comparison.status,
                "output_kind": "cross_fitted_estimate",
                "baseline_score": baseline_score,
                "augmented_score": augmented_score,
                "delta_score": augmented_score - baseline_score,
                "bootstrap_gradeable_draws": len(finite),
                "bootstrap_ci_2_5pct": (
                    float(np.percentile(finite, 2.5)) if interval_gradeable else None
                ),
                "bootstrap_ci_97_5pct": (
                    float(np.percentile(finite, 97.5)) if interval_gradeable else None
                ),
                "selection_frequency": (
                    float(np.mean(finite > 0.0)) if interval_gradeable else None
                ),
            }
        )
    return estimate_rows, bootstrap_rows, deltas_by_key


def _randomization_tests(
    comparisons: Sequence[FittedComparison],
    groups: np.ndarray,
    contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    execution = contract["execution"]
    draws = int(execution["randomization_draws"])
    unique = np.array(sorted(set(groups.astype(str))))
    group_index = {group: index for index, group in enumerate(unique)}
    row_groups = np.array([group_index[group] for group in groups])
    rng = np.random.default_rng(int(execution["randomization_seed"]))
    swap_masks = rng.integers(0, 2, size=(draws, len(unique)), dtype=np.int8).astype(
        bool
    )
    rows: list[dict[str, Any]] = []
    for comparison in comparisons:
        if comparison.estimator != "random_forest":
            continue
        base_row = {
            "target_kind": comparison.target_kind,
            "target": comparison.target,
            "contrast_id": comparison.contrast_id,
            "estimator": comparison.estimator,
            "draws": draws,
            "seed": int(execution["randomization_seed"]),
            "output_kind": "paired_family_randomization_estimate",
        }
        if not comparison.gradeable:
            rows.append(
                {
                    **base_row,
                    "gradeable": False,
                    "observed_delta": None,
                    "randomized_at_least_observed": None,
                    "p_value_one_sided": None,
                }
            )
            continue
        assert comparison.baseline_prediction is not None
        assert comparison.augmented_prediction is not None
        observed_delta = _metric(
            comparison.target_kind,
            comparison.observed,
            comparison.augmented_prediction,
        ) - _metric(
            comparison.target_kind,
            comparison.observed,
            comparison.baseline_prediction,
        )
        count = 0
        for mask in swap_masks:
            swap = mask[row_groups]
            randomized_baseline = np.where(
                swap, comparison.augmented_prediction, comparison.baseline_prediction
            )
            randomized_augmented = np.where(
                swap, comparison.baseline_prediction, comparison.augmented_prediction
            )
            randomized_delta = _metric(
                comparison.target_kind, comparison.observed, randomized_augmented
            ) - _metric(
                comparison.target_kind, comparison.observed, randomized_baseline
            )
            count += int(randomized_delta >= observed_delta)
        rows.append(
            {
                **base_row,
                "gradeable": True,
                "observed_delta": observed_delta,
                "randomized_at_least_observed": count,
                "p_value_one_sided": (count + 1.0) / (draws + 1.0),
            }
        )
    return rows


def _benjamini_hochberg(p_values: Sequence[float]) -> np.ndarray:
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values, kind="stable")
    adjusted = np.empty(len(values), dtype=float)
    running = 1.0
    for reverse_rank in range(len(values) - 1, -1, -1):
        index = order[reverse_rank]
        rank = reverse_rank + 1
        running = min(running, values[index] * len(values) / rank)
        adjusted[index] = min(running, 1.0)
    return adjusted


def _multiplicity_rows(
    randomization_rows: Sequence[Mapping[str, Any]], q: float
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for family_name, target_kind in (
        ("five_primary_continuous_contrasts", "continuous"),
        ("twenty_secondary_binary_contrasts", "binary"),
    ):
        members = [
            row for row in randomization_rows if row["target_kind"] == target_kind
        ]
        adjusted = _benjamini_hochberg(
            [
                float(row["p_value_one_sided"]) if row["gradeable"] else 1.0
                for row in members
            ]
        )
        adjusted_by_key = {
            (row["target"], row["contrast_id"]): float(value)
            for row, value in zip(members, adjusted, strict=True)
            if row["gradeable"]
        }
        for row in members:
            adjusted_value = adjusted_by_key.get((row["target"], row["contrast_id"]))
            output.append(
                {
                    "multiplicity_family": family_name,
                    "target_kind": row["target_kind"],
                    "target": row["target"],
                    "contrast_id": row["contrast_id"],
                    "estimator": row["estimator"],
                    "gradeable": row["gradeable"],
                    "p_value_one_sided": row["p_value_one_sided"],
                    "p_value_bh": adjusted_value,
                    "q_threshold": q,
                    "output_kind": "multiplicity_adjusted_estimate",
                    "reject_zero_positive_importance": (
                        None if adjusted_value is None else adjusted_value <= q
                    ),
                }
            )
    return output


def _rank_concordance_rows(
    estimate_rows: Sequence[Mapping[str, Any]],
    deltas_by_key: Mapping[tuple[str, str, str, str], np.ndarray],
    contrasts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    contrast_order = [str(row["contrast_id"]) for row in contrasts]
    lookup = {
        (row["target_kind"], row["target"], row["estimator"], row["contrast_id"]): row
        for row in estimate_rows
    }
    target_estimators = sorted(
        {(row["target_kind"], row["target"], row["estimator"]) for row in estimate_rows}
    )
    rows: list[dict[str, Any]] = []
    for target_kind, target, estimator in target_estimators:
        full = np.array(
            [
                lookup[(target_kind, target, estimator, contrast)]["delta_score"]
                for contrast in contrast_order
            ],
            dtype=float,
        )
        arrays = [
            deltas_by_key[(target_kind, target, estimator, contrast)]
            for contrast in contrast_order
        ]
        for replicate in range(len(arrays[0])):
            sampled = np.array([array[replicate] for array in arrays], dtype=float)
            gradeable = bool(np.isfinite(full).all() and np.isfinite(sampled).all())
            concordance: float | None = None
            if gradeable:
                full_rank = rankdata(full, method="average")
                sampled_rank = rankdata(sampled, method="average")
                gradeable = bool(np.std(full_rank) > 0.0 and np.std(sampled_rank) > 0.0)
                if gradeable:
                    concordance = float(np.corrcoef(full_rank, sampled_rank)[0, 1])
            rows.append(
                {
                    "target_kind": target_kind,
                    "target": target,
                    "estimator": estimator,
                    "replicate": replicate,
                    "gradeable": gradeable,
                    "spearman_rank_concordance": concordance,
                    "output_kind": "bootstrap_stability_estimate",
                }
            )
    return rows


def _model_reliance_rows(
    estimate_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in estimate_rows:
        grouped.setdefault(
            (str(row["target_kind"]), str(row["target"]), str(row["contrast_id"])),
            [],
        ).append(row)
    rows = []
    for (target_kind, target, contrast_id), members in sorted(grouped.items()):
        by_estimator = {str(row["estimator"]): row for row in members}
        values = [
            float(row["delta_score"])
            for row in members
            if row["gradeable"] and row["delta_score"] is not None
        ]
        rows.append(
            {
                "target_kind": target_kind,
                "target": target,
                "contrast_id": contrast_id,
                "gradeable": len(values) == 2,
                "random_forest_delta": by_estimator["random_forest"]["delta_score"],
                "extra_trees_delta": by_estimator["extra_trees"]["delta_score"],
                "model_reliance_min_delta": min(values) if len(values) == 2 else None,
                "model_reliance_max_delta": max(values) if len(values) == 2 else None,
                "output_kind": "model_class_reliance_range_estimate",
            }
        )
    return rows


def _prediction_rows(
    comparisons: Sequence[FittedComparison], prepared: PreparedInference
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for comparison in comparisons:
        if not comparison.gradeable:
            continue
        assert comparison.baseline_prediction is not None
        assert comparison.augmented_prediction is not None
        for index, task_id in enumerate(prepared.task_ids):
            rows.append(
                {
                    "target_kind": comparison.target_kind,
                    "target": comparison.target,
                    "contrast_id": comparison.contrast_id,
                    "estimator": comparison.estimator,
                    "task_uuid": task_id,
                    "canonical_family": prepared.canonical_families[index],
                    "fold": int(comparison.folds[index]),
                    "observed": float(comparison.observed[index]),
                    "baseline_prediction": comparison.baseline_prediction[index],
                    "augmented_prediction": comparison.augmented_prediction[index],
                    "output_kind": "fixed_out_of_fold_estimate",
                }
            )
    return rows


def _task_target_rows(prepared: PreparedInference) -> list[dict[str, Any]]:
    return [
        {
            "task_uuid": task_id,
            "canonical_family": prepared.canonical_families[index],
            "binary_difficulty_posterior_mean": prepared.primary_target[index],
            **{
                f"solvable_1x_{family}": prepared.binary_targets[family][index]
                for family in FAMILY_TARGETS
            },
            "primary_output_kind": "posterior_estimate",
            "secondary_output_kind": "derived_observed_label",
        }
        for index, task_id in enumerate(prepared.task_ids)
    ]


def _write_csv_outputs(
    output_directory: Path,
    prepared: PreparedInference,
    comparisons: Sequence[FittedComparison],
    fold_rows: Sequence[Mapping[str, Any]],
    estimate_rows: Sequence[Mapping[str, Any]],
    bootstrap_rows: Sequence[Mapping[str, Any]],
    randomization_rows: Sequence[Mapping[str, Any]],
    multiplicity_rows: Sequence[Mapping[str, Any]],
    rank_rows: Sequence[Mapping[str, Any]],
    reliance_rows: Sequence[Mapping[str, Any]],
) -> None:
    outputs: list[tuple[str, Sequence[Mapping[str, Any]]]] = [
        ("task_targets.csv", _task_target_rows(prepared)),
        ("fold_assignments.csv", fold_rows),
        ("contrast_predictions.csv", _prediction_rows(comparisons, prepared)),
        ("contrast_estimates.csv", estimate_rows),
        ("bootstrap_deltas.csv", bootstrap_rows),
        ("randomization_tests.csv", randomization_rows),
        ("multiplicity_results.csv", multiplicity_rows),
        ("rank_concordance.csv", rank_rows),
        ("model_reliance_ranges.csv", reliance_rows),
    ]
    for name, rows in outputs:
        _require(bool(rows), f"empty ML-9D output: {name}")
        stable_csv_dump(rows, list(rows[0]), output_directory / name)


def run_grouped_inference(
    root: Path,
    preregistration_path: Path,
    execution_contract_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Run the fully frozen ML-9D target-dependent analysis."""

    preregistration = _read_json(preregistration_path)
    contract = _read_json(execution_contract_path)
    prepared = prepare_inference(root, preregistration_path, execution_contract_path)
    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.mkdir(parents=True)

    print("ML9D_FIT_START", flush=True)
    comparisons, fold_rows = fit_comparisons(prepared, preregistration)
    print(f"ML9D_FIT_DONE comparisons={len(comparisons)}", flush=True)
    estimate_rows, bootstrap_rows, deltas_by_key = _score_comparisons(
        comparisons, prepared.canonical_families, contract
    )
    print(f"ML9D_BOOTSTRAP_DONE rows={len(bootstrap_rows)}", flush=True)
    randomization_rows = _randomization_tests(
        comparisons, prepared.canonical_families, contract
    )
    multiplicity_rows = _multiplicity_rows(
        randomization_rows, float(preregistration["inference"]["multiplicity"]["q"])
    )
    rank_rows = _rank_concordance_rows(estimate_rows, deltas_by_key, prepared.contrasts)
    reliance_rows = _model_reliance_rows(estimate_rows)
    _write_csv_outputs(
        output_directory,
        prepared,
        comparisons,
        fold_rows,
        estimate_rows,
        bootstrap_rows,
        randomization_rows,
        multiplicity_rows,
        rank_rows,
        reliance_rows,
    )
    stable_json_dump(
        prepared.gate_evidence, output_directory / "target_gate_evidence.json"
    )

    environment = {
        "artifact_id": "ml9d_grouped_inference_environment_v1",
        "python": platform.python_version(),
        "numpy": importlib_metadata.version("numpy"),
        "pandas": importlib_metadata.version("pandas"),
        "scipy": importlib_metadata.version("scipy"),
        "scikit_learn": importlib_metadata.version("scikit-learn"),
        "python_hash_seed": int(contract["execution"]["python_hash_seed"]),
        "thread_limits": int(contract["execution"]["thread_limits"]),
    }
    stable_json_dump(environment, output_directory / "environment.json")

    primary_rows = [
        row
        for row in estimate_rows
        if row["target_kind"] == "continuous" and row["estimator"] == "random_forest"
    ]
    secondary_rows = [
        row
        for row in estimate_rows
        if row["target_kind"] == "binary" and row["estimator"] == "random_forest"
    ]
    rejected = [
        row
        for row in multiplicity_rows
        if row["reject_zero_positive_importance"] is True
    ]
    rank_values = [
        float(row["spearman_rank_concordance"]) for row in rank_rows if row["gradeable"]
    ]
    report = {
        "artifact_id": "ml9d_grouped_inference_report_v1",
        "status": "complete_internal_descriptive_inference",
        "target_gate_status": prepared.gate_evidence["status"],
        "scientific_targets_consumed": True,
        "model_fitted": True,
        "panel_tasks": len(prepared.task_ids),
        "canonical_family_blocks": len(set(prepared.canonical_families)),
        "modeling_features": len(prepared.feature_names),
        "baseline_features": len(prepared.baseline_indices),
        "prespecified_contrasts": len(prepared.contrasts),
        "continuous_gradeable_contrasts": sum(row["gradeable"] for row in primary_rows),
        "binary_gradeable_contrasts": sum(row["gradeable"] for row in secondary_rows),
        "bh_rejections_primary": sum(
            row["reject_zero_positive_importance"] is True
            for row in rejected
            if row["target_kind"] == "continuous"
        ),
        "bh_rejections_secondary": sum(
            row["reject_zero_positive_importance"] is True
            for row in rejected
            if row["target_kind"] == "binary"
        ),
        "rank_concordance_gradeable_draws": len(rank_values),
        "rank_concordance_median": (
            float(np.median(rank_values)) if rank_values else None
        ),
        "bootstrap_replicates": int(contract["execution"]["bootstrap_draws"]),
        "randomization_draws": int(contract["execution"]["randomization_draws"]),
        "reporting_scope": "descriptive_internal_no_causal_or_validated_predictor_claim",
        "ml9c_posterior_uncertainty_caveat": (
            "The primary response is an estimated posterior mean; ML-9D conditions on "
            "that estimate and does not propagate the full ML-9C posterior."
        ),
        "new_solver_runs": False,
        "stored_targets_or_labels_mutated": False,
    }
    stable_json_dump(report, output_directory / "report.json")

    markdown = [
        "# ML-9D grouped feature inference report",
        "",
        "Status: complete internal descriptive inference.",
        "",
        f"The fixed panel contains {report['panel_tasks']} tasks in "
        f"{report['canonical_family_blocks']} canonical-family blocks. The "
        f"{report['baseline_features']}-feature size/sector baseline was compared "
        f"with each of {report['prespecified_contrasts']} frozen correlation groups.",
        "",
        "All estimates are from fixed out-of-fold predictions. Intervals use the "
        "frozen whole-family bootstrap, zero-importance tests use paired whole-family "
        "prediction swaps, and multiplicity is controlled separately for the five "
        "continuous and twenty binary prespecified tests.",
        "",
        f"Benjamini-Hochberg rejections: {report['bh_rejections_primary']} primary "
        f"and {report['bh_rejections_secondary']} secondary. These are internal "
        "descriptive results, not causal effects or validated predictor claims.",
        "",
        "The primary response is an ML-9C posterior-mean estimate. This analysis "
        "conditions on that estimate and does not propagate the full posterior "
        "uncertainty. Model-reliance ranges and rank-concordance draws are reported; "
        "no single-rank claim is authorized.",
        "",
        "No solver was run and no stored target or label was changed.",
        "",
    ]
    (output_directory / "REPORT.md").write_text("\n".join(markdown), encoding="utf-8")

    required = set(contract["outputs"]["required_files"])
    produced = {path.name for path in output_directory.iterdir() if path.is_file()}
    _require(
        produced == required - {"artifact_manifest.json"},
        "ML-9D output contract changed before manifest",
    )
    files = [
        {"path": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(output_directory.iterdir())
        if path.is_file()
    ]
    manifest = {
        "artifact_id": "ml9d_grouped_inference_manifest_v1",
        "status": "complete_internal_descriptive_inference",
        "preregistration_sha256": sha256_file(preregistration_path),
        "execution_contract_sha256": sha256_file(execution_contract_path),
        "target_gate_status": prepared.gate_evidence["status"],
        "scientific_targets_consumed": True,
        "model_fitted": True,
        "promotion_eligible_after_two_run_identity": True,
        "new_solver_runs": False,
        "files": files,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    _require(
        {path.name for path in output_directory.iterdir() if path.is_file()}
        == required,
        "ML-9D final output contract changed",
    )
    return report
