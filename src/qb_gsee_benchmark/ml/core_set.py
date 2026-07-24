"""Outcome-blind, block-aware core-set selection for ML-5 Phase A."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class BlockModel:
    """Whitened coordinates for one exact-applicability physics block."""

    name: str
    logical_block: str
    columns: tuple[str, ...]
    row_indices: np.ndarray
    coordinates: np.ndarray
    retained_components: int
    retained_variance_fraction: float
    dropped_constant_columns: tuple[str, ...]


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


def stable_csv_dump(
    rows: Sequence[Mapping[str, Any]], columns: Sequence[str], path: Path
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".17g")
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (int, np.integer)):
        return int(value)
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load_family_map(problem_instances: Path) -> dict[str, dict[str, str]]:
    """Load only task identity, broad family, and curation tier metadata."""
    tasks: dict[str, dict[str, str]] = {}
    for path in sorted(problem_instances.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        broad_family = path.parent.name
        for task in payload.get("tasks", []):
            task_uuid = str(task["task_uuid"])
            record = {
                "family": str(task.get("family") or broad_family),
                "tier": str(task.get("curation_tier") or "unspecified"),
            }
            if task_uuid in tasks and tasks[task_uuid] != record:
                raise ValueError(f"Conflicting family metadata for {task_uuid}")
            tasks[task_uuid] = record
    return tasks


def family_map_sha256(tasks: Mapping[str, Mapping[str, str]]) -> str:
    rows = [
        {
            "task_uuid": task_uuid,
            "family": str(record["family"]),
            "tier": str(record["tier"]),
        }
        for task_uuid, record in sorted(tasks.items())
    ]
    blob = (json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(blob).hexdigest()


def eligible_feature_columns(metadata: pd.DataFrame) -> list[str]:
    eligible = metadata["model_eligible"].astype(str).str.lower().eq("true")
    selected = metadata.loc[
        eligible
        & metadata["provenance_tier"].isin(["T0", "T1", "T2"])
        & ~metadata["role"].eq("audit-only")
        & metadata["implementation_status"].eq("current"),
        "column",
    ]
    return sorted(map(str, selected))


def _logical_block(column: str, metadata_row: Mapping[str, Any]) -> str:
    cost_class = str(metadata_row["cost_class"])
    protocol = str(metadata_row["protocol"])
    if column in {
        "max_vertex_degree",
        "min_vertex_degree",
        "mean_vertex_degree",
        "std_dev_vertex_degree",
        "max_weight",
        "mean_weight",
        "std_dev_weight",
        "mean_edge_order",
        "std_dev_edge_order",
        "number_of_terms",
        "pauli_terms_per_orbital_quartic",
        "mean_vertex_degree_per_orbital",
        "max_vertex_degree_per_orbital",
        "vertex_degree_coefficient_of_variation",
        "edge_order_coefficient_of_variation",
    }:
        return "jw_encoding"
    if cost_class == "header":
        return "size_dimension"
    if protocol == "MF-PROTO":
        return "mean_field_protocol"
    if column.startswith("fragment_inferred_"):
        return "fragmentation"
    if column in {
        "h1_offdiag_frobenius",
        "eri_self_repulsion_sum",
        "nonzero_integrals_1e_10",
    }:
        return "representation_pair"
    return cost_class


def _scale_matrix(values: np.ndarray, scaling: str) -> tuple[np.ndarray, np.ndarray]:
    if scaling == "zscore":
        center = np.mean(values, axis=0)
        scale = np.std(values, axis=0, ddof=0)
    elif scaling == "robust_iqr":
        center = np.median(values, axis=0)
        scale = np.percentile(values, 75, axis=0) - np.percentile(values, 25, axis=0)
        standard_deviation = np.std(values, axis=0, ddof=0)
        scale = np.where(scale > 1.0e-12, scale, standard_deviation)
    else:
        raise ValueError(f"Unknown scaling: {scaling}")
    keep = np.isfinite(scale) & (scale > 1.0e-12)
    _require(bool(np.any(keep)), "Block contains no nonconstant finite columns")
    return (values[:, keep] - center[keep]) / scale[keep], keep


def _pca_whiten(
    scaled: np.ndarray, variance_threshold: float
) -> tuple[np.ndarray, int, float]:
    _require(scaled.shape[0] >= 2, "PCA block needs at least two rows")
    _, singular_values, right = np.linalg.svd(scaled, full_matrices=False)
    explained = singular_values**2
    positive = explained > max(float(explained[0]) * 1.0e-12, 1.0e-24)
    rank = min(int(np.sum(positive)), scaled.shape[0] - 1)
    _require(rank >= 1, "PCA block has zero numerical rank")
    explained = explained[:rank]
    cumulative = np.cumsum(explained) / float(np.sum(explained))
    retained = int(np.searchsorted(cumulative, variance_threshold) + 1)
    retained = min(retained, rank)
    scores = scaled @ right[:retained].T
    eigenvalues = explained[:retained] / float(scaled.shape[0] - 1)
    coordinates = scores / np.sqrt(eigenvalues)
    return coordinates, retained, float(cumulative[retained - 1])


def build_block_models(
    features: pd.DataFrame,
    metadata: pd.DataFrame,
    columns: Sequence[str],
    *,
    scaling: str,
    variance_threshold: float,
    universal_only: bool,
) -> list[BlockModel]:
    metadata_by_column = metadata.set_index("column").to_dict(orient="index")
    grouped: dict[tuple[str, bytes], list[str]] = defaultdict(list)
    for column in columns:
        _require(column in metadata_by_column, f"No metadata for {column}")
        present = features[column].notna().to_numpy(dtype=bool)
        if universal_only and not bool(np.all(present)):
            continue
        logical = _logical_block(column, metadata_by_column[column])
        grouped[(logical, present.tobytes())].append(column)

    models: list[BlockModel] = []
    for (logical, mask_bytes), block_columns in sorted(
        grouped.items(), key=lambda item: (item[0][0], sorted(item[1]))
    ):
        mask = np.frombuffer(mask_bytes, dtype=bool, count=len(features)).copy()
        row_indices = np.flatnonzero(mask)
        values = features.loc[mask, sorted(block_columns)].to_numpy(dtype=float)
        _require(bool(np.isfinite(values).all()), f"Nonfinite value in block {logical}")
        scaled, keep = _scale_matrix(values, scaling)
        kept_columns = np.asarray(sorted(block_columns), dtype=object)[keep]
        dropped = np.asarray(sorted(block_columns), dtype=object)[~keep]
        coordinates, retained, retained_fraction = _pca_whiten(
            scaled, variance_threshold
        )
        signature = hashlib.sha256(mask_bytes).hexdigest()[:12]
        name = f"{logical}__n{len(row_indices)}__{signature}"
        models.append(
            BlockModel(
                name=name,
                logical_block=logical,
                columns=tuple(map(str, kept_columns)),
                row_indices=row_indices,
                coordinates=coordinates,
                retained_components=retained,
                retained_variance_fraction=retained_fraction,
                dropped_constant_columns=tuple(map(str, dropped)),
            )
        )
    _require(bool(models), "No feature blocks survived preprocessing")
    return models


def block_aware_distance(
    n_rows: int, models: Sequence[BlockModel]
) -> tuple[np.ndarray, np.ndarray]:
    """Average squared whitened distances over blocks shared by each pair."""
    sum_squared = np.zeros((n_rows, n_rows), dtype=float)
    shared = np.zeros((n_rows, n_rows), dtype=np.int16)
    for model in models:
        coordinates = model.coordinates
        norms = np.sum(coordinates**2, axis=1)
        squared = norms[:, None] + norms[None, :] - 2.0 * coordinates @ coordinates.T
        squared = np.maximum(squared, 0.0) / float(model.retained_components)
        index = np.ix_(model.row_indices, model.row_indices)
        sum_squared[index] += squared
        shared[index] += 1
    _require(bool(np.all(shared > 0)), "Some task pair shares no applicable block")
    distance = np.sqrt(sum_squared / shared)
    np.fill_diagonal(distance, 0.0)
    return distance, shared


def _tie_rank(task_uuid: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{task_uuid}".encode()).hexdigest()


def _choose_by_score(
    indices: Sequence[int], scores: np.ndarray, tasks: Sequence[str], seed: int
) -> int:
    best_score = max(float(scores[index]) for index in indices)
    tied = [
        index
        for index in indices
        if math.isclose(
            float(scores[index]), best_score, rel_tol=1.0e-12, abs_tol=1.0e-12
        )
    ]
    return min(tied, key=lambda index: (_tie_rank(tasks[index], seed), tasks[index]))


def stratified_farthest_first(
    distance: np.ndarray,
    tasks: Sequence[str],
    families: Sequence[str],
    *,
    max_k: int,
    seed: int,
) -> tuple[list[int], list[dict[str, Any]]]:
    """Seed every family with its medoid, then add the worst-covered task."""
    n_rows = len(tasks)
    _require(distance.shape == (n_rows, n_rows), "Distance shape mismatch")
    _require(len(families) == n_rows, "Family vector length mismatch")
    family_indices: dict[str, list[int]] = defaultdict(list)
    for index, family in enumerate(families):
        family_indices[str(family)].append(index)
    _require(max_k >= len(family_indices), "max_k cannot represent every family")
    _require(max_k <= n_rows, "max_k exceeds corpus size")

    selected: list[int] = []
    for family in sorted(family_indices):
        indices = family_indices[family]
        within = distance[np.ix_(indices, indices)]
        mean_distance = np.mean(within, axis=1)
        scores = np.full(n_rows, -np.inf)
        scores[indices] = -mean_distance
        selected.append(_choose_by_score(indices, scores, tasks, seed))

    nearest = np.full(n_rows, np.inf)
    for center in selected:
        same_family = np.asarray(families) == families[center]
        nearest[same_family] = np.minimum(
            nearest[same_family], distance[same_family, center]
        )
    selected_set = set(selected)
    curve = [_coverage_row(len(selected), nearest)]
    while len(selected) < max_k:
        candidates = [index for index in range(n_rows) if index not in selected_set]
        chosen = _choose_by_score(candidates, nearest, tasks, seed)
        selected.append(chosen)
        selected_set.add(chosen)
        same_family = np.asarray(families) == families[chosen]
        nearest[same_family] = np.minimum(
            nearest[same_family], distance[same_family, chosen]
        )
        curve.append(_coverage_row(len(selected), nearest))
    return selected, curve


def global_farthest_first(
    distance: np.ndarray,
    tasks: Sequence[str],
    *,
    max_k: int,
    seed: int,
) -> tuple[list[int], list[dict[str, Any]]]:
    """Pure feature-space farthest-first selection with no family constraint."""
    n_rows = len(tasks)
    _require(distance.shape == (n_rows, n_rows), "Distance shape mismatch")
    _require(1 <= max_k <= n_rows, "max_k outside corpus")
    scores = -np.mean(distance, axis=1)
    center = _choose_by_score(list(range(n_rows)), scores, tasks, seed)
    selected = [center]
    selected_set = {center}
    nearest = distance[:, center].copy()
    curve = [_coverage_row(1, nearest)]
    while len(selected) < max_k:
        candidates = [index for index in range(n_rows) if index not in selected_set]
        chosen = _choose_by_score(candidates, nearest, tasks, seed)
        selected.append(chosen)
        selected_set.add(chosen)
        nearest = np.minimum(nearest, distance[:, chosen])
        curve.append(_coverage_row(len(selected), nearest))
    return selected, curve


def _coverage_row(k: int, nearest: np.ndarray) -> dict[str, Any]:
    return {
        "k": k,
        "coverage_radius": float(np.max(nearest)),
        "distance_q95": float(np.quantile(nearest, 0.95)),
        "mean_distance": float(np.mean(nearest)),
        "median_distance": float(np.median(nearest)),
    }


def assign_within_family(
    distance: np.ndarray,
    selected: Sequence[int],
    tasks: Sequence[str],
    families: Sequence[str],
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    centers_by_family: dict[str, list[int]] = defaultdict(list)
    for center in selected:
        centers_by_family[str(families[center])].append(center)
    assignments = np.empty(len(tasks), dtype=int)
    assignment_distance = np.empty(len(tasks), dtype=float)
    for index, family in enumerate(families):
        centers = centers_by_family[str(family)]
        values = distance[index, centers]
        minimum = float(np.min(values))
        tied = [
            center
            for center, value in zip(centers, values)
            if math.isclose(float(value), minimum, rel_tol=1.0e-12, abs_tol=1.0e-12)
        ]
        chosen = min(
            tied, key=lambda center: (_tie_rank(tasks[center], seed), tasks[center])
        )
        assignments[index] = chosen
        assignment_distance[index] = distance[index, chosen]
    return assignments, assignment_distance


def assign_global(
    distance: np.ndarray,
    selected: Sequence[int],
    tasks: Sequence[str],
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Assign every task to its nearest selected center without family use."""
    _require(bool(selected), "At least one center is required")
    assignments = np.empty(len(tasks), dtype=int)
    assignment_distance = np.empty(len(tasks), dtype=float)
    centers = list(map(int, selected))
    for index in range(len(tasks)):
        values = distance[index, centers]
        minimum = float(np.min(values))
        tied = [
            center
            for center, value in zip(centers, values)
            if math.isclose(float(value), minimum, rel_tol=1.0e-12, abs_tol=1.0e-12)
        ]
        chosen = min(
            tied, key=lambda center: (_tie_rank(tasks[center], seed), tasks[center])
        )
        assignments[index] = chosen
        assignment_distance[index] = distance[index, chosen]
    return assignments, assignment_distance


