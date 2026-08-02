#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.pyscf_hardness_run import run_resource_finalization


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml10_pyscf_hardness/preregistration.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_resource_finalization(ROOT, PREREGISTRATION, arguments.output_dir)
    print(
        "ML10B_FINALIZATION_COMPLETE "
        f"items={report['combined_items']} "
        f"pyscf_attempted={report['pyscf_panel_attempted_cells']}"
    )


if __name__ == "__main__":
    main()
