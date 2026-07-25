#!/usr/bin/env python
"""Run the ML-8B / ML-5c gradeable-eligible core-set reselection (held)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.core_set_v2_gradeable import run_ml5c_reselection

DEFAULT_AMENDMENT = Path(
    "analysis/ml_core_set_v2/amendment_ml5c_gradeable_reselection.json"
)
DEFAULT_OUTPUT = Path("analysis/ml_core_set_v2/held_v1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--amendment", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()

    root = arguments.root.resolve()
    amendment = arguments.amendment or (root / DEFAULT_AMENDMENT)
    output = arguments.output or (root / DEFAULT_OUTPUT)

    result = run_ml5c_reselection(root, amendment, output)
    report = result["report"]
    print(
        json.dumps(
            {
                "status": report["status"],
                "binding_selection": report["binding_selection"],
                "manifest_of_record_unchanged": report["manifest_of_record_unchanged"],
                "candidates": report["candidates"],
                "metric": {
                    key: report["metric"][key]
                    for key in ("n_columns", "n_eligible", "n_jw", "applicability_blocks")
                },
                "modes": report["modes"],
                "weight_sets": report["weight_sets"],
                "sensitivity_193_columns": {
                    key: report["sensitivity_193_columns"][key]
                    for key in ("n_columns", "n_jw", "overlap_count", "overlap_fraction")
                },
                "deployment_target_layer": report["deployment_target_layer"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
