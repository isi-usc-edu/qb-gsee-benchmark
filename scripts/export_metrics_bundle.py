#!/usr/bin/env python3
"""Export the deterministic METRICS_SPEC v1.7 dashboard/paper data bundle."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from qb_gsee_benchmark.metrics import build_bundle_v1_7  # noqa: E402

DEFAULT_OUTPUT = REPOSITORY_ROOT / "scripts" / "dashboard_data" / "metrics_v1_7.json"


def _require_hartree(value: Any, context: str) -> None:
    if value != "Hartree":
        raise ValueError(f"{context} units must be Hartree, got {value!r}")


def _load_feature_norb(repository_root: Path) -> dict[str, int]:
    path = repository_root / "scripts" / "Hamiltonian_features.csv"
    if not path.exists():
        return {}
    values: dict[str, int] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            task_uuid = str(row.get("task_uuid") or "")
            candidates = []
            for key in ("n_orbs", "num_orbitals"):
                raw = row.get(key)
                if raw not in (None, ""):
                    number = float(raw)
                    if not number.is_integer() or number < 0:
                        raise ValueError(f"invalid {key} for task {task_uuid}: {raw!r}")
                    candidates.append(int(number))
            if not task_uuid or not candidates:
                continue
            if len(set(candidates)) != 1:
                raise ValueError(f"feature CSV NORB disagreement for task {task_uuid}")
            norb = candidates[0]
            if task_uuid in values and values[task_uuid] != norb:
                raise ValueError(f"duplicate feature CSV NORB disagreement for task {task_uuid}")
            values[task_uuid] = norb
    return values


LEGACY_MAPPING_RELATIVE_PATH = Path(
    "analysis/solver_panel/g31_legacy_lattice_task_mapping.csv"
)
CERTIFIED_MAPPING_STATUS = "certified_identity_lineage_and_recovered_payload"
LEGACY_LATTICE_PROBLEM_UUIDS = (
    "c2009f9f-4738-4919-9295-5f9231ca5199",
    "614c4444-a31a-4348-b24d-01040208651c",
)


def _load_legacy_task_mapping(repository_root: Path) -> dict[str, str]:
    path = repository_root / LEGACY_MAPPING_RELATIVE_PATH
    if not path.exists():
        legacy_files = [
            candidate.relative_to(repository_root).as_posix()
            for candidate in sorted((repository_root / "solution_files").rglob("*.json"))
            if any(token in candidate.as_posix() for token in LEGACY_LATTICE_PROBLEM_UUIDS)
        ]
        if legacy_files:
            raise FileNotFoundError(
                f"required certified legacy task mapping is absent: {path}; "
                f"legacy lattice solution files exist, including {legacy_files[0]}"
            )
        return {}
    mapping: dict[str, str] = {}
    current_ids: set[str] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            legacy = str(row.get("legacy_task_uuid") or "")
            current = str(row.get("current_task_uuid") or "")
            status = str(row.get("mapping_status") or "")
            if not legacy or not current or status != CERTIFIED_MAPPING_STATUS:
                raise ValueError(f"uncertified or incomplete legacy mapping row: {row}")
            if legacy in mapping or current in current_ids:
                raise ValueError("legacy lattice mapping must be one-to-one")
            mapping[legacy] = current
            current_ids.add(current)
    return mapping


def _metadata_norb(task_uuid: str, task: dict[str, Any]) -> tuple[int | None, list[str]]:
    features = task.get("features", {})
    independent = task.get("independent_parameters", {})
    if not isinstance(features, dict):
        features = {}
    if not isinstance(independent, dict):
        independent = {}
    raw_candidates = (
        ("features.num_orbitals", features.get("num_orbitals")),
        ("features.hubbard_num_sites", features.get("hubbard_num_sites")),
        ("independent_parameters.num_sites", independent.get("num_sites")),
        (
            "independent_parameters.num_spatial_orbitals",
            independent.get("num_spatial_orbitals"),
        ),
    )
    candidates: list[tuple[str, int]] = []
    for field, raw in raw_candidates:
        if raw is None:
            continue
        number = float(raw)
        if not number.is_integer() or number < 0:
            raise ValueError(f"invalid {field} for task {task_uuid}: {raw!r}")
        candidates.append((field, int(number)))
    if len({value for _, value in candidates}) > 1:
        raise ValueError(f"metadata NORB disagreement for task {task_uuid}: {candidates}")
    return (candidates[0][1] if candidates else None, [field for field, _ in candidates])


def load_committed_artifacts(repository_root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Normalize instance and non-resource solution JSONs for pure metrics."""

    tasks: dict[str, dict[str, Any]] = {}
    feature_norb = _load_feature_norb(repository_root)
    legacy_mapping = _load_legacy_task_mapping(repository_root)
    for path in sorted((repository_root / "problem_instances").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        family = path.parent.name
        instance_uuid = str(document.get("problem_instance_uuid", ""))
        for raw_task in document.get("tasks", []):
            # The metric layer converts reference_energy_uncertainty in mHa to
            # Hartree before taking the maximum across supported uncertainty fields.
            task = dict(raw_task)
            task_uuid = str(task.get("task_uuid", ""))
            if not task_uuid:
                continue
            if task_uuid in tasks:
                raise ValueError(f"duplicate task_uuid {task_uuid}")
            task["family"] = family
            task["problem_instance_uuid"] = instance_uuid
            requirements = task.get("requirements", {})
            if not isinstance(requirements, dict):
                raise ValueError(f"task {task_uuid} requirements must be an object")
            if requirements.get("absolute_accuracy_threshold") is not None:
                _require_hartree(
                    requirements.get("absolute_accuracy_threshold_energy_units"),
                    f"task {task_uuid} threshold",
                )
            if requirements.get("reference_energy") is not None:
                _require_hartree(
                    requirements.get("reference_energy_units"),
                    f"task {task_uuid} reference energy",
                )
            metadata_norb, metadata_fields = _metadata_norb(task_uuid, task)
            csv_norb = feature_norb.get(task_uuid)
            if metadata_norb is not None and csv_norb is not None and metadata_norb != csv_norb:
                raise ValueError(f"metadata/feature CSV NORB disagreement for task {task_uuid}")
            task["metrics_norb"] = metadata_norb if metadata_norb is not None else csv_norb
            task["metrics_norb_metadata_fields"] = metadata_fields
            task["metrics_norb_source"] = (
                "task_metadata+feature_csv"
                if metadata_norb is not None and csv_norb is not None
                else "task_metadata"
                if metadata_norb is not None
                else "feature_csv"
                if csv_norb is not None
                else "unspecified"
            )
            tasks[task_uuid] = task

    missing_mapping_targets = sorted(set(legacy_mapping.values()) - set(tasks))
    if missing_mapping_targets:
        raise ValueError(f"legacy mapping targets absent from committed instances: {missing_mapping_targets}")

    attempts: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for path in sorted((repository_root / "solution_files").rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if document.get("is_resource_estimate") is not False:
            continue
        solution_data = document.get("solution_data")
        solver_details = document.get("solver_details")
        if not isinstance(solution_data, list) or not isinstance(solver_details, dict):
            continue
        solver = str(solver_details.get("solver_short_name") or "unknown")
        relative_path = path.relative_to(repository_root / "solution_files")
        solution_file_family = relative_path.parts[0] if len(relative_path.parts) > 1 else "_root"
        for result in solution_data:
            if not isinstance(result, dict):
                continue
            solution_details = result.get("solution_details")
            if not isinstance(solution_details, dict):
                solution_details = {}
            if result.get("energy") is not None or "energy_units" in result:
                _require_hartree(
                    result.get("energy_units"),
                    f"solution {path} task {result.get("task_uuid", "unknown")} energy",
                )
            original_task_uuid = str(result.get("task_uuid", ""))
            if not original_task_uuid:
                continue
            task_uuid = legacy_mapping.get(original_task_uuid, original_task_uuid)
            joined_via_mapping = original_task_uuid in legacy_mapping
            pair = (solver, task_uuid)
            if pair in seen_pairs:
                raise ValueError(f"multiple committed attempts for solver/task pair {pair}")
            seen_pairs.add(pair)
            attempts.append(
                {
                    "solver": solver,
                    "task_uuid": task_uuid,
                    "original_task_uuid": original_task_uuid,
                    "joined_via_legacy_mapping": joined_via_mapping,
                    "legacy_mapping_source": (
                        LEGACY_MAPPING_RELATIVE_PATH.as_posix()
                        if joined_via_mapping
                        else None
                    ),
                    "energy": result.get("energy"),
                    "attempted": solution_details.get("attempted"),
                    "harness_status": solution_details.get("harness_status"),
                    "not_attempted_reason": solution_details.get("not_attempted_reason"),
                    "source": path.relative_to(repository_root).as_posix(),
                    "solution_file_family": solution_file_family,
                }
            )
    return tasks, attempts


def export_bundle(repository_root: Path, output: Path, bootstrap_iterations: int = 1000) -> bytes:
    tasks, attempts = load_committed_artifacts(repository_root)
    bundle = build_bundle_v1_7(
        tasks, attempts, bootstrap_iterations=bootstrap_iterations
    )
    encoded = (json.dumps(bundle, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(encoded)
    return encoded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-iterations", type=int, default=1000)
    args = parser.parse_args()
    export_bundle(args.repository_root.resolve(), args.output.resolve(), args.bootstrap_iterations)


if __name__ == "__main__":
    main()
