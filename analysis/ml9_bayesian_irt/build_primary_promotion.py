#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.bayesian_irt_primary_promotion import (
    build_primary_promotion,
)


ROOT = Path(__file__).resolve().parents[2]
AMENDMENT = ROOT / "analysis/ml9_bayesian_irt/primary_promotion_amendment_v1.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    report = build_primary_promotion(
        ROOT,
        AMENDMENT,
        arguments.source,
        arguments.output_dir,
    )
    print(
        "ML9C_PRIMARY_BUILD_PASS "
        f"tasks={report['panel_tasks']} scope={report['scope']}"
    )


if __name__ == "__main__":
    main()
