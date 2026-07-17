"""Release-gate checks for the merged G40 P1-A production table."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from scripts.build_g40_p1a_production import ALLOWED_MIGRATIONS

ROOT = Path(__file__).resolve().parents[2]
TABLE = ROOT / "scripts" / "Hamiltonian_features.csv"
OUT = ROOT / "analysis" / "feature_schema"
G40_P2_TABLE_SHA256 = "8f0d89ec2cc7cf933a57c4ace7d32cd62d478c0fb8f8272aae4d36d387d45b2b"
G58_TABLE_SHA256 = "b5f8a78c3fd8fa9ba1e5dce4e8e2986bfc19346b26375e22763816efa5cdc8f7"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_p1a_table_has_manifest_wide_universal_coverage() -> None:
    frame = pd.read_csv(TABLE)
    assert frame.shape[0] == 718
    assert frame.shape[1] >= 158
    assert frame["task_uuid"].is_unique
    g40 = frame[frame["universal_t0_linear_features_version"].notna()]
    assert len(g40) == 591
    always_applicable = [
        "n_orbs",
        "n_elec",
        "ms2",
        "log_fci_dim",
        "fermionic_coefficient_l1_norm",
        "effective_h1_frobenius_norm",
        "eri_full_l2_norm",
        "rho_offdiag",
        "bare_one_body_bandwidth",
        "fcidump_symmetry_status",
        "fcidump_container_format",
        "fcidump_ms2_source",
        "universal_t0_linear_features_version",
    ]
    assert not g40[always_applicable].isna().any().any()
    assert set(g40["universal_t0_linear_features_version"]) == {"g40_p1_linear_v4"}
    assert set(g40["fcidump_symmetry_status"]) == {
        "ok",
        "conflict_above_tolerance",
    }


def test_p1a_migration_ledger_is_complete_and_bounded() -> None:
    with (OUT / "g40_p1a_migration_ledger.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 601
    assert set(row["column"] for row in rows) == set(ALLOWED_MIGRATIONS)
    assert Counter(row["column"] for row in rows) == {
        "log_fci_dim": 373,
        "eri_full_l1_norm": 61,
        "eri_full_l2_norm": 61,
        "two_body_unique_record_count": 53,
        "two_body_duplicate_orientation_records_skipped": 53,
    }
    for row in rows:
        assert row["reason"] == ALLOWED_MIGRATIONS[row["column"]]


def test_p1a_report_binds_table_jobs_and_representation_gate() -> None:
    report = json.loads((OUT / "g40_p1a_production_report.json").read_text())
    assert report["successful_states"] == report["corpus_tasks"] == 591
    assert report["rows_before"] == 418
    assert report["rows_after"] == 591
    assert report["columns_before"] == 120
    assert report["columns_after"] == 158
    assert report["migration_cells"] == 601
    assert report["output_feature_table_sha256"] == (
        "7d15c9fefe2951be9fc1bf9fdbfeedc0f0a4ea300a3c1a47fcb7ca9e35441410"
    )
    p1b = json.loads((OUT / "g40_p1b_production_report.json").read_text())
    p1c = json.loads((OUT / "g40_p1c_production_report.json").read_text())
    retag = json.loads((OUT / "g40_retag_audit_production_report.json").read_text())
    r6 = json.loads((OUT / "g40_r6_production_report.json").read_text())
    p1d = json.loads((OUT / "g40_p1d_production_report.json").read_text())
    p2 = json.loads((OUT / "g40_p2_production_report.json").read_text())
    assert p1b["input_feature_table_sha256"] == report["output_feature_table_sha256"]
    assert p1c["input_feature_table_sha256"] == p1b["output_feature_table_sha256"]
    assert retag["input_feature_table_sha256"] == p1c["output_feature_table_sha256"]
    assert r6["input_feature_table_sha256"] == retag["output_feature_table_sha256"]
    assert p1d["input_feature_table_sha256"] == r6["output_feature_table_sha256"]
    assert p2["input_feature_table_sha256"] == p1d["output_feature_table_sha256"]
    assert p2["output_feature_table_sha256"] == G40_P2_TABLE_SHA256
    assert _sha256(TABLE) == G58_TABLE_SHA256
    assert report["initial_job_id"] == "7651290.imgt1"
    assert report["corrected_job_id"] == "7651318.imgt1"
    assert report["corrected_code_revision"].startswith("8f8348a")
    assert report["representation_pair_status"] == "passed"
    assert report["representation_pair_groups_passed"] == 2


def test_p1a_report_builder_has_no_embedded_noqa() -> None:
    builder = (ROOT / "scripts/build_g40_p1a_production.py").read_text()
    report_markdown = (OUT / "g40_p1a_production_report.md").read_text()
    assert "# noqa" not in builder
    assert "# noqa" not in report_markdown


def test_femoco76_spin_provenance_distinguishes_stages() -> None:
    provenance = json.loads((OUT / "g40_femoco76_spin_provenance.json").read_text())
    assert provenance["current_features_spin"] == 35
    assert provenance["intake_features_spin"] == 35
    assert provenance["upstream"]["orbital_generation_spin_2s"] == 35
    assert provenance["fcidump"] == {
        "container": "zip",
        "member": "FCIDUMP",
        "ms2": 3,
        "nelec": 113,
        "norb": 76,
    }
    assert provenance["instance_edit_performed"] is False
    assert provenance["finding"] == (
        "distinct_orbital_generation_and_active_space_spin_sectors"
    )
