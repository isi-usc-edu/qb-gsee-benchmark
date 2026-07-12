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
