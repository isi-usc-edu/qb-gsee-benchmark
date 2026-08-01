#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.resource_profiles_run import run_finalization


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_resource_profiles/preregistration.json"
SCHEMA_BINDING = ROOT / "analysis/ml9_resource_profiles/schema_binding_raw_failure.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = run_finalization(
        ROOT,
        PREREGISTRATION,
        SCHEMA_BINDING,
        arguments.output,
    )
    census = manifest["census"]
    print(
        "ML9B_FINALIZATION_COMPLETE "
        f"attempted={census['attempted_cells']} "
        f"endpoints={census['resource_endpoint_rows']} "
        f"profiles={census['data_profile_rows']}"
    )


if __name__ == "__main__":
    main()
