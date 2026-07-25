#!/usr/bin/env python
"""Run the ML-8C gradeable-mask sensitivity annex to the G50 final_v4 analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.g50_gradeable_mask_sensitivity import (
    run_gradeable_mask_sensitivity,
)

DEFAULT_PREREGISTRATION = Path(
    "analysis/ml_g50_solver_families/sensitivity_preregistration_gradeable_mask.json"
)
DEFAULT_OUTPUT = Path(
    "analysis/ml_g50_solver_families/sensitivity_gradeable_mask_v1"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--preregistration", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()

    root = arguments.root.resolve()
    preregistration = arguments.preregistration or (root / DEFAULT_PREREGISTRATION)
    output = arguments.output or (root / DEFAULT_OUTPUT)

    result = run_gradeable_mask_sensitivity(root, preregistration, output)
    report = result["report"]
    print(
        json.dumps(
            {
                "status": report["status"],
                "panel": report["panel"],
                "gradeable_population": {
                    key: report["gradeable_population"][key]
                    for key in (
                        "gradeable_population_total",
                        "gradeable_population_covered",
                        "gradeable_population_orphaned",
                        "restated_weight_sum",
                        "max_restated_weight",
                    )
                },
                "parent_signals": report["parent_signals"],
                "signals": report["signals"],
                "negative_verdict_survives_decontamination": report[
                    "negative_verdict_survives_decontamination"
                ],
                "stop_at_triggered": report["stop_at_triggered"],
                "eligibility_changes": report["eligibility_changes"],
                "equivalence_guard": report["equivalence_guard"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
