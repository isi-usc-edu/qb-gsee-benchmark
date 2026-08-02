#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.ml11b_variant_ability import finalize_identical_runs
from qb_gsee_benchmark.ml.ml11c_frontend_extensions import (
    ANALYSIS_DIRECTORY,
    build_combined_addendum_run,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    analysis = root / ANALYSIS_DIRECTORY

    raw_runs = analysis / "raw_runs"
    first_run = raw_runs / "run_1"
    second_run = raw_runs / "run_2"
    final = analysis / "final_v1"
    identity = analysis / "two_run_identity_v1.json"

    first = build_combined_addendum_run(root, first_run)
    second = build_combined_addendum_run(root, second_run)
    promotion = finalize_identical_runs(
        first_run,
        second_run,
        final,
        identity,
        "ml11c_frontend_combined_addendum_two_run_identity_v1",
    )
    print(
        json.dumps(
            {
                "archive_sha256": first["archive"]["archive_sha256"],
                "final_manifest_sha256": first["run_manifest_sha256"],
                "index_sha256": first["index_sha256"],
                "run_2_archive_sha256": second["archive"]["archive_sha256"],
                "status": "pass",
                "two_run_identity_sha256": promotion["identity_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
