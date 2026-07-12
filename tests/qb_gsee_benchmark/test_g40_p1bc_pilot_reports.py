import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "feature_schema"


def test_p1b_pilot_report_binds_precision_representation_and_pbs() -> None:
    report = json.loads((OUT / "g40_p1b_pilot_report.json").read_text())
    assert report["status"] == "passed"
    assert report["code_revision"] == "dd281ca"
    assert report["extractor_version"] == "g40_p1b_determinant_coupling_v4"
    assert report["successful_states"] == report["selected_tasks"] == 25
    assert report["pbs"]["job_id"] == "7651363.imgt1"
    assert report["pbs"]["exit_status"] == 0
    assert report["pbs"]["queue"] == "compute"
    assert report["representation_pair_check"] == {
        "equivalence_groups": 2,
        "groups_passed": 2,
        "status": "passed",
    }
    assert report["branching_precision_gate"]["failure_count"] == 0
    assert report["branching_precision_gate"]["status"] == "passed"
    assert len(report["state_ledger"]) == 25
