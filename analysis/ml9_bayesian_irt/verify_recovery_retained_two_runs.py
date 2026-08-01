#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.core_set import sha256_file, stable_json_dump


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_bayesian_irt/recovery_preregistration_v2.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    arguments = parser.parse_args()
    run_1 = arguments.run_1.resolve()
    run_2 = arguments.run_2.resolve()

    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    expected = sorted(preregistration["outputs"]["required_files"])
    files_1 = sorted(path.name for path in run_1.iterdir() if path.is_file())
    files_2 = sorted(path.name for path in run_2.iterdir() if path.is_file())
    if files_1 != expected or files_2 != expected:
        raise ValueError("retained ML-9C recovery tree does not match the contract")

    hashes = {}
    for name in expected:
        first = run_1 / name
        second = run_2 / name
        if first.read_bytes() != second.read_bytes():
            raise ValueError(f"retained ML-9C recovery byte mismatch: {name}")
        hashes[name] = sha256_file(first)

    report = json.loads((run_1 / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (run_1 / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    if report["status"] != "retained_internal_recovery_diagnostic_failure":
        raise ValueError("retained ML-9C recovery report has the wrong status")
    if manifest["status"] != "retained_internal_recovery_diagnostic_failure":
        raise ValueError("retained ML-9C recovery manifest has the wrong status")
    if report["all_recovery_diagnostics_pass"] is not False:
        raise ValueError("retained ML-9C recovery report unexpectedly passed")
    if manifest["all_recovery_diagnostics_pass"] is not False:
        raise ValueError("retained ML-9C recovery manifest unexpectedly passed")
    handoff = run_1 / "difficulty_handoff_ml9d.csv"
    if (
        sha256_file(handoff)
        != preregistration["binary_rasch"]["required_handoff_sha256"]
    ):
        raise ValueError("retained ML-9C recovery changed the healthy binary handoff")
    if (ROOT / "analysis/ml9_bayesian_irt/final_v1").exists():
        raise ValueError("failed ML-9C recovery must not have a promoted final_v1")

    identity = {
        "artifact_id": "ml9c_identified_recovery_retained_identity_v2",
        "status": "pass_retained_nonpromotion",
        "byte_identical": True,
        "file_count": len(expected),
        "relative_paths": expected,
        "file_hashes": hashes,
        "binary_handoff_unchanged": True,
        "all_recovery_diagnostics_pass": False,
        "promotion_block": "identified recovery sampler diagnostics failed",
        "run_1": str(run_1.relative_to(ROOT)),
        "run_2": str(run_2.relative_to(ROOT)),
        "promoted": None,
    }
    stable_json_dump(identity, arguments.identity)
    print(
        "ML9C_RECOVERY_RETAINED_IDENTITY_PASS "
        f"files={len(expected)} manifest={hashes['artifact_manifest.json']}"
    )


if __name__ == "__main__":
    main()
