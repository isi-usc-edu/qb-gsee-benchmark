#!/usr/bin/env python
"""Run the ML-8D UQ solvability estimator and solvability-ratio v2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.solvability_uq import run_solvability_uq

DEFAULT_PREREGISTRATION = Path("analysis/ml_solvability_uq/preregistration.json")
DEFAULT_OUTPUT = Path("analysis/ml_solvability_uq/held_v1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--preregistration", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    arguments = parser.parse_args()

    root = arguments.root.resolve()
    preregistration = arguments.preregistration or (root / DEFAULT_PREREGISTRATION)
    output = arguments.output or (root / DEFAULT_OUTPUT)

    result = run_solvability_uq(root, preregistration, output)
    report = result["report"]
    print(
        json.dumps(
            {
                "status": report["status"],
                "panel": report["panel"],
                "design_track": report["design_track"],
                "model_track": {
                    key: report["model_track"][key]
                    for key in ("estimator", "ratio_range", "fallback_used_for_variants")
                },
                "calibration_gate": report["calibration_gate"],
                "stop_at": report["stop_at"],
                "kernel_psd_summary": report["kernel_psd_summary"],
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
