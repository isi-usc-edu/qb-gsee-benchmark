import hashlib
import json

import pandas as pd
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


def test_p1b_production_table_and_report_are_complete() -> None:
    table = ROOT / "scripts" / "Hamiltonian_features.csv"
    frame = pd.read_csv(table)
    assert frame.shape == (591, 190)
    assert frame["task_uuid"].is_unique
    assert set(frame["determinant_coupling_features_version"]) == {
        "g40_p1b_determinant_coupling_v4"
    }
    required = [
        "det_coupling_nonzero_degree",
        "det_coupling_participation_ratio",
        "det_coupling_top_10_l2_mass_fraction",
        "random_det_expected_degree_rel_1e_8",
        "random_det_expected_degree_mc_se_rel_1e_8",
        "random_det_branching_double_method",
    ]
    assert not frame[required].isna().any().any()

    report = json.loads((OUT / "g40_p1b_production_report.json").read_text())
    assert report["successful_states"] == report["corpus_tasks"] == 591
    assert report["rows_before"] == report["rows_after"] == 591
    assert report["columns_before"] == 158
    assert report["columns_after"] == 190
    assert len(report["new_columns"]) == 32
    assert report["newly_populated_cells"] == 18857
    assert report["changed_populated_cells"] == 0
    assert report["code_revision"] == "dd281ca"
    assert report["builder_revision"] == "0da1087"
    assert report["pbs"]["job_id"] == "7651364.imgt1"
    assert report["pbs"]["exit_status"] == 0
    assert report["representation_pair_check"]["status"] == "passed"
    assert (
        report["output_feature_table_sha256"]
        == hashlib.sha256(table.read_bytes()).hexdigest()
    )


def test_p1c_pilot_report_binds_representation_and_pbs() -> None:
    report = json.loads((OUT / "g40_p1c_pilot_report.json").read_text())
    assert report["status"] == "passed"
    assert report["code_revision"] == "a1179fa"
    assert report["extractor_version"] == "g40_p1c_orderability_v1"
    assert report["successful_states"] == report["selected_tasks"] == 25
    assert report["pbs"]["job_id"] == "7651352.imgt1"
    assert report["pbs"]["exit_status"] == 0
    assert report["pbs"]["queue"] == "compute"
    assert report["maximum_task_walltime_seconds"] > 3000.0
    assert report["maximum_task_peak_rss_kb"] < 3_000_000
    assert report["representation_pair_check"] == {
        "equivalence_groups": 2,
        "groups_passed": 2,
        "status": "passed",
    }
    assert len(report["state_ledger"]) == 25
