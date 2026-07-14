import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "feature_schema"


def test_p1d_pilot_report_binds_exact_code_resources_and_representation() -> None:
    report = json.loads((OUT / "g40_p1d_pilot_report.json").read_text())
    assert report["status"] == "passed"
    assert report["code_revision"] == "c626e5c"
    assert report["extractor_version"] == "g40_p1d_interaction_spectrum_v1"
    assert report["successful_states"] == report["selected_tasks"] == 25
    assert report["pbs"]["job_id"] == "7651564.imgt1"
    assert report["pbs"]["exit_status"] == 0
    assert report["pbs"]["queue"] == "compute"
    assert report["maximum_task_walltime_seconds"] < 400.0
    assert report["maximum_task_peak_rss_kb"] < 5_000_000
    assert report["maximum_task_walltime_task_uuid"]
    assert report["maximum_task_peak_rss_task_uuid"]
    assert report["representation_pair_check"] == {
        "equivalence_groups": 4,
        "groups_passed": 4,
        "status": "passed",
    }
    assert len(report["state_ledger"]) == 25


def test_representation_gate_accepts_an_all_inv_block(tmp_path: Path) -> None:
    pair_dir = tmp_path / "pairs"
    state_dir = tmp_path / "states"
    pair_dir.mkdir()
    state_dir.mkdir()
    tasks = []
    for task_uuid in ("a", "b"):
        tasks.append(
            {
                "task_uuid": task_uuid,
                "features": {"equivalence_group_id": "all-inv"},
            }
        )
        (state_dir / f"{task_uuid}.linear.json").write_text(
            json.dumps(
                {
                    "task_uuid": task_uuid,
                    "status": "success",
                    "extractor_version": "fixture",
                    "features": {"n_orbs": 2},
                }
            )
            + "\n"
        )
    (pair_dir / "pair.json").write_text(json.dumps({"tasks": tasks}) + "\n")
    output = tmp_path / "report.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_g40_representation_pairs.py"),
            "--pair-instance-dir",
            str(pair_dir),
            "--state-dir",
            str(state_dir),
            "--state-pattern",
            "*.linear.json",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(output.read_text())
    assert payload["status"] == "passed"
    assert payload["equivalence_groups"] == payload["groups_passed"] == 5
    all_inv = next(
        report
        for report in payload["reports"]
        if report["equivalence_group_id"] == "all-inv"
    )
    assert all_inv["status"] == "passed"
    assert all_inv["changed_basis_features"] == []


