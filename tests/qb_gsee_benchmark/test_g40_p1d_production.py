import hashlib
import json
from pathlib import Path

import pandas as pd

from qb_gsee_benchmark.features.feature_schema import P1D_AUDIT, P1D_MODEL

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "feature_schema"
TABLE = ROOT / "scripts" / "Hamiltonian_features.csv"


def test_p1d_production_report_binds_full_additive_merge() -> None:
    report = json.loads((OUT / "g40_p1d_production_report.json").read_text())
    r6 = json.loads((OUT / "g40_r6_production_report.json").read_text())
    p2 = json.loads((OUT / "g40_p2_production_report.json").read_text())

    assert report["report_version"] == "g40_p1d_production_v1"
    assert report["block"] == "g40_p1d"
    assert report["code_revision"] == report["builder_revision"] == "10b5f91"
    assert report["extractor_version"] == "g40_p1d_interaction_spectrum_v1"
    assert report["successful_states"] == report["corpus_tasks"] == 591
    assert report["rows_before"] == report["rows_after"] == 591
    assert report["columns_before"] == 239
    assert report["columns_after"] == 253
    assert set(report["new_columns"]) == P1D_MODEL | P1D_AUDIT
    assert report["newly_populated_cells"] == 8267
    assert report["changed_populated_cells"] == 0
    assert report["input_feature_table_sha256"] == r6["output_feature_table_sha256"]
    assert p2["input_feature_table_sha256"] == report["output_feature_table_sha256"]
    assert (
        p2["output_feature_table_sha256"]
        == hashlib.sha256(TABLE.read_bytes()).hexdigest()
    )
    assert report["legacy_df_values_preserved"] is True
    assert (
        report["legacy_df_value_sha256_before"]
        == report["legacy_df_value_sha256_after"]
    )
    assert report["pbs"]["job_id"] == "7651579.imgt1"
    assert report["pbs"]["queue"] == "compute"
    assert report["pbs"]["exit_status"] == 0
    assert report["representation_pair_check"] == {
        "equivalence_groups": 5,
        "groups_passed": 5,
        "status": "passed",
    }


def test_p1d_production_table_has_frozen_schema_and_expected_nulls() -> None:
    frame = pd.read_csv(TABLE)
    assert frame.shape == (591, 580)
    assert set(P1D_MODEL | P1D_AUDIT) <= set(frame)
    assert set(frame["interaction_spectrum_features_version"]) == {
        "g40_p1d_interaction_spectrum_v1"
    }
    always_populated = (P1D_MODEL | P1D_AUDIT) - {"interaction_spectrum_decay_exponent"}
    assert not frame[list(always_populated)].isna().any().any()
    assert frame["interaction_spectrum_decay_exponent"].isna().sum() == 7


def test_p1d_production_preserves_real_all_zero_controls() -> None:
    frame = pd.read_csv(TABLE)
    controls = frame[frame["problem_instance_short_name"] == "tight_binding_controls"]
    assert len(controls) == 5
    zero_columns = [
        "interaction_spectrum_active_pair_dimension",
        "interaction_spectrum_rank_rel_1e_2",
        "interaction_spectrum_rank_rel_1e_4",
        "interaction_spectrum_rank_rel_1e_6",
        "interaction_spectrum_effective_rank",
        "interaction_spectrum_participation_rank",
        "interaction_spectrum_relative_gap",
        "interaction_spectrum_negative_mass_fraction",
        "interaction_spectrum_max_abs_eigenvalue",
    ]
    assert (controls[zero_columns] == 0).all().all()
    assert controls["interaction_spectrum_decay_exponent"].isna().all()


def test_p1d_production_representation_gate_is_green() -> None:
    report = json.loads(
        (OUT / "g40_p1d_production_representation_pair_check.json").read_text()
    )
    assert report["status"] == "passed"
    assert report["equivalence_groups"] == report["groups_passed"] == 5
    assert report["failures"] == []
    assert report["permutation_blocks"] == ["interaction-spectrum"]
