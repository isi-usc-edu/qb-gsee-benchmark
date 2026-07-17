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
V3_MANIFEST_SHA256 = "13f90d0f34e0ba3dd7c56030b185979b7ef440d9d8cab73fa69e9a2c79fdea53"
FROZEN_PILOT_SOURCE_FEATURE_TABLE_SHA256 = (
    "ee94df21f927ff2e548ac10fda8d5a88c601f31330619ec6c575dc75cf436dc7"
)
CURRENT_G58_FEATURE_TABLE_SHA256 = (
    "b5f8a78c3fd8fa9ba1e5dce4e8e2986bfc19346b26375e22763816efa5cdc8f7"
)


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
    assert (
        contract["universal_attempt"]["attempt_all_manifest_tasks_per_solver"]
        is True
    )
    assert (
        contract["universal_attempt"][
            "not_attempted_permitted_within_binding_manifest"
        ]
        is False
    )
    assert contract["production_scope"]["binding_task_count"] == "TBD_AT_GATE_3"
    assert contract["production_scope"]["outside_manifest"]["status"] == (
        "not_attempted"
    )
    assert contract["cost_projection"]["working_uniform_cap_hours_per_task"] == 12
    assert contract["cost_projection"]["production_hardware_unit_per_task"][
        "SHCI"
    ] == "TBD_AT_GATE_3_O35"
    assert "admission_inputs" not in pilot["calibration_contract"]
    assert "production_admission_policy" not in pilot["calibration_contract"]
    assert (
        pilot["calibration_contract"]["production_attempt_scope"]
        == "all_tasks_within_frozen_ml5_binding_manifest_per_solver"
    )
    assert (
        pilot["calibration_contract"]["production_scope"][
            "pilot_execution_gated_on_binding_manifest"
        ]
        is False
    )


def test_g50_scope_amendment_preserves_pilot_manifest_bytes() -> None:
    assert hashlib.sha256(V3_MANIFEST.read_bytes()).hexdigest() == V3_MANIFEST_SHA256


def test_g50_pilot_remains_bound_to_frozen_pre_g58_table() -> None:
    manifest = json.loads(V3_MANIFEST.read_text(encoding="utf-8"))
    live_table = ROOT / "scripts/Hamiltonian_features.csv"

    assert (
        manifest["corpus"]["feature_table_sha256"]
        == FROZEN_PILOT_SOURCE_FEATURE_TABLE_SHA256
    )
    assert (
        hashlib.sha256(live_table.read_bytes()).hexdigest()
        == CURRENT_G58_FEATURE_TABLE_SHA256
    )
    assert FROZEN_PILOT_SOURCE_FEATURE_TABLE_SHA256 != CURRENT_G58_FEATURE_TABLE_SHA256


def test_g50_authorization_is_cpu_pilot_only() -> None:
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
    authorization = pilot["authorization"]

    assert contract["pilot_design"]["execution_authorized"] is True
    assert authorization["pilot_execution_authorized"] is True
    assert authorization["qsub_permitted"] is True
    assert authorization["ipie_swing_submission_permitted"] is False
    assert authorization["production_execution_authorized"] is False
    assert authorization["authorized_cpu_campaign_ids"] == [
        "g50_dmrg_pilot_2026-07_v1",
        "g50_trimci_pilot_2026-07_v1",
        "g50_shci_pilot_2026-07_v1",
    ]


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
