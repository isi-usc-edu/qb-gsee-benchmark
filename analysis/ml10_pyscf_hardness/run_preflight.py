#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.pyscf_hardness_preflight import run_preflight


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml10_pyscf_hardness/preregistration.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_preflight(ROOT, PREREGISTRATION, arguments.output)
    census = report["census"]
    print(
        "ML10_PREFLIGHT_PASS "
        f"corpus_cells={census['corpus_cells']} "
        f"panel_coverage={census['covered_panel_tasks']}/{census['panel_tasks']} "
        f"flag_rows={census['epistemic_flag_rows']}"
    )


if __name__ == "__main__":
    main()
