#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from qb_gsee_benchmark.ml.resource_profiles import run_outcome_blind_preflight


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_resource_profiles/preregistration.json"
OUTPUT = ROOT / "analysis/ml9_resource_profiles/preflight_v1"


def main() -> None:
    report = run_outcome_blind_preflight(ROOT, PREREGISTRATION, OUTPUT)
    census = report["census"]
    print(
        "ML9B_PREFLIGHT_PASS "
        f"tasks={census['panel_tasks']} "
        f"variants={census['solver_variants']} "
        f"profiled={census['profiled_variants']} "
        f"companions={census['companion_variants']}"
    )


if __name__ == "__main__":
    main()
