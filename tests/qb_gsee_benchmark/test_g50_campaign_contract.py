from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_g50_campaign_contract_assertions_pass() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_g50_campaign_contract.py"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    assert report["failed_checks"] == []
    assert report["passed_count"] == report["check_count"]


def test_g50_pilot_manifest_is_reproducible() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_g50_pilot_manifest.py"),
            "--check",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_g50_verifier_rejects_duplicate_canonical_family(tmp_path: Path) -> None:
    manifest_path = (
        ROOT / "analysis/solver_campaigns/g50_pilot_task_manifest_v2.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    first, duplicate = manifest["pilot_tasks"][:2]
    duplicate["problem_instance_short_name"] = first["problem_instance_short_name"]
    duplicate["family_group"] = first["family_group"]
    mutated = tmp_path / "duplicate-family.json"
    mutated.write_text(json.dumps(manifest), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_g50_campaign_contract.py"),
            "--pilot-manifest",
            str(mutated),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert "pilot_canonical_family_unique" in report["failed_checks"]
