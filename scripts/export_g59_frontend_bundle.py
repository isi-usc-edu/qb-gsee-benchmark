#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.g59_frontend_bundle import build_g59_frontend_bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    arguments = parser.parse_args()
    report = build_g59_frontend_bundle(
        arguments.root, arguments.output, archive_path=arguments.archive
    )
    print(
        "G59_FRONTEND_COMPLETE "
        f"files={report['files_verified']} "
        f"observations={report['observations_verified']} "
        f"predictions={report['predictions_verified']} "
        f"archive={report['archive']['archive_sha256']}"
    )


if __name__ == "__main__":
    main()
