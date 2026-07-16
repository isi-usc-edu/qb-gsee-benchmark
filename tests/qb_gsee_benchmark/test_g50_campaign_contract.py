from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2_MANIFEST = ROOT / "analysis/solver_campaigns/g50_pilot_task_manifest_v2.json"
V3_MANIFEST = ROOT / "analysis/solver_campaigns/g50_pilot_task_manifest_v3.json"
V2_MANIFEST_SHA256 = "e1586f910206bc9c92b10a5dff84adf9b6a4a3517f09d2228865f94dff58d612"


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


def test_g50_o34_replaces_admission_with_uniform_cap() -> None:
    contract = json.loads(
        (
            ROOT / "analysis/solver_campaigns/g50_campaign_contract_v1.json"
        ).read_text(encoding="utf-8")
    )
    pilot = json.loads(
        (ROOT / "analysis/solver_campaigns/g50_pilot_design_v1.json").read_text(
            encoding="utf-8"
        )
    )

    assert "target_blind_admission" not in contract
    assert contract["universal_attempt"]["attempt_all_tasks_per_solver"] is True
    assert contract["universal_attempt"]["not_attempted_permitted"] is False
    assert contract["cost_projection"]["working_uniform_cap_hours_per_task"] == 12
    assert "admission_inputs" not in pilot["calibration_contract"]
    assert "production_admission_policy" not in pilot["calibration_contract"]
    assert (
        pilot["calibration_contract"]["production_attempt_scope"]
        == "all_718_tasks_per_solver"
    )


def test_g50_pilot_manifest_v3_is_reproducible() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/build_g50_pilot_manifest.py"),
            "--check",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "verified" in result.stdout


def test_g50_verifier_rejects_duplicate_canonical_family(tmp_path: Path) -> None:
    manifest_path = V3_MANIFEST
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


def test_g50_v2_manifest_is_preserved_as_audit_predecessor() -> None:
    assert hashlib.sha256(V2_MANIFEST.read_bytes()).hexdigest() == V2_MANIFEST_SHA256


def test_g50_verifier_rejects_superseded_v2_manifest() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_g50_campaign_contract.py"),
            "--pilot-manifest",
            str(V2_MANIFEST),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert "pilot_manifest_hash_bound" in report["failed_checks"]


def test_g50_v3_has_unique_artifact_bound_families() -> None:
    manifest = json.loads(V3_MANIFEST.read_text())
    tasks = manifest["pilot_tasks"]
    assert len({task["family_group"] for task in tasks}) == 12
