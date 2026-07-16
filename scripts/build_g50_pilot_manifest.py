#!/usr/bin/env python3
"""Build the target-blind G-50 pilot task manifest deterministically."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEATURES_PATH = Path("scripts/Hamiltonian_features.csv")
OUTPUT_PATH = Path("analysis/solver_campaigns/g50_pilot_task_manifest_v1.json")
PILOT_TASK_COUNT = 12
EXPECTED_CORPUS_TASKS = 718
ALGORITHM_ID = "rank_scaled_maximin_unique_family_v1"
FORBIDDEN_FIELD_TOKENS = (
    "accuracy_threshold",
    "prior_solver_outcome",
    "reference_energy",
    "supervised_success_label",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _finite_number(value: Any) -> float | None:
    if value in (None, "", "nan", "None"):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _task_value(row: dict[str, str], task: dict[str, Any], key: str) -> float:
    value = _finite_number(row.get(key))
    if value is not None:
        return value
    for container in (task.get("features", {}), task.get("independent_parameters", {})):
        value = _finite_number(container.get(key))
        if value is not None:
            return value
    raise ValueError(f"Task {row['task_uuid']} has no target-blind value for {key}")


def _log10_determinant_bound(
    row: dict[str, str], task: dict[str, Any], norb: int, nelec: int, ms2: int
) -> tuple[float, str]:
    value = _finite_number(row.get("log_fci_dim"))
    if value is not None:
        return value, "Hamiltonian_features.csv:log_fci_dim"
    determinant_count = _finite_number(
        task.get("features", {}).get("determinant_count")
    )
    if determinant_count is not None and determinant_count >= 1:
        return math.log10(determinant_count), "problem_instance:determinant_count"
    if (nelec + ms2) % 2:
        raise ValueError(f"Task {row['task_uuid']} has inconsistent NELEC/MS2 parity")
    nalpha = (nelec + ms2) // 2
    nbeta = nelec - nalpha
    if not (0 <= nalpha <= norb and 0 <= nbeta <= norb):
        raise ValueError(f"Task {row['task_uuid']} has an invalid electron sector")
    log_dimension = (
        math.lgamma(norb + 1)
        - math.lgamma(nalpha + 1)
        - math.lgamma(norb - nalpha + 1)
        + math.lgamma(norb + 1)
        - math.lgamma(nbeta + 1)
        - math.lgamma(norb - nbeta + 1)
    ) / math.log(10.0)
    return log_dimension, "derived_spin_sector_determinant_bound"


def _load_task_index(
    root: Path,
) -> dict[str, tuple[Path, dict[str, Any], dict[str, Any]]]:
    index: dict[str, tuple[Path, dict[str, Any], dict[str, Any]]] = {}
    for path in sorted((root / "problem_instances").rglob("*.json")):
        instance = json.loads(path.read_text(encoding="utf-8"))
        for task in instance.get("tasks", []):
            task_uuid = task["task_uuid"]
            if task_uuid in index:
                raise ValueError(f"Duplicate task UUID {task_uuid}")
            index[task_uuid] = (path, instance, task)
    return index


def _fcidump_record(task: dict[str, Any]) -> dict[str, Any]:
    records = [
        item
        for item in task.get("supporting_files", [])
        if item.get("is_fcidump_file") is True
    ]
    if len(records) != 1:
        raise ValueError(
            f"Task {task['task_uuid']} must have exactly one FCIDUMP, found {len(records)}"
        )
    record = records[0]
    return {
        "instance_data_checksum": record["instance_data_checksum"],
        "instance_data_checksum_type": record["instance_data_checksum_type"],
        "instance_data_object_url": record["instance_data_object_url"],
        "instance_data_object_uuid": record["instance_data_object_uuid"],
    }


def _family_key(row: dict[str, str], task: dict[str, Any]) -> tuple[str, str]:
    features = task.get("features", {})
    for key in ("ml_family_weighting_group", "hamiltonian_family"):
        value = features.get(key)
        if value:
            return str(value), f"problem_instance:{key}"
    return (
        row["problem_instance_short_name"],
        "Hamiltonian_features.csv:problem_instance_short_name",
    )


def _squared_distance(left: list[float], right: list[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(left, right, strict=True))


def build(root: Path = ROOT) -> dict[str, Any]:
    features_path = root / FEATURES_PATH
    with features_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_CORPUS_TASKS:
        raise ValueError(
            f"Expected {EXPECTED_CORPUS_TASKS} feature rows, found {len(rows)}"
        )
    if len({row["task_uuid"] for row in rows}) != len(rows):
        raise ValueError("Feature table task UUIDs are not unique")

    task_index = _load_task_index(root)
    if set(task_index) != {row["task_uuid"] for row in rows}:
        raise ValueError("Feature table and problem-instance task UUID sets differ")

    candidates: list[dict[str, Any]] = []
    for row in rows:
        task_uuid = row["task_uuid"]
        path, instance, task = task_index[task_uuid]
        family, family_source = _family_key(row, task)
        norb = int(_task_value(row, task, "n_orbs"))
        nelec = int(_task_value(row, task, "n_elec"))
        ms2 = int(_task_value(row, task, "ms2"))
        log_dimension, log_dimension_source = _log10_determinant_bound(
            row, task, norb, nelec, ms2
        )
        vector = [
            math.log10(norb + 1),
            nelec / (2.0 * norb),
            abs(ms2) / max(1, nelec),
            log_dimension,
        ]
        candidates.append(
            {
                "family": family,
                "family_source": family_source,
                "instance": instance,
                "instance_path": path,
                "log_dimension_source": log_dimension_source,
                "problem_instance_uuid": row["problem_instance_uuid"],
                "row": row,
                "task": task,
                "task_uuid": task_uuid,
                "target_blind_vector": vector,
                "descriptors": {
                    "abs_ms2_fraction": vector[2],
                    "electron_filling_fraction": vector[1],
                    "log10_determinant_space_bound": vector[3],
                    "ms2": ms2,
                    "n_electrons": nelec,
                    "n_orbitals": norb,
                },
            }
        )

    rank_vectors = [[0.0] * len(candidates) for _ in range(4)]
    for column in range(4):
        order = sorted(
            range(len(candidates)),
            key=lambda index: (
                candidates[index]["target_blind_vector"][column],
                candidates[index]["task_uuid"],
            ),
        )
        for rank, index in enumerate(order):
            rank_vectors[column][index] = rank / (len(candidates) - 1)
    scaled = [
        [rank_vectors[column][index] for column in range(4)]
        for index in range(len(candidates))
    ]

    center = [0.5] * 4
    first = min(
        range(len(candidates)),
        key=lambda index: (
            _squared_distance(scaled[index], center),
            candidates[index]["task_uuid"],
        ),
    )
    selected = [first]
    selected_families = {candidates[first]["family"]}
    selection_distances = [math.sqrt(_squared_distance(scaled[first], center))]
    while len(selected) < PILOT_TASK_COUNT:
        eligible = [
            index
            for index in range(len(candidates))
            if index not in selected
            and candidates[index]["family"] not in selected_families
        ]
        if not eligible:
            raise ValueError(
                "Not enough distinct problem-instance families for pilot selection"
            )
        distance_by_index = {
            index: min(
                _squared_distance(scaled[index], scaled[chosen]) for chosen in selected
            )
            for index in eligible
        }
        best_distance = max(distance_by_index.values())
        chosen = min(
            (
                index
                for index, distance in distance_by_index.items()
                if math.isclose(distance, best_distance, rel_tol=0.0, abs_tol=1e-15)
            ),
            key=lambda index: candidates[index]["task_uuid"],
        )
        selected.append(chosen)
        selected_families.add(candidates[chosen]["family"])
        selection_distances.append(math.sqrt(distance_by_index[chosen]))

    pilot_tasks = []
    for selection_rank, (index, distance) in enumerate(
        zip(selected, selection_distances, strict=True), start=1
    ):
        item = candidates[index]
        relative_path = item["instance_path"].relative_to(root).as_posix()
        pilot_tasks.append(
            {
                "descriptors": item["descriptors"],
                "family_group": item["family"],
                "family_group_source": item["family_source"],
                "fcidump": _fcidump_record(item["task"]),
                "log10_determinant_space_bound_source": item["log_dimension_source"],
                "problem_instance_path": relative_path,
                "problem_instance_sha256": _sha256(item["instance_path"]),
                "problem_instance_short_name": item["family"],
                "problem_instance_uuid": item["problem_instance_uuid"],
                "selection_distance": round(distance, 15),
                "selection_rank": selection_rank,
                "task_uuid": item["task_uuid"],
            }
        )

    result = {
        "corpus": {
            "feature_table_path": FEATURES_PATH.as_posix(),
            "feature_table_sha256": _sha256(features_path),
            "task_count": len(candidates),
        },
        "forbidden_selection_fields": list(FORBIDDEN_FIELD_TOKENS),
        "pilot_task_count": len(pilot_tasks),
        "pilot_tasks": pilot_tasks,
        "schema_version": 1,
        "selection": {
            "algorithm_id": ALGORITHM_ID,
            "family_constraint": "one_task_per_declared_family_group",
            "first_point": "nearest_rank_scaled_descriptor_median",
            "next_points": "maximum_minimum_rank_scaled_euclidean_distance",
            "target_blind_descriptors": [
                "log10_n_orbitals_plus_one",
                "electron_filling_fraction",
                "abs_ms2_fraction",
                "log10_determinant_space_bound",
            ],
            "tie_break": "lexicographically_smallest_task_uuid",
        },
        "status": "design_only_submission_held",
    }
    serialized = _json_dump(result["pilot_tasks"]).lower()
    for token in FORBIDDEN_FIELD_TOKENS:
        if token in serialized:
            raise ValueError(
                f"Forbidden target field leaked into pilot manifest: {token}"
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    rendered = _json_dump(build(root))
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"stale or missing pilot manifest: {output}")
        print(f"verified {output}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
