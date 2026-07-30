#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.g59_frontend_bundle import (
    verify_frontend_archive,
    verify_g59_frontend_bundle,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    arguments = parser.parse_args()
    report = verify_g59_frontend_bundle(arguments.bundle)
    if arguments.archive is not None:
        report["archive"] = verify_frontend_archive(arguments.bundle, arguments.archive)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
