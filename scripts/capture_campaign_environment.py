#!/usr/bin/env python3
"""Capture and validate the isolated Python environment for a campaign stage."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import site
from pathlib import Path


PACKAGES = ("numpy", "scipy", "pyscf")
THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")


def capture(stage: str) -> dict[str, object]:
    package_versions = {
        package: importlib.metadata.version(package) for package in PACKAGES
    }
    payload: dict[str, object] = {
        "schema_version": 1,
        "stage": stage,
        "python": platform.python_version(),
        "packages": package_versions,
        "python_executable": os.path.realpath(os.sys.executable),
        "python_no_user_site": os.environ.get("PYTHONNOUSERSITE"),
        "user_site_enabled": bool(site.ENABLE_USER_SITE),
        "thread_environment": {
            variable: os.environ.get(variable) for variable in THREAD_VARIABLES
        },
    }
    if payload["python_no_user_site"] != "1" or payload["user_site_enabled"]:
        raise RuntimeError(
            "campaign environment is not isolated: require PYTHONNOUSERSITE=1 "
            "with the user site disabled"
        )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = capture(args.stage)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
