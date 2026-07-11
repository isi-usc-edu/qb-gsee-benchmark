#!/usr/bin/env python3
"""Verify G40 feature tags on the certified G21 representation pairs."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.features.feature_schema import metadata_for_column


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pair-instance-dir",
        type=Path,
        default=ROOT / "problem_instances" / "orbital_representation_pairs",
    )
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rtol", type=float, default=1.0e-9)
    parser.add_argument("--atol", type=float, default=1.0e-10)
    return parser.parse_args()


def _close(left: Any, right: Any, rtol: float, atol: float) -> bool:
    if left is None or right is None:
        return left is right
    return math.isclose(float(left), float(right), rel_tol=rtol, abs_tol=atol)


def main() -> int:
    args = parse_args()
    groups: dict[str, list[str]] = defaultdict(list)
    for path in sorted(args.pair_instance_dir.glob("*.json")):
        document = json.loads(path.read_text())
        for task in document["tasks"]:
            group = task.get("features", {}).get("equivalence_group_id")
            if not group:
                raise ValueError(f"{task['task_uuid']} lacks equivalence_group_id")
            groups[group].append(task["task_uuid"])

    states = {}
    for path in sorted(args.state_dir.glob("*.linear.json")):
        state = json.loads(path.read_text())
        states[state["task_uuid"]] = state

    reports = []
    failures = []
    for group, task_uuids in sorted(groups.items()):
        missing = sorted(set(task_uuids) - set(states))
        if missing:
            failures.append({"group": group, "reason": "missing_state", "tasks": missing})
            reports.append(
                {
                    "equivalence_group_id": group,
                    "task_uuids": sorted(task_uuids),
                    "status": "failed",
                    "missing_task_uuids": missing,
                }
            )
            continue
        group_states = [states[task_uuid] for task_uuid in sorted(task_uuids)]
        extractor_versions = sorted(
            {state.get("extractor_version") for state in group_states}
        )
        if len(extractor_versions) != 1:
            failures.append(
                {
                    "group": group,
                    "reason": "mixed_extractor_versions",
                    "versions": extractor_versions,
                }
            )
        non_success = [
            state["task_uuid"]
            for state in group_states
            if state.get("status") != "success"
        ]
        if non_success:
            failures.append(
                {"group": group, "reason": "non_success_state", "tasks": non_success}
            )
            continue

        common = set.intersection(
            *(set(state["features"]) for state in group_states)
        )
        invariant_checks = {}
        basis_values = {}
        changed_basis_features = []
        for column in sorted(common):
            metadata = metadata_for_column(column)
            if not metadata.model_eligible:
                continue
            values = [state["features"][column] for state in group_states]
            if metadata.representation == "INV":
                passed = all(
                    _close(values[0], value, args.rtol, args.atol)
                    for value in values[1:]
                )
                invariant_checks[column] = {"values": values, "passed": passed}
                if not passed:
                    failures.append(
                        {
                            "group": group,
                            "reason": "invariant_feature_changed",
                            "column": column,
                            "values": values,
                        }
                    )
            elif metadata.representation in {"BAS", "BAS+ORD", "GAUGE"}:
                basis_values[column] = values
                if any(
                    not _close(values[0], value, args.rtol, args.atol)
                    for value in values[1:]
                ):
                    changed_basis_features.append(column)
        if not changed_basis_features:
            failures.append(
                {
                    "group": group,
                    "reason": "no_representation_sensitive_feature_changed",
                }
            )
        reports.append(
            {
                "equivalence_group_id": group,
                "task_uuids": [state["task_uuid"] for state in group_states],
                "extractor_versions": extractor_versions,
                "status": (
                    "passed"
                    if len(extractor_versions) == 1
                    and all(item["passed"] for item in invariant_checks.values())
                    and changed_basis_features
                    else "failed"
                ),
                "invariant_checks": invariant_checks,
                "basis_feature_values": basis_values,
                "changed_basis_features": changed_basis_features,
            }
        )

    payload = {
        "check": "g40_p1a_g21_representation_pairs",
        "rtol": args.rtol,
        "atol": args.atol,
        "equivalence_groups": len(groups),
        "groups_passed": sum(report["status"] == "passed" for report in reports),
        "status": "passed" if not failures else "failed",
        "reports": reports,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "equivalence_groups": payload["equivalence_groups"],
                "groups_passed": payload["groups_passed"],
                "failures": len(failures),
            },
            sort_keys=True,
        )
    )
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
