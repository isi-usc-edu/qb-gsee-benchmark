#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from qb_gsee_benchmark.ml.core_set import sha256_file, stable_json_dump


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_bayesian_irt/preregistration.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--promote", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    arguments = parser.parse_args()

    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    expected = sorted(preregistration["outputs"]["required_files"])
    files_1 = sorted(path.name for path in arguments.run_1.iterdir() if path.is_file())
    files_2 = sorted(path.name for path in arguments.run_2.iterdir() if path.is_file())
    if files_1 != expected or files_2 != expected:
        raise ValueError("ML-9C run tree does not match the frozen output contract")
    hashes = {}
    for name in expected:
        first = arguments.run_1 / name
        second = arguments.run_2 / name
        if first.read_bytes() != second.read_bytes():
            raise ValueError(f"ML-9C two-run byte mismatch: {name}")
        hashes[name] = sha256_file(first)

    if arguments.promote.exists():
        shutil.rmtree(arguments.promote)
    shutil.copytree(arguments.run_1, arguments.promote)
    identity = {
        "artifact_id": "ml9c_bayesian_inverted_irt_two_run_identity_v1",
        "status": "pass",
        "byte_identical": True,
        "file_count": len(expected),
        "relative_paths": expected,
        "file_hashes": hashes,
        "run_1": str(arguments.run_1.relative_to(ROOT)),
        "run_2": str(arguments.run_2.relative_to(ROOT)),
        "promoted": str(arguments.promote.relative_to(ROOT)),
    }
    stable_json_dump(identity, arguments.identity)
    print(
        "ML9C_TWO_RUN_IDENTITY_PASS "
        f"files={len(expected)} manifest={hashes['artifact_manifest.json']}"
    )


if __name__ == "__main__":
    main()
