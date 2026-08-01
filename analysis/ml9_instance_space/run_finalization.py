#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.instance_space_run import run_finalization


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_instance_space/preregistration.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = run_finalization(ROOT, PREREGISTRATION, arguments.output)
    census = manifest["census"]
    print(
        "ML9A_FINALIZATION_COMPLETE "
        f"panel={census['panel_tasks']} "
        f"corpus={census['corpus_tasks']} "
        f"projection_features={census['projection_features']} "
        f"bootstrap={census['bootstrap_replicates']}"
    )


if __name__ == "__main__":
    main()
