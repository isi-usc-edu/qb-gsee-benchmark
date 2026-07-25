#!/usr/bin/env python
"""Build the ML-8A corpus-wide gradeability census (held artifact)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.gradeability_census import build_census

DEFAULT_PREREGISTRATION = Path("analysis/ml_gradeability_census/preregistration.json")
DEFAULT_OUTPUT = Path("analysis/ml_gradeability_census/held_v1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--preregistration", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()

    root = arguments.root.resolve()
    preregistration = arguments.preregistration or (root / DEFAULT_PREREGISTRATION)
    output = arguments.output or (root / DEFAULT_OUTPUT)

    result = build_census(root, preregistration, output)
    report = result["report"]
    print(
        json.dumps(
            {
                "status": report["status"],
                "totals": report["totals"],
                "reason_counts": report["reason_counts"],
                "panel_cross_check": {
                    "evaluated": report["panel_cross_check"].get("evaluated"),
                    "observed": report["panel_cross_check"].get("observed"),
                    "prediction_confirmed": report["panel_cross_check"].get(
                        "prediction_confirmed"
                    ),
                },
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
