#!/usr/bin/env python3
"""Verify a generated G50 solver-family frontend data handoff."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from qb_gsee_benchmark.ml.g50_frontend_bundle import (  # noqa: E402
    verify_frontend_archive,
    verify_frontend_bundle,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    report = verify_frontend_bundle(args.bundle)
    if args.archive is not None:
        report["archive"] = verify_frontend_archive(args.bundle, args.archive)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
