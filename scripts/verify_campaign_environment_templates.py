#!/usr/bin/env python3
"""Fail closed on isolation and environment capture in future templates."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {
    "pbs": Path("scripts/templates/python_campaign.pbs.template"),
    "extraction": Path("scripts/templates/python_extraction.sh.template"),
    "harvest": Path("scripts/templates/python_harvest.sh.template"),
}
CONTRACT = Path("analysis/solver_campaigns/future_campaign_environment_contract.md")


def verify(root: Path = ROOT) -> dict[str, object]:
    checks: dict[str, bool] = {}
    for stage, relative in TEMPLATES.items():
        text = (root / relative).read_text(encoding="utf-8")
        checks[f"{stage}:strict_shell"] = "set -euo pipefail" in text
        checks[f"{stage}:pinned_interpreter"] = (
            "${PYTHON:?" in text and '"$PYTHON"' in text
        )
        checks[f"{stage}:isolation"] = "export PYTHONNOUSERSITE=1" in text
        checks[f"{stage}:capture"] = (
            "scripts/capture_campaign_environment.py" in text
            and f"--stage {stage}" in text
            and "--output \"$ENVIRONMENT_RECORD\"" in text
        )
        checks[f"{stage}:persistent_record_required"] = "${ENVIRONMENT_RECORD:?" in text

    contract = (root / CONTRACT).read_text(encoding="utf-8")
    contract_words = " ".join(contract.lower().split())
    checks["contract:all_stages"] = all(
        stage in contract_words for stage in TEMPLATES
    )
    checks["contract:future_scope"] = (
        "every new python campaign launcher" in contract_words
        and "historical campaign bundles remain immutable" in contract_words
    )
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": 1,
        "status": "passed" if not failed else "failed",
        "check_count": len(checks),
        "passed_count": len(checks) - len(failed),
        "failed_checks": failed,
        "templates": {stage: str(path) for stage, path in TEMPLATES.items()},
    }


def main() -> int:
    report = verify()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
