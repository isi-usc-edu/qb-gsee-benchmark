#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.g50_solver_families_run import run_finalization

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_finalization(
        ROOT,
        ROOT / "analysis/ml_g50_solver_families/preregistration.json",
        ROOT / "analysis/ml_g50_solver_families/amendment_size_sector_backfill.json",
        ROOT / "analysis/ml_g50_solver_families/amendment_rung_ledger_recovery.json",
        arguments.output,
    )
    panel = report["panel"]
    print(
        "ML_G50_COMPLETE "
        f"labels={panel['normalized_labels']} "
        f"eligible_variants={panel['eligible_variants']} "
        f"predictions={panel['prediction_rows']}"
    )


if __name__ == "__main__":
    main()
