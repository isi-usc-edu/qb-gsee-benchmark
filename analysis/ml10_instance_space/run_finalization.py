#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.pyscf_instance_space_run import (
    run_instance_space_finalization,
)


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml10_pyscf_hardness/preregistration.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_instance_space_finalization(
        ROOT, PREREGISTRATION, arguments.output_dir
    )
    print(
        "ML10A_FINALIZATION_COMPLETE "
        f"panel_gates={report['panel_pythia_gates_passed']}/{report['panel_pythia_gates_total']} "
        f"external_gates={report['external_validation_gates_passed']}/{report['external_validation_gates_total']}"
    )


if __name__ == "__main__":
    main()
