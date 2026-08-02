#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.pyscf_gao_delta import prepare_gao_delta_data
from qb_gsee_benchmark.ml.pyscf_instance_space_run import (
    run_instance_space_finalization,
)


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = Path(__file__).with_name("preregistration.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int)
    arguments = parser.parse_args()
    data = prepare_gao_delta_data(ROOT, PREREGISTRATION)
    report = run_instance_space_finalization(
        ROOT,
        PREREGISTRATION,
        arguments.output_dir,
        bootstrap_replicates=arguments.bootstrap_replicates,
        prepared_data=data,
        artifact_version=3,
    )
    print(
        "ML10_GAO_ISA_COMPLETE "
        f"panel={report['covered_panel_tasks']}/{report['panel_tasks']} "
        f"corpus={report['covered_corpus_tasks']}/{report['corpus_tasks']} "
        f"bootstrap={report['bootstrap_replicates']}"
    )


if __name__ == "__main__":
    main()
