#!/usr/bin/env python3
"""Run ML-3 strictly from its already committed manifest_v2."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from qb_gsee_benchmark.ml.interim_v2_runner import run_interim_v2_evaluation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("analysis/ml_v2/manifest_v2.json")
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else root / args.manifest
    relative = str(manifest.relative_to(root))
    if subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=root,
        capture_output=True,
        text=True,
    ).returncode:
        raise SystemExit("manifest_v2 must be committed before any scored ML-3 run")
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", relative], cwd=root
    ).returncode:
        raise SystemExit("manifest_v2 differs from committed HEAD; refusing ML-3 run")
    print(json.dumps(run_interim_v2_evaluation(root, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
