#!/usr/bin/env python3
"""Build ML-3's frozen pre-run manifest without fitting outcome models."""

from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.interim import stable_json_dump
from qb_gsee_benchmark.ml.interim_v2 import build_manifest_v2


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--output", type=Path, default=Path("analysis/ml_v2/manifest_v2.json")
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    stable_json_dump(build_manifest_v2(root), output)
    print(output)


if __name__ == "__main__":
    main()
