#!/usr/bin/env python3
"""Verify the G-33 O5 threshold classes for all Simons H-chain tasks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from generate_simons_hydrogen_chain_thresholds import (
    EXPECTED_COUNTS,
    INSTANCE,
    THRESHOLDS_HARTREE,
)


def main() -> int:
    payload = json.loads(INSTANCE.read_text())
    counts = {size: 0 for size in THRESHOLDS_HARTREE}
    errors: list[dict[str, Any]] = []
    for task in payload.get("tasks", []):
        size = task.get("independent_parameters", {}).get("n_hydrogen")
        requirements = task.get("requirements", {})
        if size not in THRESHOLDS_HARTREE:
            errors.append(
                {"task_uuid": task.get("task_uuid"), "unsupported_size": size}
            )
            continue
        counts[size] += 1
        actual = requirements.get("absolute_accuracy_threshold")
        units = requirements.get("absolute_accuracy_threshold_energy_units")
        if actual != THRESHOLDS_HARTREE[size] or units != "Hartree":
            errors.append(
                {
                    "task_uuid": task.get("task_uuid"),
                    "n_hydrogen": size,
                    "expected_hartree": THRESHOLDS_HARTREE[size],
                    "actual": actual,
                    "units": units,
                }
            )
    passed = counts == EXPECTED_COUNTS and not errors
    report = {
        "status": "pass" if passed else "fail",
        "checks": [
            {
                "name": "h_chain_thresholds_match_o5_classes",
                "passed": passed,
                "detail": {
                    "counts": counts,
                    "expected_counts": EXPECTED_COUNTS,
                    "thresholds_hartree": THRESHOLDS_HARTREE,
                    "errors": errors,
                },
            }
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
