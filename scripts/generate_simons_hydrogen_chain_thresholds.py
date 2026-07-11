#!/usr/bin/env python3
"""Apply the ratified O5 accuracy classes to the Simons H-chain tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTANCE = (
    ROOT
    / "problem_instances"
    / "hydrogen_chains"
    / (
        "problem_instance.simons_hydrogen_chains."
        "bd0915d5-f7d5-5266-8b3e-f40028110f7b.json"
    )
)
THRESHOLDS_HARTREE = {
    10: 0.00159362,
    30: 0.003,
    50: 0.005,
}
EXPECTED_COUNTS = {10: 20, 30: 10, 50: 10}


def apply_thresholds(payload: dict[str, Any]) -> dict[int, int]:
    if payload.get("short_name") != "simons_hydrogen_chains":
        raise ValueError("unexpected problem instance")
    counts = {size: 0 for size in THRESHOLDS_HARTREE}
    for task in payload.get("tasks", []):
        size = task.get("independent_parameters", {}).get("n_hydrogen")
        if size not in THRESHOLDS_HARTREE:
            raise ValueError(f"unsupported H-chain size: {size!r}")
        requirements = task.get("requirements")
        if not isinstance(requirements, dict):
            raise ValueError(f"task {task.get('task_uuid')} lacks requirements")
        requirements["absolute_accuracy_threshold"] = THRESHOLDS_HARTREE[size]
        requirements["absolute_accuracy_threshold_energy_units"] = "Hartree"
        counts[size] += 1
    if counts != EXPECTED_COUNTS:
        raise ValueError(f"unexpected H-chain class counts: {counts}")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", type=Path, default=INSTANCE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.instance.read_text())
    before = args.instance.read_text()
    counts = apply_thresholds(payload)
    rendered = json.dumps(payload, indent=2) + "\n"
    changed = rendered != before
    if args.check and changed:
        raise RuntimeError(f"threshold regeneration would change {args.instance}")
    if not args.check:
        args.instance.write_text(rendered)
    print(
        json.dumps(
            {
                "status": "current" if not changed else "updated",
                "instance": str(args.instance.relative_to(ROOT)),
                "counts": counts,
                "thresholds_hartree": THRESHOLDS_HARTREE,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
