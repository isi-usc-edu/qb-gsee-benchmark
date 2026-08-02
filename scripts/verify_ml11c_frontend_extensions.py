#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.ml11_frontend_bundle import verify_ml11_archive
from qb_gsee_benchmark.ml.ml11c_frontend_extensions import (
    ANALYSIS_DIRECTORY,
    verify_combined_addendum,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    analysis = root / ANALYSIS_DIRECTORY
    final = analysis / "final_v1"
    bundle = final / "frontend_combined_addendum_v3_1"
    archive = final / "frontend_combined_addendum_v3_1.zip"
    identity_path = analysis / "two_run_identity_v1.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if identity.get("byte_identical") is not True or identity.get("status") != "pass":
        raise ValueError("ML-11c two-run identity did not pass")
    report = {
        "archive": verify_ml11_archive(bundle, archive),
        "bundle": verify_combined_addendum(bundle),
        "final_manifest_sha256": sha256_file(final / "artifact_manifest.json"),
        "two_run_identity_sha256": sha256_file(identity_path),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
