#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.g50_solver_families_run import verify_and_promote_two_runs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--promoted", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    arguments = parser.parse_args()
    report = verify_and_promote_two_runs(
        arguments.first,
        arguments.second,
        arguments.promoted,
        arguments.identity,
        artifact_id="ml_g59_solver_family_two_run_identity_v1",
    )
    print(
        "ML_G59_TWO_RUN_IDENTITY "
        f"files={report['file_count']} "
        f"manifest={report['promoted_bundle_manifest_sha256']}"
    )


if __name__ == "__main__":
    main()
