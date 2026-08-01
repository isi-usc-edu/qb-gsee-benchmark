#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.bayesian_irt_run import run_finalization


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_bayesian_irt/preregistration.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_finalization(ROOT, PREREGISTRATION, arguments.output_dir)
    print(
        "ML9C_FINALIZATION_COMPLETE "
        f"tasks={report['panel_tasks']} "
        f"variants={report['solver_variants']} "
        f"diagnostics_pass={report['all_sampler_diagnostics_pass']}"
    )


if __name__ == "__main__":
    main()
