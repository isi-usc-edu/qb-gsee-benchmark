import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "feature_schema"


def test_p2_pilot_report_binds_states_contract_representation_and_cost(
    tmp_path,
) -> None:
    selection = OUT / "g40_p2_pilot_selection.txt"
    selection_manifest = OUT / "g40_p2_pilot_selection_v3_postpilot_amendment_gr16.json"
    selection_payload = json.loads(selection_manifest.read_text())
    expected_masks = {
        task["task_uuid"]: set(task["expected_masks"])
        for task in selection_payload["tasks"]
    }
    contract_path = OUT / "g40_p2_feature_contract.json"
    contract = json.loads(contract_path.read_text())
    state_dir = tmp_path / "states"
    state_dir.mkdir()
    for task_uuid in selection.read_text().splitlines():
        features = {column: None for column in contract["output_columns"]}
        features.update(
            {
                "mfproto_scf_seconds": 1.0,
                "mfproto_stability_seconds": 2.0,
                "mfproto_hf_variance_seconds": 3.0,
                "mfproto_mp2_seconds": 4.0,
                "mfproto_pair_graph_seconds": 0.5,
                "mf_tie_core_degenerate_subspace_count": 0,
                "mf_tie_selected_fock_alpha_degenerate_subspace_count": 0,
                "mf_tie_selected_fock_beta_degenerate_subspace_count": 0,
            }
        )
        task_masks = expected_masks[task_uuid]
        if "rhf_not_attempted_ms2_nonzero" in task_masks:
            features["mf_branch_count"] = 4
        if "spin_gap_sector_empty" in task_masks:
            features["mf_core_gap_alpha_reason"] = "empty_or_full_spin_sector"
        if "all_amplitudes_masked" in task_masks:
            features["mp2_opposite_spin_amplitude_reason"] = "all_amplitudes_masked"
        if "external_stability_dimension_ceiling" in task_masks:
            features["mf_stability_external_reason"] = "external_dimension_ceiling"
        if "natural_occupation_out_of_range" in task_masks:
            features["mp2_natural_occupation_reason"] = (
                "natural_occupation_out_of_range"
            )
            features["mp2_natural_occupation_minimum_raw"] = -0.3031729295813625
            features["mp2_natural_occupation_maximum_raw"] = 1.3031729295813625
        state = {
            "status": "success",
            "task_uuid": task_uuid,
            "extractor_version": "g40_p2_mfproto_v3",
            "code_revision": "revision",
            "configuration": {"protocol_version": "g40_p2_mfproto_v3"},
            "walltime_seconds": 10.0,
            "process_peak_rss_kb": 2048,
            "features": features,
        }
        (state_dir / f"{task_uuid}.mfproto.json").write_text(
            json.dumps(state, sort_keys=True) + "\n"
        )
    representation = tmp_path / "representation.json"
    representation.write_text(
        json.dumps(
            {
                "status": "passed",
                "equivalence_groups": 6,
                "groups_passed": 6,
                "code_revision": "verifier-revision",
            }
        )
    )
    accounting = tmp_path / "accounting.txt"
    accounting.write_text(
        "\n".join(
            [
                "Job Id: 1.imgt1",
                "    Job_Name = g40_p2_fixture",
                "    job_state = F",
                "    Exit_status = 0",
                "    resources_used.walltime = 00:05:00",
                "    resources_used.cput = 01:00:00",
                "    resources_used.mem = 1024kb",
                "    resources_used.vmem = 2048kb",
                "    Resource_List.ncpus = 128",
                "    Resource_List.walltime = 12:00:00",
                "    queue = compute",
            ]
        )
        + "\n"
    )
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    job = tmp_path / "pilot.pbs"
    for path in (stdout, stderr, job):
        path.write_text("fixture\n")
    output = tmp_path / "report"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "build_g40_p2_pilot_report.py"),
        "--state-dir",
        str(state_dir),
        "--selection",
        str(selection),
        "--selection-manifest",
        str(selection_manifest),
        "--feature-contract",
        str(contract_path),
        "--representation-check",
        str(representation),
        "--accounting",
        str(accounting),
        "--stdout-log",
        str(stdout),
        "--stderr-log",
        str(stderr),
        "--job-script",
        str(job),
        "--code-revision",
        "revision",
        "--verifier-code-revision",
        "verifier-revision",
        "--report-code-revision",
        "report-revision",
        "--output-prefix",
        str(output),
    ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    report = json.loads(output.with_suffix(".json").read_text())
    assert report["status"] == "passed"
    assert report["report_version"] == "g40_p2_pilot_report_v5"
    assert report["code_revision"] == "revision"
    assert report["verifier_code_revision"] == "verifier-revision"
    assert report["report_code_revision"] == "report-revision"
    assert report["successful_states"] == report["selected_tasks"] == 25
    assert report["output_contract"]["status"] == "passed"
    assert report["representation_gate"]["groups_passed"] == 6
    assert report["cost_gate"]["node_hour_status"] == "passed"
    assert report["cost_gate"]["memory_status"] == "passed"
    assert report["cost_gate"]["state_peak_rss_gb"] == 2048 / 1024**2
    assert report["cost_gate"]["pbs_sampled_peak_memory_gb"] == 1024 / 1024**2
    assert report["cost_gate"]["maximum_memory_gb"] == 2048 / 1024**2
    assert report["degenerate_fock_expected"] == 6
    assert report["cost_gate"]["projection_method"] == (
        "uniform_mean_scaling_of_hard_biased_25_state_pilot"
    )
    assert report["pbs_gate"]["status"] == "passed"
    assert report["mask_regime_gate"]["status"] == "passed"
    assert (
        report["mask_regime_coverage"]["all_amplitudes_masked"]["observed_task_uuids"]
        == selection_payload["mask_regime_coverage"]["all_amplitudes_masked"][
            "task_uuids"
        ]
    )
    assert len(report["state_ledger"]) == 25
    assert report["natural_occupation_mask_audit"] == [
        {
            "task_uuid": "beabcf8f-a6c0-5e32-9385-110ff65cbbf0",
            "reason": "natural_occupation_out_of_range",
            "minimum_raw": -0.3031729295813625,
            "maximum_raw": 1.3031729295813625,
        }
    ]
    assert report["mask_table_amendment"]["review_id"] == "goals-review-16"
    assert (
        report["mask_regime_coverage"]["natural_occupation_out_of_range"]["status"]
        == "passed"
    )

    failed_accounting = tmp_path / "accounting.failed.txt"
    failed_accounting.write_text(
        accounting.read_text()
        .replace("Job Id: 1.imgt1", "Job Id: 0.imgt1")
        .replace("Exit_status = 0", "Exit_status = 1")
    )
    failed_output = tmp_path / "report-failed"
    failed_command = list(command)
    failed_command[failed_command.index(str(accounting))] = str(failed_accounting)
    failed_command[failed_command.index(str(output))] = str(failed_output)
    failed_result = subprocess.run(
        failed_command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert failed_result.returncode == 1
    failed_report = json.loads(failed_output.with_suffix(".json").read_text())
    assert failed_report["status"] == "failed"
    assert failed_report["pbs_gate"] == {
        "failed_job_ids": ["0.imgt1"],
        "jobs": 1,
        "status": "failed",
        "successful_jobs": 0,
        "unauthorized_queue_job_ids": [],
    }

    repaired_output = tmp_path / "report-repaired"
    repaired_command = list(command)
    repaired_command[repaired_command.index(str(output))] = str(repaired_output)
    repaired_command.extend(["--superseded-accounting", str(failed_accounting)])
    subprocess.run(
        repaired_command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    repaired_report = json.loads(repaired_output.with_suffix(".json").read_text())
    assert repaired_report["status"] == "passed"
    assert [item["job_id"] for item in repaired_report["superseded_pbs_jobs"]] == [
        "0.imgt1"
    ]


def test_committed_p2_pilot_report_closes_all_gates_and_preserves_repair() -> None:
    report_path = OUT / "g40_p2_pilot_report.json"
    current_check_path = OUT / "g40_p2_representation_pair_check.json"
    superseded_check_path = (
        OUT / "g40_p2_representation_pair_check_superseded_1b35f2d.json"
    )
    report = json.loads(report_path.read_text())
    current_check = json.loads(current_check_path.read_text())
    superseded_check = json.loads(superseded_check_path.read_text())

    assert report["report_version"] == "g40_p2_pilot_report_v3"
    assert report["status"] == "passed"
    assert report["code_revision"] == "1b35f2d"
    assert report["verifier_code_revision"] == "8f369a6"
    assert report["report_code_revision"] == "8f369a6"
    assert report["successful_states"] == report["selected_tasks"] == 25
    assert report["output_contract"]["status"] == "passed"
    assert report["output_contract"]["columns"] == 327
    assert report["representation_gate"]["status"] == "passed"
    assert report["representation_gate"]["groups_passed"] == 6
    assert report["representation_gate"]["failures"] == []
    assert report["representation_gate"]["rotation_pair_nonvacuity"]["status"] == (
        "passed"
    )
    assert report["pbs_gate"] == {
        "failed_job_ids": [],
        "jobs": 11,
        "status": "passed",
        "successful_jobs": 11,
        "unauthorized_queue_job_ids": [],
    }
    assert [item["job_id"] for item in report["pbs_jobs"]] == [
        *(f"{job_id}.imgt1" for job_id in range(7651821, 7651831)),
        "7652168.imgt1",
    ]
    assert [
        (item["job_id"], item["exit_status"]) for item in report["superseded_pbs_jobs"]
    ] == [("7651831.imgt1", 1)]
    assert report["mask_regime_gate"]["status"] == "passed"
    assert all(
        item["status"] in {"passed", "unreachable in corpus, fixture-covered"}
        for item in report["mask_regime_coverage"].values()
    )
    assert report["degenerate_fock_states"] == 15
    assert len(report["tie_audit_ledger"]) == 15
    assert {
        "ac3a023f-8d31-5d79-803e-c54e947c8d75",
        "beabcf8f-a6c0-5e32-9385-110ff65cbbf0",
    } <= {item["task_uuid"] for item in report["tie_audit_ledger"]}
    assert report["cost_gate"]["projected_production_node_hours"] < 23.0
    assert report["cost_gate"]["maximum_memory_gb"] < 94.0
    assert report["cost_gate"]["node_hour_status"] == "passed"
    assert report["cost_gate"]["memory_status"] == "passed"

    assert current_check["status"] == "passed"
    assert current_check["code_revision"] == "8f369a6"
    assert current_check["groups_passed"] == current_check["equivalence_groups"] == 6
    assert current_check["rotation_pair_nonvacuity"]["status"] == "passed"
    assert superseded_check["status"] == "failed"
    assert superseded_check["failures"] == [
        {
            "group": "b696450f-72ab-5509-b932-61fb30eda535",
            "reason": "no_representation_sensitive_feature_changed",
        }
    ]

    assert report["representation_check"] == {
        "path": current_check_path.name,
        "sha256": hashlib.sha256(current_check_path.read_bytes()).hexdigest(),
    }
    assert report["superseded_representation_checks"] == [
        {
            "path": superseded_check_path.name,
            "sha256": hashlib.sha256(superseded_check_path.read_bytes()).hexdigest(),
        }
    ]


def test_committed_p2_v5_report_uses_amended_table_and_same_states() -> None:
    report_path = OUT / "g40_p2_pilot_report_v5.json"
    report = json.loads(report_path.read_text())
    failed_v4 = json.loads(
        (OUT / "g40_p2_repilot_report_v4_d40ccf7_failed.json").read_text()
    )
    amendment_path = OUT / "g40_p2_pilot_selection_v3_postpilot_amendment_gr16.json"

    assert report["report_version"] == "g40_p2_pilot_report_v5"
    assert report["status"] == "passed"
    assert report["code_revision"] == "d40ccf7"
    assert report["verifier_code_revision"] == "d40ccf7"
    assert report["report_code_revision"] == "db6cfa1"
    assert report["successful_states"] == report["selected_tasks"] == 25
    assert report["state_ledger"] == failed_v4["state_ledger"]
    assert report["mask_regime_gate"]["status"] == "passed"
    assert report["mask_table_amendment"]["status"] == "adjudicated_post_pilot"
    assert report["mask_table_amendment"]["review_id"] == "goals-review-16"
    assert report["selection_manifest"] == {
        "path": amendment_path.name,
        "sha256": hashlib.sha256(amendment_path.read_bytes()).hexdigest(),
    }
    assert report["mask_regime_coverage"]["natural_occupation_out_of_range"] == {
        "declaration_status": "corpus-reachable",
        "status": "passed",
        "expected_task_uuids": ["beabcf8f-a6c0-5e32-9385-110ff65cbbf0"],
        "observed_task_uuids": ["beabcf8f-a6c0-5e32-9385-110ff65cbbf0"],
        "missing_task_uuids": [],
        "unexpected_task_uuids": [],
    }
    assert report["natural_occupation_mask_audit"] == [
        {
            "task_uuid": "beabcf8f-a6c0-5e32-9385-110ff65cbbf0",
            "reason": "natural_occupation_out_of_range",
            "minimum_raw": -0.3031729295813625,
            "maximum_raw": 1.3031729295813625,
        }
    ]
    assert report["pbs_gate"]["status"] == "passed"
    assert report["representation_gate"]["status"] == "passed"
    assert report["cost_gate"]["node_hour_status"] == "passed"
    assert report["cost_gate"]["memory_status"] == "passed"
