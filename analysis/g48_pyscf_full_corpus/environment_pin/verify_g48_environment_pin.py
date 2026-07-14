#!/usr/bin/env python3
"""Verify the immutable G-48 PySCF pre-pilot environment pin."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import site
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PIN_PATH = Path(__file__).with_name("g48_environment_pin.json")
LOCK_PATH = Path(__file__).with_name("requirements.lock")
MANIFEST_PATH = Path(__file__).with_name("g48_environment_pin_bundle_manifest.json")
sys.path.insert(0, str(REPO_ROOT / "src"))

import h5py
import numpy
import pyscf
import scipy

from qb_gsee_benchmark.solvers import pyscf_adapter


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict[str, object]:
    pin = json.loads(PIN_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    checks: dict[str, bool] = {}

    checks["campaign_id"] = pin["campaign_id"] == pyscf_adapter.G48_METHOD_CAMPAIGN
    checks["adapter_version"] = (
        pin["adapter"]["version"] == pyscf_adapter.ADAPTER_VERSION
    )
    checks["legacy_campaign_rejected"] = (
        pin["adapter"]["rejected_legacy_campaign"]
        == pyscf_adapter.LEGACY_METHOD_CAMPAIGN
    )
    for relative_path, expected_sha in pin["repository"]["source_sha256"].items():
        checks[f"source_sha256:{relative_path}"] = (
            _sha256(REPO_ROOT / relative_path) == expected_sha
        )

    runtime = pin["runtime"]
    checks["python"] = platform.python_version() == runtime["python"]
    checks["python_implementation"] = (
        platform.python_implementation() == runtime["python_implementation"]
    )
    checks["python_compiler"] = platform.python_compiler() == runtime["python_compiler"]
    checks["platform"] = platform.platform() == runtime["platform"]
    isolation = runtime["isolation"]
    checks["python_user_site_disabled"] = (
        site.ENABLE_USER_SITE is isolation["python_user_site"]
    )
    checks["python_no_user_site_environment"] = (
        os.environ.get("PYTHONNOUSERSITE")
        == isolation["required_environment"]["PYTHONNOUSERSITE"]
    )
    modules = {
        "h5py": h5py,
        "numpy": numpy,
        "pyscf": pyscf,
        "scipy": scipy,
    }
    prefix = Path(sys.prefix).resolve()
    for package, module in modules.items():
        checks[f"package:{package}"] = (
            module.__version__ == runtime["packages"][package]
        )
        checks[f"package_origin:{package}"] = (
            Path(module.__file__).resolve().is_relative_to(prefix)
        )
    legacy_linalg = getattr(numpy.linalg, "linalg", None)
    checks["numpy_pyscf_diis_compatibility"] = (
        legacy_linalg is not None
        and legacy_linalg.LinAlgError is numpy.linalg.LinAlgError
    )

    expected_lock = "".join(
        f"{package}=={version}\n"
        for package, version in sorted(runtime["packages"].items())
    )
    checks["requirements_lock"] = LOCK_PATH.read_text() == expected_lock

    for relative_path, expected_sha in manifest["artifact_sha256"].items():
        checks[f"bundle_sha256:{relative_path}"] = (
            _sha256(MANIFEST_PATH.parent / relative_path) == expected_sha
        )

    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": 1,
        "campaign_id": pin["campaign_id"],
        "status": "passed" if not failed else "failed",
        "check_count": len(checks),
        "passed_count": len(checks) - len(failed),
        "failed_checks": failed,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
