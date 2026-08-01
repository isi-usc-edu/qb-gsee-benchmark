#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.grouped_inference_run import run_grouped_inference


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_grouped_inference/preregistration.json"
EXECUTION_CONTRACT = ROOT / "analysis/ml9_grouped_inference/execution_contract_v1.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_grouped_inference(
        ROOT,
        PREREGISTRATION,
        EXECUTION_CONTRACT,
        arguments.output_dir.resolve(),
    )
    print(
        "ML9D_FINALIZATION_PASS "
        f"primary_rejections={report['bh_rejections_primary']} "
        f"secondary_rejections={report['bh_rejections_secondary']}"
    )


if __name__ == "__main__":
    main()
