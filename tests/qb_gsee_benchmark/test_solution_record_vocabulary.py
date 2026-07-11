import json
from pathlib import Path

from qb_gsee_benchmark.solvers.audit import audit_solution_tree


ROOT = Path(__file__).resolve().parents[2]


def test_solution_records_vocabulary_consistent():
    report = audit_solution_tree(ROOT / "solution_files")
    assert report["violations"] == []
    assert report["status"] == "pass"


def test_g31_solution_records_have_campaign_and_shci_epsilon():
    report_path = (
        ROOT / "analysis" / "solver_panel" / "g39_solution_vocabulary_migration.json"
    )
    report = json.loads(report_path.read_text())
    assert report["records"] == 165
    assert len(report["original_corrections"]) == 27
    assert len(report["diamond_corrections"]) == 2
    for record in report["records_detail"]:
        payload = json.loads((ROOT / record["path"]).read_text())
        row = payload["solution_data"][0]
        config = payload["solver_details"]["algorithm_details"]["solver_config"]
        assert row["solution_details"]["campaign"] == report["campaign"]
        assert config["campaign"] == report["campaign"]
        adapter = payload["solver_details"]["algorithm_details"]["harness_adapter"]
        if adapter == "shci_arrow":
            assert config["eps_var"] == 5.0e-5
            assert config["eps_var_label"] == "5e-5"
