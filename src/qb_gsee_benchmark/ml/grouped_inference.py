"""Outcome-blind correlation groups for ML-9D grouped inference."""

from __future__ import annotations

import json
import platform
from collections import Counter
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.g50_solver_families import derive_feature_policy
from qb_gsee_benchmark.ml.instance_space import coordinate_preprocessing


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_path(
    root: Path, specification: Mapping[str, Any], label: str
) -> tuple[Path, str]:
    path = root / str(specification["path"])
    _require(path.is_file(), f"missing ML-9D input {label}: {path}")
    digest = sha256_file(path)
    _require(
        digest == str(specification["sha256"]),
        f"changed ML-9D input {label}: {path}",
    )
    return path, digest


def _slug(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)


def _correlation_distance(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    _require(values.ndim == 2, "ML-9D feature matrix must be two-dimensional")
    active = np.std(values, axis=0, ddof=0) > 0.0
    correlations = np.zeros((values.shape[1], values.shape[1]), dtype=float)
    if int(active.sum()) > 1:
        correlations[np.ix_(active, active)] = np.corrcoef(
            values[:, active], rowvar=False
        )
    correlations = np.nan_to_num(correlations, nan=0.0, posinf=0.0, neginf=0.0)
    correlations = (correlations + correlations.T) / 2.0
    np.fill_diagonal(correlations, 1.0)
    distances = np.clip(1.0 - np.abs(correlations), 0.0, 1.0)
    distances = (distances + distances.T) / 2.0
    np.fill_diagonal(distances, 0.0)
    return correlations, distances


def _stable_clusters(
    columns: list[str], raw_labels: np.ndarray
) -> tuple[list[list[str]], dict[str, str]]:
    clusters: dict[int, list[str]] = {}
    for column, label in zip(columns, raw_labels, strict=True):
        clusters.setdefault(int(label), []).append(column)
    ordered = sorted(
        (sorted(members) for members in clusters.values()),
        key=lambda members: (-len(members), members[0]),
    )
    feature_to_group: dict[str, str] = {}
    for index, members in enumerate(ordered, start=1):
        group_id = f"G{index:02d}"
        for member in members:
            feature_to_group[member] = group_id
    return ordered, feature_to_group


def run_outcome_blind_group_preflight(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Build frozen ML-9D feature groups without accessing any target."""

    preregistration = _read_json(preregistration_path)
    _require(
        preregistration.get("artifact_id")
        == "ml9d_grouped_inference_preregistration_v1",
        "wrong ML-9D preregistration",
    )
    _require(
        preregistration.get("frozen_before_target_fit") is True,
        "ML-9D preregistration is not frozen",
    )

    order = preregistration["order"]
    order_hashes: dict[str, str] = {}
    for label, path_key, hash_key in (
        ("ml_goals", "ml_goals_external_path", "ml_goals_sha256"),
        (
            "pi_literature_memo",
            "pi_literature_memo_external_path",
            "pi_literature_memo_sha256",
        ),
    ):
        path = Path(str(order[path_key]))
        _require(path.is_file(), f"missing ML-9D order source: {path}")
        digest = sha256_file(path)
        _require(digest == str(order[hash_key]), f"changed ML-9D order: {path}")
        order_hashes[label] = digest

    input_paths: dict[str, Path] = {}
    input_hashes: dict[str, str] = {}
    for label, specification in sorted(preregistration["outcome_blind_inputs"].items()):
        path, digest = _verify_path(root, specification, label)
        input_paths[label] = path
        input_hashes[label] = digest

    metadata = pd.read_csv(input_paths["feature_metadata"])
    identifiers = _read_json(input_paths["identifier_screen"])["identifier_columns"]
    policy = derive_feature_policy(metadata, identifiers)
    columns = list(policy["selected"])
    _require(len(columns) == 193, "ML-9D modeling feature count changed")
    _require(len(policy["jw"]) == 17, "ML-9D JW feature count changed")

    census = pd.read_csv(input_paths["ml9a_feature_census"])
    _require(len(census) == 193, "ML-9D feature census count changed")
    _require(
        set(census["column"].astype(str)) == set(columns),
        "ML-9D feature census membership changed",
    )
    census = census.set_index("column").reindex(columns)

    features = pd.read_csv(input_paths["feature_table"], low_memory=False)
    features["task_uuid"] = features["task_uuid"].astype(str)
    _require(
        len(features) == 718 and features["task_uuid"].is_unique,
        "ML-9D feature-table census changed",
    )
    panel = pd.read_csv(input_paths["panel_of_record"])
    panel["task_uuid"] = panel["task_uuid"].astype(str)
    _require(
        len(panel) == 96 and panel["task_uuid"].is_unique,
        "ML-9D panel census changed",
    )
    panel_values = (
        features.set_index("task_uuid")
        .reindex(panel["task_uuid"])[columns]
        .apply(pd.to_numeric, errors="coerce")
    )
    transformed, parameters = coordinate_preprocessing(panel_values)

    canonical_payload = _read_json(input_paths["canonical_families"])
    canonical_map = {
        str(row["task_uuid"]): str(row["canonical_family_recommended"])
        for row in canonical_payload["tasks"]
    }
    panel_families = [canonical_map[task] for task in panel["task_uuid"]]
    _require(
        len(set(panel_families))
        == int(preregistration["population"]["expected_canonical_family_blocks"]),
        "ML-9D panel canonical-family count changed",
    )

    correlations, distances = _correlation_distance(transformed.to_numpy(float))
    grouping = preregistration["correlation_grouping"]
    hierarchy = linkage(
        squareform(distances, checks=True),
        method=str(grouping["linkage"]),
        optimal_ordering=bool(grouping["optimal_leaf_ordering"]),
    )
    raw_labels = fcluster(
        hierarchy,
        t=float(grouping["fixed_distance_cut"]),
        criterion="distance",
    )
    clusters, feature_to_group = _stable_clusters(columns, raw_labels)

    group_members = {
        f"G{index:02d}": members for index, members in enumerate(clusters, start=1)
    }
    baseline_anchors = list(
        preregistration["prespecified_contrasts"]["baseline"]["anchors"]
    )
    baseline_groups = sorted({feature_to_group[anchor] for anchor in baseline_anchors})
    _require(len(baseline_groups) >= 1, "ML-9D baseline has no correlation group")

    additions = preregistration["prespecified_contrasts"]["additions"]
    contrast_by_group: dict[str, Mapping[str, Any]] = {}
    for contrast in additions:
        anchor = str(contrast["anchor"])
        _require(anchor in feature_to_group, f"missing ML-9D contrast anchor: {anchor}")
        group_id = feature_to_group[anchor]
        _require(
            group_id not in baseline_groups,
            f"ML-9D contrast anchor joined baseline: {anchor}",
        )
        _require(
            group_id not in contrast_by_group,
            f"ML-9D contrast anchors share a cluster: {anchor}",
        )
        contrast_by_group[group_id] = contrast

    group_names: dict[str, str] = {}
    group_summaries: list[dict[str, Any]] = []
    baseline_part = {
        group_id: index for index, group_id in enumerate(baseline_groups, 1)
    }
    correlation_index = {column: index for index, column in enumerate(columns)}
    for group_id, members in group_members.items():
        block_counts = Counter(
            str(census.loc[column, "logical_block"]) for column in members
        )
        largest = max(block_counts.values())
        dominant = sorted(
            block for block, count in block_counts.items() if count == largest
        )
        if group_id in baseline_part:
            group_name = (
                "size_sector_complexity_baseline_part_" f"{baseline_part[group_id]}"
            )
        elif group_id in contrast_by_group:
            anchor = str(contrast_by_group[group_id]["anchor"])
            group_name = str(grouping["anchor_name_overrides"][anchor])
        else:
            group_name = (
                f"{group_id.lower()}__{'_'.join(map(_slug, dominant))}__"
                f"{_slug(members[0])}"
            )
        _require(group_name not in group_names.values(), "duplicate ML-9D group name")
        group_names[group_id] = group_name

        indices = [correlation_index[column] for column in members]
        if len(indices) > 1:
            within = np.abs(correlations[np.ix_(indices, indices)])
            upper = within[np.triu_indices(len(indices), k=1)]
            mean_within = float(np.mean(upper))
            minimum_within = float(np.min(upper))
        else:
            mean_within = 1.0
            minimum_within = 1.0
        contrast = contrast_by_group.get(group_id)
        group_summaries.append(
            {
                "group_id": group_id,
                "group_name": group_name,
                "feature_count": len(members),
                "dominant_logical_blocks": ";".join(dominant),
                "logical_block_counts": ";".join(
                    f"{block}:{count}" for block, count in sorted(block_counts.items())
                ),
                "member_columns": ";".join(members),
                "baseline_component": group_id in baseline_groups,
                "contrast_id": "" if contrast is None else str(contrast["id"]),
                "contrast_anchor": "" if contrast is None else str(contrast["anchor"]),
                "jw_feature_count": int(
                    sum(
                        str(census.loc[column, "jw_feature"]).lower() == "true"
                        for column in members
                    )
                ),
                "constant_feature_count": int(
                    sum(
                        bool(parameters.loc[column, "constant_after_completion"])
                        for column in members
                    )
                ),
                "mean_absolute_within_group_correlation": mean_within,
                "minimum_absolute_within_group_correlation": minimum_within,
            }
        )

    feature_rows: list[dict[str, Any]] = []
    for column in columns:
        group_id = feature_to_group[column]
        contrast = contrast_by_group.get(group_id)
        feature_rows.append(
            {
                "feature": column,
                "group_id": group_id,
                "group_name": group_names[group_id],
                "group_size": len(group_members[group_id]),
                "logical_block": str(census.loc[column, "logical_block"]),
                "jw_feature": str(census.loc[column, "jw_feature"]).lower() == "true",
                "panel_missing_fraction": float(
                    census.loc[column, "panel_missing_fraction"]
                ),
                "constant_after_completion": bool(
                    parameters.loc[column, "constant_after_completion"]
                ),
                "baseline_component": group_id in baseline_groups,
                "contrast_id": "" if contrast is None else str(contrast["id"]),
                "contrast_anchor": "" if contrast is None else str(contrast["anchor"]),
            }
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    stable_csv_dump(
        feature_rows,
        [
            "feature",
            "group_id",
            "group_name",
            "group_size",
            "logical_block",
            "jw_feature",
            "panel_missing_fraction",
            "constant_after_completion",
            "baseline_component",
            "contrast_id",
            "contrast_anchor",
        ],
        output_directory / "feature_groups.csv",
    )
    stable_csv_dump(
        group_summaries,
        [
            "group_id",
            "group_name",
            "feature_count",
            "dominant_logical_blocks",
            "logical_block_counts",
            "member_columns",
            "baseline_component",
            "contrast_id",
            "contrast_anchor",
            "jw_feature_count",
            "constant_feature_count",
            "mean_absolute_within_group_correlation",
            "minimum_absolute_within_group_correlation",
        ],
        output_directory / "group_summary.csv",
    )
    stable_csv_dump(
        [
            {
                "merge_step": step,
                "left_node": int(row[0]),
                "right_node": int(row[1]),
                "correlation_distance": float(row[2]),
                "merged_feature_count": int(row[3]),
            }
            for step, row in enumerate(hierarchy, start=1)
        ],
        [
            "merge_step",
            "left_node",
            "right_node",
            "correlation_distance",
            "merged_feature_count",
        ],
        output_directory / "linkage_matrix.csv",
    )
    stable_csv_dump(
        [
            {
                "feature": column,
                **{
                    other: float(correlations[row_index, column_index])
                    for column_index, other in enumerate(columns)
                },
            }
            for row_index, column in enumerate(columns)
        ],
        ["feature", *columns],
        output_directory / "correlation_matrix.csv",
    )
    preprocessing_rows = [
        {"feature": column, **parameters.loc[column].to_dict()} for column in columns
    ]
    stable_csv_dump(
        preprocessing_rows,
        ["feature", *list(parameters.columns)],
        output_directory / "feature_preprocessing.csv",
    )

    environment = {
        "artifact_id": "ml9d_outcome_blind_environment_v1",
        "python": platform.python_version(),
        "numpy": importlib_metadata.version("numpy"),
        "pandas": importlib_metadata.version("pandas"),
        "scipy": importlib_metadata.version("scipy"),
        "target_packages_loaded": [],
    }
    stable_json_dump(environment, output_directory / "environment.json")

    selected_contrasts = [
        {
            "contrast_id": str(contrast["id"]),
            "anchor": str(contrast["anchor"]),
            "group_id": feature_to_group[str(contrast["anchor"])],
            "group_name": group_names[feature_to_group[str(contrast["anchor"])]],
            "feature_count": len(
                group_members[feature_to_group[str(contrast["anchor"])]]
            ),
        }
        for contrast in additions
    ]
    report = {
        "artifact_id": "ml9d_outcome_blind_group_preflight_v1",
        "status": "pass_outcome_blind_groups_frozen",
        "preregistration_sha256": sha256_file(preregistration_path),
        "scientific_targets_consumed": False,
        "primary_target_accessed": False,
        "secondary_targets_accessed": False,
        "model_fitted": False,
        "input_hashes": input_hashes,
        "order_hashes": order_hashes,
        "census": {
            "corpus_tasks": len(features),
            "panel_tasks": len(panel),
            "panel_canonical_task_families": len(set(panel_families)),
            "modeling_features": len(columns),
            "jw_features": len(policy["jw"]),
            "constant_after_completion": int(
                parameters["constant_after_completion"].sum()
            ),
            "correlation_groups": len(group_members),
            "baseline_groups": len(baseline_groups),
            "baseline_features": int(
                sum(len(group_members[group_id]) for group_id in baseline_groups)
            ),
            "prespecified_contrasts": len(selected_contrasts),
        },
        "grouping": {
            "distance": grouping["distance"],
            "linkage": grouping["linkage"],
            "fixed_distance_cut": grouping["fixed_distance_cut"],
            "group_size_descending": sorted(
                (len(members) for members in group_members.values()), reverse=True
            ),
        },
        "baseline": {
            "name": preregistration["prespecified_contrasts"]["baseline"]["id"],
            "anchors": baseline_anchors,
            "group_ids": baseline_groups,
            "group_names": [group_names[group_id] for group_id in baseline_groups],
        },
        "prespecified_contrasts": selected_contrasts,
        "target_gate": {
            "status": "held_before_target_access",
            "reason": "ML-9C promoted final_v1 handoff is required and was not inspected by this outcome-blind preflight.",
            "retained_raw_handoff_allowed": False,
        },
    }
    stable_json_dump(report, output_directory / "preflight_report.json")

    files = []
    for name in (
        "correlation_matrix.csv",
        "environment.json",
        "feature_groups.csv",
        "feature_preprocessing.csv",
        "group_summary.csv",
        "linkage_matrix.csv",
        "preflight_report.json",
    ):
        path = output_directory / name
        files.append(
            {"path": name, "sha256": sha256_file(path), "bytes": path.stat().st_size}
        )
    manifest = {
        "artifact_id": "ml9d_outcome_blind_group_manifest_v1",
        "status": "pass_outcome_blind_groups_frozen",
        "preregistration_sha256": sha256_file(preregistration_path),
        "scientific_targets_consumed": False,
        "model_fitted": False,
        "target_dependent_outputs_promoted": False,
        "files": files,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return report
