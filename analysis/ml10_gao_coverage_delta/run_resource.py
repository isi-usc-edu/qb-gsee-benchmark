#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.pyscf_gao_delta import prepare_gao_delta_data
from qb_gsee_benchmark.ml.pyscf_hardness_run import run_resource_finalization


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = Path(__file__).with_name("preregistration.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    data = prepare_gao_delta_data(ROOT, PREREGISTRATION)
    report = run_resource_finalization(
        ROOT,
        PREREGISTRATION,
        arguments.output_dir,
        prepared_data=data,
        artifact_version=3,
    )
    print(
        "ML10_GAO_RESOURCE_COMPLETE "
        f"attempted={report['pyscf_panel_attempted_cells']} "
        f"cost_screened={report['pyscf_panel_cost_screened_cells']} "
        f"no_coverage={report['pyscf_panel_no_coverage_cells']}"
    )


if __name__ == "__main__":
    main()
