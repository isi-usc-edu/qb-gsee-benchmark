#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.g50_solver_families_run import run_finalization
from qb_gsee_benchmark.ml.g59_panel_refresh import (
    load_g59_panel_refresh,
    panel_refresh_analysis_revision,
)

ROOT = Path(__file__).resolve().parents[2]
G50 = ROOT / "analysis/ml_g50_solver_families"
AMENDMENT = ROOT / "analysis/ml_g59_panel_refresh/amendment_post_g59_panel_refresh.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    bundle = load_g59_panel_refresh(ROOT, AMENDMENT, require_complete=True)
    report = run_finalization(
        ROOT,
        G50 / "preregistration.json",
        G50 / "amendment_size_sector_backfill.json",
        G50 / "amendment_rung_ledger_recovery.json",
        G50 / "amendment_trimci_bounded_rung_semantics.json",
        arguments.output,
        normalized_override=(bundle["observations"], bundle["coverage"]),
        selection_weights_override=bundle["selection_weights"],
        analysis_revision=panel_refresh_analysis_revision(bundle),
    )
    panel = report["panel"]
    print(
        "ML_G59_COMPLETE "
        f"labels={panel['normalized_labels']} "
        f"eligible_variants={panel['eligible_variants']} "
        f"predictions={panel['prediction_rows']} "
        f"selection_weight_sum={panel['selection_weight_sum']}"
    )


if __name__ == "__main__":
    main()
