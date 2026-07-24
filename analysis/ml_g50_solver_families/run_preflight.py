#!/usr/bin/env python3
"""Run the frozen G50 solver-family outcome-blind preflight."""

from pathlib import Path

from qb_gsee_benchmark.ml.g50_solver_families import run_outcome_blind_preflight

ROOT = Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    report = run_outcome_blind_preflight(
        ROOT,
        ROOT / "analysis/ml_g50_solver_families/preregistration.json",
        ROOT / "analysis/ml_g50_solver_families/preflight",
    )
    print(
        "ML_G50_PREFLIGHT_OK"
        f" tasks={report['panel']['corpus_tasks']}"
        f" selected={report['panel']['selected_tasks']}"
        f" families={report['panel']['canonical_families']}"
        f" solver_families={report['panel']['analysis_solver_families']}"
        f" variants={report['panel']['analysis_variants']}"
        f" features={report['feature_census']['selected']}"
    )
