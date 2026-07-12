#!/usr/bin/env python3
"""Run ML-2 strictly from the already committed ML-1 manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from qb_gsee_benchmark.ml.interim_runner import run_interim_evaluation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--manifest", type=Path, default=Path("analysis/ml_v2/manifest.json")
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    manifest = args.manifest if args.manifest.is_absolute() else repo_root / args.manifest
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(manifest.relative_to(repo_root))],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if tracked.returncode:
        raise SystemExit("Manifest must be committed before any scored evaluation")
    dirty = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", str(manifest.relative_to(repo_root))],
        cwd=repo_root,
    )
    if dirty.returncode:
        raise SystemExit("Manifest differs from committed HEAD; refusing evaluation")
    print(json.dumps(run_interim_evaluation(repo_root, manifest), sort_keys=True))


if __name__ == "__main__":
    main()
