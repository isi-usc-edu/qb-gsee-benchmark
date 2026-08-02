#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.ml11b_variant_ability import (
    ANALYSIS_DIRECTORY,
    build_addendum_run,
    build_scoped_variant_ability,
    finalize_identical_runs,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    analysis = root / ANALYSIS_DIRECTORY

    promotion_runs = analysis / "promotion_raw_runs"
    promotion_run_1 = promotion_runs / "run_1"
    promotion_run_2 = promotion_runs / "run_2"
    promotion_final = analysis / "final_v1"
    promotion_identity = analysis / "two_run_identity_promotion_v1.json"
    build_scoped_variant_ability(
        root,
        root / "analysis/ml9_bayesian_irt/raw_runs/run_1",
        promotion_run_1,
    )
    build_scoped_variant_ability(
        root,
        root / "analysis/ml9_bayesian_irt/raw_runs/run_2",
        promotion_run_2,
    )
    promotion_report = finalize_identical_runs(
        promotion_run_1,
        promotion_run_2,
        promotion_final,
        promotion_identity,
        "ml11b_variant_ability_two_run_identity_v1",
    )

    addendum_runs = analysis / "addendum_raw_runs"
    addendum_run_1 = addendum_runs / "run_1"
    addendum_run_2 = addendum_runs / "run_2"
    addendum_final = analysis / "frontend_addendum_final_v1"
    addendum_identity = analysis / "two_run_identity_addendum_v1.json"
    first = build_addendum_run(root, promotion_final, addendum_run_1)
    second = build_addendum_run(root, promotion_final, addendum_run_2)
    addendum_report = finalize_identical_runs(
        addendum_run_1,
        addendum_run_2,
        addendum_final,
        addendum_identity,
        "ml11b_frontend_addendum_two_run_identity_v1",
    )
    print(
        json.dumps(
            {
                "addendum": addendum_report,
                "archive_sha256": first["archive"]["archive_sha256"],
                "index_sha256": first["index_sha256"],
                "promotion": promotion_report,
                "run_2_archive_sha256": second["archive"]["archive_sha256"],
                "status": "pass",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
