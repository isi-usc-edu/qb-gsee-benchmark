#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.bayesian_irt_primary_promotion import (
    verify_and_promote_primary,
)


ROOT = Path(__file__).resolve().parents[2]
AMENDMENT = ROOT / "analysis/ml9_bayesian_irt/primary_promotion_amendment_v1.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--promote", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    arguments = parser.parse_args()
    identity = verify_and_promote_primary(
        ROOT,
        AMENDMENT,
        arguments.run_1,
        arguments.run_2,
        arguments.promote,
        arguments.identity,
    )
    print(
        "ML9C_PRIMARY_TWO_RUN_IDENTITY_PASS "
        f"files={identity['file_count']} "
        f"manifest={identity['promoted_manifest_sha256']}"
    )


if __name__ == "__main__":
    main()
