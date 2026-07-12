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
                "mf_tie_core_degenerate_subspace_count": 0,
                "mf_tie_selected_fock_alpha_degenerate_subspace_count": 0,
                "mf_tie_selected_fock_beta_degenerate_subspace_count": 0,
            }
        )
        state = {
            "status": "success",
            "task_uuid": task_uuid,
            "extractor_version": "g40_p2_mfproto_v1",
            "code_revision": "revision",
            "configuration": {"protocol_version": "g40_p2_mfproto_v1"},
            "walltime_seconds": 10.0,
            "features": features,
        }
        (state_dir / f"{task_uuid}.mfproto.json").write_text(
            json.dumps(state, sort_keys=True) + "\n"
        )
    representation = tmp_path / "representation.json"
    representation.write_text(
        json.dumps({"status": "passed", "equivalence_groups": 6, "groups_passed": 6})
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
        "--output-prefix",
        str(output),
    ]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    report = json.loads(output.with_suffix(".json").read_text())
    assert report["status"] == "passed"
    assert report["successful_states"] == report["selected_tasks"] == 25
    assert report["output_contract"]["status"] == "passed"
    assert report["representation_gate"]["groups_passed"] == 6
    assert report["cost_gate"]["node_hour_status"] == "passed"
    assert report["cost_gate"]["memory_status"] == "passed"
    assert len(report["state_ledger"]) == 25
