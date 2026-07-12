#!/usr/bin/env python3
"""Build the frozen ML-v2 interim manifest without fitting any model."""

from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.interim import build_manifest, stable_json_dump


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output", type=Path, default=Path("analysis/ml_v2/manifest.json")
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else repo_root / args.output
    stable_json_dump(build_manifest(repo_root), output)
    print(output)


if __name__ == "__main__":
    main()