def _availability_profiles(n_rows: int, models: Sequence[BlockModel]) -> list[str]:
    profiles: list[list[str]] = [[] for _ in range(n_rows)]
    for model in models:
        if len(model.row_indices) == n_rows:
            continue
        for index in model.row_indices:
            profiles[int(index)].append(model.name)
    return [
        (
            hashlib.sha256("|".join(sorted(names)).encode()).hexdigest()[:12]
            if names
            else "universal_only"
        )
        for names in profiles
    ]


def _selection_artifacts(
    *,
    k: int,
    selected_order: Sequence[int],
    distance: np.ndarray,
    tasks: Sequence[str],
    short_names: Sequence[str],
    families: Sequence[str],
    tiers: Sequence[str],
    profiles: Sequence[str],
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = list(selected_order[:k])
    assignments, assignment_distance = assign_within_family(
        distance, selected, tasks, families, seed
    )
    assigned: dict[int, list[int]] = defaultdict(list)
    for row_index, center in enumerate(assignments):
        assigned[int(center)].append(row_index)
    weights = []
    for order, center in enumerate(selected, start=1):
        members = assigned[center]
        family_population = sum(family == families[center] for family in families)
        weights.append(
            {
                "k": k,
                "selection_order": order,
                "task_uuid": tasks[center],
                "problem_instance_short_name": short_names[center],
                "family": families[center],
                "tier": tiers[center],
                "availability_profile": profiles[center],
                "selection_weight": len(members),
                "family_population": family_population,
                "cell_radius": float(np.max(assignment_distance[members])),
                "cell_mean_distance": float(np.mean(assignment_distance[members])),
                "weight_definition": "family_restricted_voronoi_cluster_size",
                "prototype_non_binding": True,
            }
        )
    assignment_rows = []
    for index, center in enumerate(assignments):
        assignment_rows.append(
            {
                "k": k,
                "task_uuid": tasks[index],
                "problem_instance_short_name": short_names[index],
                "family": families[index],
                "tier": tiers[index],
                "availability_profile": profiles[index],
                "selected_task_uuid": tasks[int(center)],
                "coverage_distance": float(assignment_distance[index]),
                "prototype_non_binding": True,
            }
        )
    return weights, assignment_rows


def global_selection_artifacts(
    *,
    k: int,
    selected_order: Sequence[int],
    distance: np.ndarray,
    tasks: Sequence[str],
    short_names: Sequence[str],
    families: Sequence[str],
    tiers: Sequence[str],
    profiles: Sequence[str],
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build global Voronoi weights plus family-stratified diagnostics."""
    selected = list(selected_order[:k])
    assignments, assignment_distance = assign_global(distance, selected, tasks, seed)
    assigned: dict[int, list[int]] = defaultdict(list)
    for row_index, center in enumerate(assignments):
        assigned[int(center)].append(row_index)
    weights = []
    for order, center in enumerate(selected, start=1):
        members = assigned[center]
        weights.append(
            {
                "k": k,
                "selection_order": order,
                "task_uuid": tasks[center],
                "problem_instance_short_name": short_names[center],
                "family": families[center],
                "tier": tiers[center],
                "availability_profile": profiles[center],
                "selection_weight": len(members),
                "cell_radius": float(np.max(assignment_distance[members])),
                "cell_mean_distance": float(np.mean(assignment_distance[members])),
                "weight_definition": "global_feature_space_voronoi_cluster_size",
                "family_used_for_selection": False,
                "binding_selection": True,
            }
        )
    assignment_rows = []
    for index, center_value in enumerate(assignments):
        center = int(center_value)
        assignment_rows.append(
            {
                "k": k,
                "task_uuid": tasks[index],
                "problem_instance_short_name": short_names[index],
                "family": families[index],
                "tier": tiers[index],
                "availability_profile": profiles[index],
                "selected_task_uuid": tasks[center],
                "selected_family": families[center],
                "cross_family_assignment": families[index] != families[center],
                "coverage_distance": float(assignment_distance[index]),
                "weight_definition": "global_feature_space_voronoi_cluster_size",
                "family_used_for_selection": False,
                "binding_selection": True,
            }
        )
    _require(
        sum(row["selection_weight"] for row in weights) == len(tasks),
        "Global Voronoi weights do not sum to corpus size",
    )
    return weights, assignment_rows


def _cost_by_task(
    cost_plan: Path, expected_tasks: set[str]
) -> dict[str, dict[str, Any]]:
    columns = [
        "task_uuid",
        "method",
        "projected_wall_seconds_q90",
        "wall_cap_seconds",
        "planned_disposition",
    ]
    frame = pd.read_csv(cost_plan, usecols=columns, low_memory=False)
    _require(frame.shape[0] == len(expected_tasks) * 5, "Cost plan is not 591x5")
    _require(set(map(str, frame["task_uuid"])) == expected_tasks, "Cost task mismatch")
    _require(
        not frame.duplicated(["task_uuid", "method"]).any(),
        "Duplicate cost task/method row",
    )
    output = {}
    for task_uuid, group in frame.groupby("task_uuid", sort=True):
        attempts = group[group["planned_disposition"].eq("planned_attempt")]
        q90 = float(attempts["projected_wall_seconds_q90"].sum()) / 3600.0
        cap = float(attempts["wall_cap_seconds"].sum()) / 3600.0
        output[str(task_uuid)] = {
            "planned_methods": int(len(attempts)),
            "not_attempted_methods": int(len(group) - len(attempts)),
            "predicted_node_hours_q90": q90,
            "predicted_node_hours_with_contingency": q90 * 1.25,
            "worst_case_cap_node_hours": cap,
        }
    return output


def _cost_option(
    selected_tasks: Sequence[str], cost: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "planned_method_attempts": sum(
            cost[task]["planned_methods"] for task in selected_tasks
        ),
        "not_attempted_methods": sum(
            cost[task]["not_attempted_methods"] for task in selected_tasks
        ),
        "predicted_node_hours_q90": float(
            sum(cost[task]["predicted_node_hours_q90"] for task in selected_tasks)
        ),
        "predicted_node_hours_with_25pct_contingency": float(
            sum(
                cost[task]["predicted_node_hours_with_contingency"]
                for task in selected_tasks
            )
        ),
        "worst_case_cap_node_hours": float(
            sum(cost[task]["worst_case_cap_node_hours"] for task in selected_tasks)
        ),
        "cost_model_role": "annotation_only_after_feature_space_selection",
    }


def _block_summary(models: Sequence[BlockModel], n_rows: int) -> list[dict[str, Any]]:
    return [
        {
            "name": model.name,
            "logical_block": model.logical_block,
            "applicable_tasks": len(model.row_indices),
            "universal": len(model.row_indices) == n_rows,
            "input_columns": list(model.columns),
            "dropped_constant_columns": list(model.dropped_constant_columns),
            "retained_components": model.retained_components,
            "retained_variance_fraction": model.retained_variance_fraction,
        }
        for model in models
    ]


def _profile_tvd(
    corpus_profiles: Sequence[str], selected_profiles: Sequence[str]
) -> float:
    corpus = Counter(corpus_profiles)
    selected = Counter(selected_profiles)
    keys = set(corpus) | set(selected)
    return 0.5 * sum(
        abs(corpus[key] / len(corpus_profiles) - selected[key] / len(selected_profiles))
        for key in keys
    )


def report_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "ml5_prototype_report.schema.json",
        "type": "object",
        "required": [
            "prototype_status",
            "binding_selection",
            "outcome_blind",
            "input_provenance",
            "corpus",
            "primary_metric",
            "k_options",
        ],
        "properties": {
            "prototype_status": {"const": "non_binding"},
            "binding_selection": {"const": False},
            "outcome_blind": {"const": True},
            "k_options": {
                "type": "array",
                "minItems": 4,
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "required": ["k", "coverage_radius", "selection_cost"],
                },
            },
        },
        "additionalProperties": True,
    }


def artifact_schemas() -> dict[str, Any]:
    return {
        "schema_version": "ml5-phase-a-prototype-v1",
        "coverage_curve.csv": {
            "primary_key": ["k"],
            "columns": [
                "k",
                "coverage_radius",
                "distance_q95",
                "mean_distance",
                "median_distance",
                "candidate_k",
                "prototype_non_binding",
            ],
        },
        "selection_weights.csv": {
            "primary_key": ["k", "task_uuid"],
            "columns": [
                "k",
                "selection_order",
                "task_uuid",
                "problem_instance_short_name",
                "family",
                "tier",
                "availability_profile",
                "selection_weight",
                "family_population",
                "cell_radius",
                "cell_mean_distance",
                "weight_definition",
                "prototype_non_binding",
            ],
        },
        "coverage_assignments.csv": {
            "primary_key": ["k", "task_uuid"],
            "columns": [
                "k",
                "task_uuid",
                "problem_instance_short_name",
                "family",
                "tier",
                "availability_profile",
                "selected_task_uuid",
                "coverage_distance",
                "prototype_non_binding",
            ],
        },
    }


def _load_and_verify_inputs(
    repo_root: Path, manifest: Mapping[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, str]]]:
    inputs = manifest["inputs"]
    for spec in inputs.values():
        path = repo_root / spec["path"]
        _require(path.is_file(), f"Missing pinned input: {spec['path']}")
        _require(sha256_file(path) == spec["sha256"], f"SHA mismatch: {spec['path']}")
    features = pd.read_csv(
        repo_root / inputs["feature_table"]["path"], low_memory=False
    )
    metadata = pd.read_csv(repo_root / inputs["feature_metadata"]["path"])
    expected_shape = tuple(inputs["feature_table"]["shape"])
    _require(features.shape == expected_shape, "Feature table shape mismatch")
    _require(
        metadata.shape[0] == features.shape[1]
        and set(metadata["column"]) == set(features.columns),
        "Feature metadata does not cover the table exactly",
    )
    tasks = load_family_map(repo_root / "problem_instances")
    _require(len(tasks) == len(features), "Family map size mismatch")
    _require(
        family_map_sha256(tasks) == manifest["family_mapping"]["sha256"],
        "Family-map SHA mismatch",
    )
    observed_families = dict(
        sorted(Counter(row["family"] for row in tasks.values()).items())
    )
    _require(
        observed_families == manifest["family_mapping"]["family_counts"],
        "Family census mismatch",
    )
    return features, metadata, tasks


def run_prototype(repo_root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(manifest.get("prototype_status") == "non_binding", "Not a prototype")
    _require(manifest.get("binding_selection") is False, "Binding run is gated")
    schema_path = repo_root / "analysis/ml_core_set/manifest_prototype.schema.json"
    Draft202012Validator(json.loads(schema_path.read_text())).validate(manifest)
    features, metadata, task_metadata = _load_and_verify_inputs(repo_root, manifest)

    tasks = list(map(str, features["task_uuid"]))
    _require(len(tasks) == len(set(tasks)), "Feature table has duplicate task UUIDs")
    _require(set(tasks) == set(task_metadata), "Feature/family task sets differ")
    families = [task_metadata[task]["family"] for task in tasks]
    tiers = [task_metadata[task]["tier"] for task in tasks]
    short_names = list(map(str, features["problem_instance_short_name"]))

    eligible = eligible_feature_columns(metadata)
    identifier_columns = list(manifest["identifier_columns"])
    identifier_artifact = json.loads(
        (repo_root / manifest["inputs"]["identifier_screen"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    _require(
        identifier_columns == identifier_artifact.get("identifier_columns"),
        "Identifier list differs from the pinned screen",
    )
    _require(set(identifier_columns) <= set(eligible), "Identifier column not eligible")
    primary_columns = sorted(set(eligible) - set(identifier_columns))
    _require(
        len(eligible) == manifest["expected_counts"]["eligible_columns"],
        "Eligible count drift",
    )
    _require(
        len(primary_columns) == manifest["expected_counts"]["primary_columns"],
        "Primary count drift",
    )

    _require(len(tasks) == manifest["expected_counts"]["tasks"], "Task count drift")
    _require(
        len(set(families)) == manifest["expected_counts"]["families"],
        "Family count drift",
    )
    variants = manifest["metric_variants"]
    variant_results: dict[str, dict[str, Any]] = {}
    candidate_ks = list(map(int, manifest["candidate_k_values"]))
    max_k = max(candidate_ks)
    seed = int(manifest["seed"])
    for variant in variants:
        columns = eligible if variant["include_identifier_columns"] else primary_columns
        models = build_block_models(
            features,
            metadata,
            columns,
            scaling=str(variant["scaling"]),
            variance_threshold=float(variant["pca_variance_threshold"]),
            universal_only=bool(variant["universal_only"]),
        )
        distance, shared = block_aware_distance(len(features), models)
        order, curve = stratified_farthest_first(
            distance, tasks, families, max_k=max_k, seed=seed
        )
        variant_results[str(variant["name"])] = {
            "config": dict(variant),
            "models": models,
            "distance": distance,
            "shared": shared,
            "order": order,
            "curve": curve,
        }

    primary = variant_results[manifest["primary_metric_variant"]]
    primary_models = primary["models"]
    profiles = _availability_profiles(len(features), primary_models)
    all_weights: list[dict[str, Any]] = []
    all_assignments: list[dict[str, Any]] = []
    for k in candidate_ks:
        weights, assignments = _selection_artifacts(
            k=k,
            selected_order=primary["order"],
            distance=primary["distance"],
            tasks=tasks,
            short_names=short_names,
            families=families,
            tiers=tiers,
            profiles=profiles,
            seed=seed,
        )
        all_weights.extend(weights)
        all_assignments.extend(assignments)

    cost_path = repo_root / manifest["inputs"]["cost_plan_annotation_only"]["path"]
    costs = _cost_by_task(cost_path, set(tasks))
    curve_lookup = {row["k"]: row for row in primary["curve"]}
    k_options = []
    for k in candidate_ks:
        chosen = primary["order"][:k]
        selected_tasks = [tasks[index] for index in chosen]
        family_counts = dict(
            sorted(Counter(families[index] for index in chosen).items())
        )
        k_options.append(
            dict(curve_lookup[k])
            | {
                "family_counts": family_counts,
                "all_families_represented": set(family_counts) == set(families),
                "weight_sum": sum(
                    row["selection_weight"] for row in all_weights if row["k"] == k
                ),
                "selection_cost": _cost_option(selected_tasks, costs),
            }
        )

    primary_sets = {
        k: {tasks[index] for index in primary["order"][:k]} for k in candidate_ks
    }
    sensitivity_rows = []
    for name, result in variant_results.items():
        if name == manifest["primary_metric_variant"]:
            continue
        comparisons = []
        for k in candidate_ks:
            selected = {tasks[index] for index in result["order"][:k]}
            overlap = len(primary_sets[k] & selected)
            profiles_selected = [profiles[index] for index in result["order"][:k]]
            comparisons.append(
                {
                    "k": k,
                    "overlap_count": overlap,
                    "overlap_fraction": overlap / k,
                    "jaccard": overlap / len(primary_sets[k] | selected),
                    "coverage_radius": next(
                        row["coverage_radius"]
                        for row in result["curve"]
                        if row["k"] == k
                    ),
                    "primary_availability_profile_tvd": _profile_tvd(
                        profiles, profiles_selected
                    ),
                }
            )
        sensitivity_rows.append(
            {
                "variant": name,
                "config": result["config"],
                "block_count": len(result["models"]),
                "comparisons": comparisons,
            }
        )

    output_dir = repo_root / manifest["output_directory"]
    coverage_columns = artifact_schemas()["coverage_curve.csv"]["columns"]
    curve_rows = [
        row
        | {
            "candidate_k": row["k"] in candidate_ks,
            "prototype_non_binding": True,
        }
        for row in primary["curve"]
    ]
    stable_csv_dump(curve_rows, coverage_columns, output_dir / "coverage_curve.csv")
    weight_columns = artifact_schemas()["selection_weights.csv"]["columns"]
    stable_csv_dump(all_weights, weight_columns, output_dir / "selection_weights.csv")
    assignment_columns = artifact_schemas()["coverage_assignments.csv"]["columns"]
    stable_csv_dump(
        all_assignments,
        assignment_columns,
        output_dir / "coverage_assignments.csv",
    )

    sensitivity = {
        "schema_version": "ml5-phase-a-prototype-v1",
        "prototype_status": "non_binding",
        "primary_variant": manifest["primary_metric_variant"],
        "interpretation_rule": (
            "Report drift; do not tune the metric or choose k from these "
            "prototype results."
        ),
        "variants": sensitivity_rows,
    }
    stable_json_dump(sensitivity, output_dir / "sensitivity_report.json")
    schemas = artifact_schemas()
    stable_json_dump(schemas, output_dir / "artifact_schemas.json")
    schema = report_schema()
    stable_json_dump(schema, output_dir / "ml5_prototype_report.schema.json")

    report = {
        "$schema": "ml5_prototype_report.schema.json",
        "schema_version": "ml5-phase-a-prototype-v1",
        "prototype_status": "non_binding",
        "binding_selection": False,
        "outcome_blind": True,
        "selection_consumed_solver_results": False,
        "binding_gate": (
            "PI must pin the complete post-production feature table before any "
            "binding selection."
        ),
        "input_provenance": manifest["inputs"],
        "family_mapping": manifest["family_mapping"],
        "corpus": {
            "tasks": len(tasks),
            "families": len(set(families)),
            "family_counts": dict(sorted(Counter(families).items())),
            "tiers": dict(sorted(Counter(tiers).items())),
        },
        "primary_metric": {
            "variant": manifest["primary_metric_variant"],
            "eligible_columns": len(eligible),
            "identifier_columns_excluded": identifier_columns,
            "selected_columns": len(primary_columns),
            "blocks": _block_summary(primary_models, len(features)),
            "shared_block_count_min": int(np.min(primary["shared"])),
            "shared_block_count_max": int(np.max(primary["shared"])),
            "distance_definition": (
                "root mean square of per-block PCA-whitened RMS distances over "
                "blocks applicable to both systems; no missing value is imputed"
            ),
        },
        "selection_algorithm": manifest["selection_algorithm"],
        "candidate_k_values": candidate_ks,
        "k_decision": "deferred_to_Matt_and_PI",
        "k_options": k_options,
        "selection_weights": {
            "definition": "family_restricted_voronoi_cluster_size",
            "sum_to_corpus_size_for_every_k": all(
                option["weight_sum"] == len(tasks) for option in k_options
            ),
            "population_claim_rule": (
                "Multiply each selected-system contribution by selection_weight; "
                "family sums reproduce family population sizes."
            ),
        },
        "cost_annotation": {
            "source_role": "accepted G-48 Phase-1 five-method planning model",
            "selection_independence": (
                "Cost data are loaded only after all feature-space selections "
                "are fixed."
            ),
            "limitation": (
                "These are G-48 panel-equivalent node-hours, not a future expensive-"
                "solver campaign estimate."
            ),
        },
        "sensitivity_artifact": "sensitivity_report.json",
    }
    Draft202012Validator(schema).validate(report)
    stable_json_dump(report, output_dir / "ml5_prototype_report.json")

    generated = [
        "artifact_schemas.json",
        "coverage_assignments.csv",
        "coverage_curve.csv",
        "ml5_prototype_report.json",
        "ml5_prototype_report.schema.json",
        "selection_weights.csv",
        "sensitivity_report.json",
    ]
    artifact_manifest = {
        "schema_version": "ml5-phase-a-prototype-v1",
        "prototype_status": "non_binding",
        "artifacts": [
            {
                "path": name,
                "sha256": sha256_file(output_dir / name),
                "bytes": (output_dir / name).stat().st_size,
            }
            for name in generated
        ],
    }
    stable_json_dump(artifact_manifest, output_dir / "artifact_manifest.json")
    return {
        "prototype_status": "non_binding",
        "tasks": len(tasks),
        "families": len(set(families)),
        "eligible_columns": len(eligible),
        "primary_columns": len(primary_columns),
        "primary_blocks": len(primary_models),
        "candidate_k_values": candidate_ks,
        "weight_rows": len(all_weights),
        "assignment_rows": len(all_assignments),
        "generated_artifacts": len(generated) + 1,
    }
