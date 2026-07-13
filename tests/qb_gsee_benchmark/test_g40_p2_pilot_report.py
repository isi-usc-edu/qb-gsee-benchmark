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
    selection_manifest = OUT / "g40_p2_pilot_selection.json"
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
        state = {
            "status": "success",
            "task_uuid": task_uuid,
            "extractor_version": "g40_p2_mfproto_v2",
            "code_revision": "revision",
            "configuration": {"protocol_version": "g40_p2_mfproto_v2"},
            "walltime_seconds": 10.0,
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
    assert report["code_revision"] == "revision"
    assert report["verifier_code_revision"] == "verifier-revision"
    assert report["report_code_revision"] == "report-revision"
    assert report["successful_states"] == report["selected_tasks"] == 25
    assert report["output_contract"]["status"] == "passed"
    assert report["representation_gate"]["groups_passed"] == 6
    assert report["cost_gate"]["node_hour_status"] == "passed"
    assert report["cost_gate"]["memory_status"] == "passed"
    assert report["pbs_gate"]["status"] == "passed"
    assert report["mask_regime_gate"]["status"] == "passed"
    assert (
        report["mask_regime_coverage"]["all_amplitudes_masked"]["observed_task_uuids"]
        == selection_payload["mask_regime_coverage"]["all_amplitudes_masked"][
            "task_uuids"
        ]
    )
    assert len(report["state_ledger"]) == 25
    assert (
        report["mask_regime_coverage"]["natural_occupation_out_of_range"]["status"]
        == "unreachable in corpus, fixture-covered"
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
