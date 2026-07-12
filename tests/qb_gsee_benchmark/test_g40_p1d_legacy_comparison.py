import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "feature_schema"


def test_p1d_legacy_comparison_is_complete_and_provenanced() -> None:
    selection = OUT / "g40_p1d_legacy_comparison_selection.txt"
    selected = selection.read_text().splitlines()
    comparison = pd.read_csv(OUT / "g40_p1d_legacy_comparison.csv")
    report = json.loads((OUT / "g40_p1d_legacy_comparison.json").read_text())
    r6 = json.loads((OUT / "g40_r6_production_report.json").read_text())

    assert len(selected) == len(set(selected)) == 184
    assert comparison["task_uuid"].is_unique
    assert set(comparison["task_uuid"]) == set(selected)
    assert report["report_version"] == "g40_p1d_legacy_comparison_v1"
    assert report["extractor_version"] == "g40_p1d_interaction_spectrum_v1"
    assert report["code_revision"] == "533a3fd"
    assert report["rows"] == len(comparison) == 184
    assert report["selection_sha256"] == hashlib.sha256(
        selection.read_bytes()
    ).hexdigest()
    assert report["feature_table_sha256"] == r6["input_feature_table_sha256"]
    assert report["pbs"]["job_id"] == "7651569.imgt1"
    assert report["pbs"]["queue"] == "compute"
    assert report["pbs"]["exit_status"] == 0
    assert report["pbs"]["walltime_seconds"] == 1143


def test_p1d_comparison_records_materially_different_conventions() -> None:
    report = json.loads((OUT / "g40_p1d_legacy_comparison.json").read_text())

    assert report["non_psd_rows"] == 12
    assert report["maximum_negative_mass_fraction"] > 3.0e-5
    assert report["rank_comparisons"]["rel_1e_4"]["median_relative_difference"] > 0.5
    assert report["decay_comparison"]["spearman"] < -0.5
    assert report["gap_comparison"]["spearman"] > 0.999
    assert "PI review required" in report["name_decision"]
    assert "does not silently overwrite legacy df_* names" in report["name_decision"]
