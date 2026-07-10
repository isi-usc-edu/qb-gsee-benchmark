#!/usr/bin/env python3
"""Export the deterministic METRICS_SPEC v1.2 dashboard/paper data bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from qb_gsee_benchmark.metrics import build_bundle_v1_2  # noqa: E402

DEFAULT_OUTPUT = REPOSITORY_ROOT / "scripts" / "dashboard_data" / "metrics_v1_2.json"


def load_committed_artifacts(repository_root: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Normalize instance and non-resource solution JSONs for pure metrics."""

    tasks: dict[str, dict[str, Any]] = {}
    for path in sorted((repository_root / "problem_instances").rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        family = path.parent.name
        instance_uuid = str(document.get("problem_instance_uuid", ""))
        for raw_task in document.get("tasks", []):
            task = dict(raw_task)
            task_uuid = str(task.get("task_uuid", ""))
            if not task_uuid:
                continue
            if task_uuid in tasks:
                raise ValueError(f"duplicate task_uuid {task_uuid}")
            task["family"] = family
            task["problem_instance_uuid"] = instance_uuid
            tasks[task_uuid] = task

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
        for result in solution_data:
            if not isinstance(result, dict):
                continue
            task_uuid = str(result.get("task_uuid", ""))
            if not task_uuid:
                continue
            pair = (solver, task_uuid)
            if pair in seen_pairs:
                raise ValueError(f"multiple committed attempts for solver/task pair {pair}")
            seen_pairs.add(pair)
            attempts.append(
                {
                    "solver": solver,
                    "task_uuid": task_uuid,
                    "energy": result.get("energy"),
                    "source": path.relative_to(repository_root).as_posix(),
                }
            )
    return tasks, attempts


def export_bundle(repository_root: Path, output: Path, bootstrap_iterations: int = 1000) -> bytes:
    tasks, attempts = load_committed_artifacts(repository_root)
    bundle = build_bundle_v1_2(
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
