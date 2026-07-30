#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.g59_solvability_uq import run_g59_solvability_uq

ROOT = Path(__file__).resolve().parents[2]
AMENDMENT = ROOT / "analysis/ml_g59_solvability_uq/amendment_post_g59_uq.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = run_g59_solvability_uq(ROOT, AMENDMENT, arguments.output)
    report = result["report"]
    print(
        "ML_G59_UQ_COMPLETE "
        f"variants={report['panel']['variants']} "
        f"panel_tasks={report['panel']['training_panel_tasks']} "
        f"weight_sum={report['analysis_revision']['design_population']['restated_weight_sum']} "
        f"gate_passed={report['calibration_gate']['passed_count']}"
    )


if __name__ == "__main__":
    main()