def _run_linear_rotation_gate(
    tmp_path: Path,
    group_values: dict[str, tuple[float, float]],
    *,
    density_delta: dict[str, float] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    pair_dir = tmp_path / "rotation-pairs"
    state_dir = tmp_path / "rotation-states"
    certificate_dir = tmp_path / "rotation-certificates"
    pair_dir.mkdir()
    state_dir.mkdir()
    certificate_dir.mkdir()
    density_delta = density_delta or {}
    tasks = []
    for group, values in group_values.items():
        certificate_path = certificate_dir / f"{group}.rotation.json"
        certificate_path.write_text(
            json.dumps(
                {
                    "equivalence_group_id": group,
                    "source_representation": "source",
                    "localized_representation": "localized",
                    "rotation_matrix": [[1.0, 0.0], [0.0, 1.0]],
                },
                sort_keys=True,
            )
            + "\n"
        )
        checksum = hashlib.sha1(certificate_path.read_bytes()).hexdigest()
        for member, value in enumerate(values):
            task_uuid = f"{group}-{member}"
            representation = "source" if member == 0 else "localized"
            tasks.append(
                {
                    "task_uuid": task_uuid,
                    "features": {
                        "equivalence_group_id": group,
                        "orbital_representation": representation,
                    },
                    "supporting_files": [
                        {
                            "is_fcidump_file": False,
                            "instance_data_object_url": (
                                f"https://example.test/{certificate_path.name}"
                            ),
                            "instance_data_checksum_type": "sha1sum",
                            "instance_data_checksum": checksum,
                        }
                    ],
                }
            )
            delta = density_delta.get(group, 0.0) if member else 0.0
            selected_certificate = {
                "certificate_version": ("g40_mfproto_selected_stationary_point_v1"),
                "selected_branch_index": 0,
                "selected_method": "RHF",
                "selected_guess": "G1",
                "selected_energy_hartree": -2.0,
                "selected_s2": 0.0,
                "density_alpha": [[1.0 + delta, 0.0], [0.0, 0.0]],
                "density_beta": [[1.0 + delta, 0.0], [0.0, 0.0]],
                "fock_spectrum_alpha_hartree": [-1.0, 1.0],
                "fock_spectrum_beta_hartree": [-1.0, 1.0],
                "stationary_components": [[0, 1]],
                "branch_structure": [
                    {
                        "method": "RHF",
                        "guess": "G1",
                        "converged": True,
                        "fallback_used": False,
                        "engine_converged": True,
                        "error_type": None,
                    }
                ],
            }
            (state_dir / f"{task_uuid}.linear.json").write_text(
                json.dumps(
                    {
                        "task_uuid": task_uuid,
                        "status": "success",
                        "extractor_version": "fixture",
                        "features": {"n_orbs": 2, "rho_offdiag": value},
                        "audit": {"selected_state_certificate": selected_certificate},
                    }
                )
                + "\n"
            )
    (pair_dir / "pairs.json").write_text(json.dumps({"tasks": tasks}) + "\n")
    output = tmp_path / "rotation-report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/verify_g40_representation_pairs.py"),
            "--pair-instance-dir",
            str(pair_dir),
            "--rotation-certificate-dir",
            str(certificate_dir),
            "--state-dir",
            str(state_dir),
            "--state-pattern",
            "*.linear.json",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result, json.loads(output.read_text())


def test_rotation_gate_requires_basis_drift_across_set_not_per_pair(
    tmp_path: Path,
) -> None:
    result, payload = _run_linear_rotation_gate(
        tmp_path,
        {"no-drift": (1.0, 1.0), "drift": (1.0, 2.0)},
    )
    assert result.returncode == 0
    assert payload["status"] == "passed"
    reports = {
        report["equivalence_group_id"]: report
        for report in payload["reports"]
        if "task_uuids" in report
    }
    assert reports["no-drift"]["status"] == "passed"
    assert reports["no-drift"]["basis_drift_observed"] is False
    assert reports["no-drift"]["stationary_point_identity"]["status"] == ("passed")
    assert reports["drift"]["basis_drift_observed"] is True
    assert payload["rotation_pair_nonvacuity"] == {
        "groups_with_basis_features": ["drift", "no-drift"],
        "groups_with_observed_basis_drift": ["drift"],
        "status": "passed",
    }


def test_zero_drift_rotation_pair_fails_bad_stationary_identity(
    tmp_path: Path,
) -> None:
    result, payload = _run_linear_rotation_gate(
        tmp_path,
        {"no-drift": (1.0, 1.0), "drift": (1.0, 2.0)},
        density_delta={"no-drift": 1.0e-4},
    )
    assert result.returncode == 1
    report = next(
        item
        for item in payload["reports"]
        if item.get("equivalence_group_id") == "no-drift"
    )
    identity = report["stationary_point_identity"]
    assert identity["status"] == "failed"
    assert identity["checks"]["mapped_spin_density"] is False
    assert {item["reason"] for item in payload["failures"]} == {
        "stationary_point_identity_certificate_failed"
    }


def test_rotation_gate_fails_when_entire_pair_set_is_basis_vacuous(
    tmp_path: Path,
) -> None:
    result, payload = _run_linear_rotation_gate(tmp_path, {"no-drift": (1.0, 1.0)})
    assert result.returncode == 1
    assert payload["status"] == "failed"
    assert payload["rotation_pair_nonvacuity"]["status"] == "failed"
    assert payload["failures"] == [
        {
            "groups": ["no-drift"],
            "reason": (
                "no_representation_sensitive_feature_changed_in_rotation_pair_set"
            ),
        }
    ]
