#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from qb_gsee_benchmark.ml.ml11_frontend_bundle import build_ml11_frontend_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run-directory", type=Path, required=True)
    arguments = parser.parse_args()
    report = build_ml11_frontend_run(arguments.root, arguments.run_directory)
    print(
        "ML11_FRONTEND_EXPORT_COMPLETE "
        f"files={report['files_verified']} "
        f"index={report['index_sha256']} "
        f"archive={report['archive']['archive_sha256']}"
    )


if __name__ == "__main__":
    main()
