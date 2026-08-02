#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.pyscf_gao_delta import prepare_gao_delta_data
from qb_gsee_benchmark.ml.pyscf_hardness_run import run_desk_finalization


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = Path(__file__).with_name("preregistration.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    data = prepare_gao_delta_data(ROOT, PREREGISTRATION)
    report = run_desk_finalization(
        ROOT,
        PREREGISTRATION,
        arguments.output_dir,
        prepared_data=data,
        artifact_version=2,
    )
    print(
        "ML10_GAO_DESK_COMPLETE "
        f"union={report['pyscf_known_union_successes']} "
        f"unique={report['pyscf_union_unique_additions_beyond_ladder']}"
    )


if __name__ == "__main__":
    main()
