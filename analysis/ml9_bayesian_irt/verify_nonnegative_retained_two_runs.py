#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.core_set import sha256_file, stable_json_dump


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = (
    ROOT / "analysis/ml9_bayesian_irt/recovery_preregistration_v3.json"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    arguments = parser.parse_args()

    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    expected = sorted(preregistration["outputs"]["required_files"])
    files_1 = sorted(path.name for path in arguments.run_1.iterdir() if path.is_file())
    files_2 = sorted(path.name for path in arguments.run_2.iterdir() if path.is_file())
    if files_1 != expected or files_2 != expected:
        raise ValueError("retained ML-9C v3 tree does not match the output contract")

    hashes = {}
    for name in expected:
        first = arguments.run_1 / name
        second = arguments.run_2 / name
        if first.read_bytes() != second.read_bytes():
            raise ValueError(f"retained ML-9C v3 two-run byte mismatch: {name}")
        hashes[name] = sha256_file(first)

    report = json.loads((arguments.run_1 / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (arguments.run_1 / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    expected_status = "retained_internal_recovery_diagnostic_failure"
    if report.get("status") != expected_status:
        raise ValueError("retained ML-9C v3 report has the wrong status")
    if manifest.get("status") != expected_status:
        raise ValueError("retained ML-9C v3 manifest has the wrong status")
    if report.get("all_recovery_diagnostics_pass") is not False:
        raise ValueError("retained ML-9C v3 report unexpectedly passed diagnostics")
    if manifest.get("all_recovery_diagnostics_pass") is not False:
        raise ValueError("retained ML-9C v3 manifest unexpectedly passed diagnostics")

    identity = {
        "artifact_id": "ml9c_nonnegative_recovery_retained_identity_v3",
        "status": "pass_retained_not_promoted",
        "byte_identical": True,
        "promoted": False,
        "promotion_block": "one or more frozen recovery diagnostic gates failed",
        "file_count": len(expected),
        "relative_paths": expected,
        "file_hashes": hashes,
        "run_1": str(arguments.run_1.resolve().relative_to(ROOT)),
        "run_2": str(arguments.run_2.resolve().relative_to(ROOT)),
    }
    stable_json_dump(identity, arguments.identity)
    print(
        "ML9C_NONNEGATIVE_RETAINED_TWO_RUN_IDENTITY_PASS "
        f"files={len(expected)} manifest={hashes['artifact_manifest.json']} "
        "promoted=false"
    )


if __name__ == "__main__":
    main()
