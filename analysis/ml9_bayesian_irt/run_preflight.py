#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from qb_gsee_benchmark.ml.bayesian_irt import run_outcome_blind_preflight


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_bayesian_irt/preregistration.json"
OUTPUT = ROOT / "analysis/ml9_bayesian_irt/preflight_v1"


def main() -> None:
    report = run_outcome_blind_preflight(ROOT, PREREGISTRATION, OUTPUT)
    census = report["census"]
    print(
        "ML9C_PREFLIGHT_PASS "
        f"tasks={census['panel_tasks']} "
        f"task_families={census['canonical_task_families']} "
        f"variants={census['solver_variants']} "
        f"cells={census['observation_rows_by_line_count_only']}"
    )


if __name__ == "__main__":
    main()
