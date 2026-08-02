#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.pyscf_sparse_irt_artifacts import run_sparse_finalization


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml10_pyscf_hardness/preregistration.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tune", type=int)
    parser.add_argument("--draws", type=int)
    arguments = parser.parse_args()
    report = run_sparse_finalization(
        ROOT,
        PREREGISTRATION,
        arguments.output_dir,
        tune=arguments.tune,
        draws=arguments.draws,
    )
    print(
        "ML10C_FINALIZATION_COMPLETE "
        f"tasks={report['panel_tasks']} "
        f"items={report['items']} "
        f"observed={report['observed_response_cells']} "
        f"diagnostics_pass={report['all_sampler_diagnostics_pass']}"
    )


if __name__ == "__main__":
    main()
