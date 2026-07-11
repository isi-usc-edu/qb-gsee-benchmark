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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_p1a_table_has_manifest_wide_universal_coverage() -> None:
    frame = pd.read_csv(TABLE)
    assert frame.shape == (591, 158)
    assert frame["task_uuid"].is_unique
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
    assert not frame[always_applicable].isna().any().any()
    assert set(frame["universal_t0_linear_features_version"]) == {"g40_p1_linear_v4"}
    assert set(frame["fcidump_symmetry_status"]) == {
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
    assert report["output_feature_table_sha256"] == _sha256(TABLE)
    assert report["initial_job_id"] == "7651290.imgt1"
    assert report["corrected_job_id"] == "7651318.imgt1"
    assert report["corrected_code_revision"].startswith("8f8348a")
    assert report["representation_pair_status"] == "passed"
    assert report["representation_pair_groups_passed"] == 2
