#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from qb_gsee_benchmark.ml.ml11_frontend_bundle import finalize_ml11_frontend_runs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-1", type=Path, required=True)
    parser.add_argument("--run-2", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    arguments = parser.parse_args()
    report = finalize_ml11_frontend_runs(
        arguments.run_1,
        arguments.run_2,
        arguments.final,
        arguments.identity,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
