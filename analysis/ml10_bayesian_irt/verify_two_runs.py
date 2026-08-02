#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from qb_gsee_benchmark.ml.core_set import _require, sha256_file, stable_json_dump
from qb_gsee_benchmark.ml.pyscf_sparse_irt_artifacts import REQUIRED_FILES


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--promoted", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    arguments = parser.parse_args()
    expected = sorted(REQUIRED_FILES)
    files_first = sorted(path.name for path in arguments.first.iterdir() if path.is_file())
    files_second = sorted(path.name for path in arguments.second.iterdir() if path.is_file())
    _require(files_first == expected and files_second == expected, "ML-10C run tree changed")
    hashes = {}
    for name in expected:
        first = arguments.first / name
        second = arguments.second / name
        _require(first.read_bytes() == second.read_bytes(), f"ML-10C two-run mismatch: {name}")
        hashes[name] = sha256_file(first)
    report = json.loads((arguments.first / "report.json").read_text(encoding="utf-8"))
    promotion_eligible = bool(report["all_sampler_diagnostics_pass"])
    _require(not arguments.promoted.exists(), "ML-10C promoted directory already exists")
    if promotion_eligible:
        shutil.copytree(arguments.first, arguments.promoted)
    identity = {
        "artifact_id": "ml10c_sparse_bayesian_irt_two_run_identity_v1",
        "status": "pass_promoted" if promotion_eligible else "pass_nonpromotion_diagnostic_failure",
        "byte_identical": True,
        "file_count": len(expected),
        "relative_paths": expected,
        "file_hashes": hashes,
        "run_1": str(arguments.first.relative_to(ROOT)),
        "run_2": str(arguments.second.relative_to(ROOT)),
        "promoted": str(arguments.promoted.relative_to(ROOT)) if promotion_eligible else None,
        "promotion_eligible": promotion_eligible,
        "promotion_performed": promotion_eligible,
    }
    stable_json_dump(identity, arguments.identity)
    print(f"ML10C_TWO_RUN_IDENTITY_PASS files={len(expected)} promoted={promotion_eligible}")


if __name__ == "__main__":
    main()
