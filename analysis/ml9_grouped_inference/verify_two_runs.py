#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from qb_gsee_benchmark.ml.core_set import sha256_file, stable_json_dump


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "analysis/ml9_grouped_inference/execution_contract_v1.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--promote", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    arguments = parser.parse_args()

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected = sorted(contract["outputs"]["required_files"])
    files_1 = sorted(path.name for path in arguments.run_1.iterdir() if path.is_file())
    files_2 = sorted(path.name for path in arguments.run_2.iterdir() if path.is_file())
    if files_1 != expected or files_2 != expected:
        raise ValueError("ML-9D run tree does not match the frozen output contract")

    hashes = {}
    for name in expected:
        first = arguments.run_1 / name
        second = arguments.run_2 / name
        if first.read_bytes() != second.read_bytes():
            raise ValueError(f"ML-9D two-run byte mismatch: {name}")
        hashes[name] = sha256_file(first)

    manifest = json.loads(
        (arguments.run_1 / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    report = json.loads((arguments.run_1 / "report.json").read_text(encoding="utf-8"))
    gate = json.loads(
        (arguments.run_1 / "target_gate_evidence.json").read_text(encoding="utf-8")
    )
    if manifest["status"] != "complete_internal_descriptive_inference":
        raise ValueError("ML-9D manifest is incomplete")
    if report["status"] != "complete_internal_descriptive_inference":
        raise ValueError("ML-9D report is incomplete")
    if gate["status"] != "pass_target_access_authorized":
        raise ValueError("ML-9D target gate did not pass")
    if manifest["promotion_eligible_after_two_run_identity"] is not True:
        raise ValueError("ML-9D manifest is not promotion eligible")
    if arguments.promote.exists():
        raise ValueError(f"ML-9D promotion destination exists: {arguments.promote}")

    shutil.copytree(arguments.run_1, arguments.promote)
    identity = {
        "artifact_id": "ml9d_grouped_inference_two_run_identity_v1",
        "status": "pass",
        "byte_identical": True,
        "file_count": len(expected),
        "relative_paths": expected,
        "file_hashes": hashes,
        "target_gate_passed": True,
        "run_1": str(arguments.run_1.relative_to(ROOT)),
        "run_2": str(arguments.run_2.relative_to(ROOT)),
        "promoted": str(arguments.promote.relative_to(ROOT)),
    }
    stable_json_dump(identity, arguments.identity)
    print(
        "ML9D_TWO_RUN_IDENTITY_PASS "
        f"files={len(expected)} manifest={hashes['artifact_manifest.json']}"
    )


if __name__ == "__main__":
    main()
