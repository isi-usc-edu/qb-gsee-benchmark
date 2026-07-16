import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qb_gsee_benchmark.features.feature_schema import (
    P1B_AUDIT,
    P1B_MODEL,
    P1C_AUDIT,
    P1C_BAS_MODEL,
    P1C_BAS_ORD_MODEL,
    P1D_AUDIT,
    P1D_MODEL,
    PLANNED_COLUMNS,
    metadata_catalog,
    metadata_for_column,
    model_eligible_columns,
)
from qb_gsee_benchmark.features.integral_features import (
    fermionic_coefficient_l1_norm,
    log10_fci_dimension,
)

ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "scripts" / "Hamiltonian_features.csv"
OUT = ROOT / "analysis" / "feature_schema"


def test_log10_fci_dimension_uses_fcidump_ms2_convention() -> None:
    assert log10_fci_dimension(4, 4, 0) == pytest.approx(math.log10(36))
    assert log10_fci_dimension(10, 6, 2) == pytest.approx(
        math.log10(math.comb(10, 4) * math.comb(10, 2))
    )


@pytest.mark.parametrize("norb, nelec, ms2", [(4, 3, 0), (2, 6, 0), (4, 2, 6)])
def test_log10_fci_dimension_rejects_invalid_sectors(
    norb: int, nelec: int, ms2: int
) -> None:
    with pytest.raises(ValueError):
        log10_fci_dimension(norb, nelec, ms2)


def test_fermionic_coefficient_norm_uses_effective_one_body() -> None:
    h1 = np.array([[2.0, -1.0], [-1.0, 3.0]])
    eri = np.zeros((2, 2, 2, 2))
    eri[0, 1, 1, 0] = 4.0

    # h_tilde[0,0] is reduced by 2; the two-body contribution is also 2.
    assert fermionic_coefficient_l1_norm(h1, eri) == pytest.approx(7.0)


def test_fermionic_coefficient_norm_is_basis_dependent() -> None:
    h1 = np.diag([1.0, 0.0])
    eri = np.zeros((2, 2, 2, 2))
    rotation = np.array([[1.0, -1.0], [1.0, 1.0]]) / math.sqrt(2.0)
    rotated_h1 = rotation.T @ h1 @ rotation

    assert fermionic_coefficient_l1_norm(h1, eri) == pytest.approx(1.0)
    assert fermionic_coefficient_l1_norm(rotated_h1, eri) == pytest.approx(2.0)


def test_schema_classifies_every_current_column_once() -> None:
    columns = list(pd.read_csv(FEATURES, nrows=0).columns)
    catalog = metadata_catalog(columns)

    assert len(catalog) == len(columns) + len(set(PLANNED_COLUMNS) - set(columns))
    assert len({row.column for row in catalog}) == len(catalog)


def test_p0_eligibility_and_retags_are_explicit() -> None:
    log_dimension = metadata_for_column("log_fci_dim")
    assert log_dimension.model_eligible
    assert log_dimension.implementation_status == "current"
    assert metadata_for_column("df_gap").representation == "INV"
    assert metadata_for_column("one_norm").representation == "BAS+ORD"
    assert (
        metadata_for_column("det_coupling_nonzero_degree").representation == "BAS+ORD"
    )
    assert (
        metadata_for_column("random_det_expected_degree_rel_1e_8").representation
        == "BAS+ORD"
    )
    assert metadata_for_column("cut_weight_rcm_max").representation == "BAS+ORD"
    assert (
        metadata_for_column("cut_weight_minimum_degree_sum").representation == "BAS+ORD"
    )
    assert (
        metadata_for_column("cut_weight_heuristic_spread_p95").representation
        == "BAS+ORD"
    )
    assert metadata_for_column("cut_weight_fiedler_max").representation == "BAS+ORD"
    assert (
        metadata_for_column("cut_weight_linear_relaxation_sum").representation
        == "BAS+ORD"
    )
    assert metadata_for_column("cut_weight_best_p95").representation == "BAS+ORD"
    assert metadata_for_column("min_fill_width_upper_bound").representation == "BAS+ORD"
    assert (
        metadata_for_column("det_coupling_reference_boundary_tie").representation
        == "BAS+ORD"
    )
    assert metadata_for_column("mpo_pair_rank_applicable").representation == "BAS"
    assert (
        metadata_for_column("interaction_spectrum_effective_rank").representation
        == "INV"
    )
    assert metadata_for_column("interaction_spectrum_effective_rank").model_eligible
    assert not metadata_for_column(
        "interaction_spectrum_negative_mass_fraction"
    ).model_eligible
    for column in (
        "df_rank",
        "df_gap",
        "df_eig_decay_exponent",
        "df_rank_per_orbital",
        "df_eigs",
        "df_eig_decay_r2",
        "df_eig_decay_npoints",
    ):
        assert not metadata_for_column(column).model_eligible
        assert metadata_for_column(column).exclusion_reason == (
            "superseded by exact invariant interaction-spectrum block - "
            "different threshold conventions"
        )
    assert not metadata_for_column("one_norm").model_eligible
    assert not metadata_for_column("ccsd_t1_diagnostic").model_eligible
    assert not metadata_for_column("sign_free_condition_flag").model_eligible

    columns = list(pd.read_csv(FEATURES, nrows=0).columns)
    eligible = model_eligible_columns(columns)
    assert "log_fci_dim" in eligible
    assert "one_norm" not in eligible
    assert "df_rank" not in eligible
    assert "df_gap" not in eligible
    assert "ccsd_t1_diagnostic" not in eligible
    assert "fermionic_coefficient_l1_norm" in eligible


def test_mp2_amplitude_statistics_are_annotated_at_exact_degeneracy() -> None:
    columns = list(pd.read_csv(FEATURES, nrows=0).columns)
    catalog = metadata_catalog(columns, include_planned=False)
    sensitive = [row for row in catalog if row.gauge_sensitive_at_degeneracy]

    assert len(sensitive) == 46
    assert {row.gauge_sensitivity_explanation for row in sensitive} == {
        "Elementwise MP2 amplitude statistic; rotations within exactly "
        "degenerate occupied or virtual orbital subspaces can change this "
        "value while rotation-invariant energies and L2 norms remain unchanged."
    }
    assert metadata_for_column("mp2_amplitude_l1_norm").gauge_sensitive_at_degeneracy
    assert metadata_for_column(
        "mp2_kappa_1p45_same_spin_amplitude_top_16_l2_mass_fraction"
    ).gauge_sensitive_at_degeneracy
    assert metadata_for_column(
        "mp2_pair_double_amplitude_l1_fraction"
    ).gauge_sensitive_at_degeneracy
    for invariant in (
        "mp2_amplitude_l2_norm",
        "mp2_correlation_energy_per_electron_hartree",
        "mp2_denominator_inverse_second_moment",
    ):
        metadata = metadata_for_column(invariant)
        assert metadata.gauge_sensitive_at_degeneracy is False
        assert metadata.gauge_sensitivity_explanation == ""


def test_generated_p0_artifacts_are_deterministic_and_value_preserving(
    tmp_path: Path,
) -> None:
    before = FEATURES.read_bytes()
    first_out = tmp_path / "first"
    second_out = tmp_path / "second"

    def generate(output_dir: Path) -> dict[str, bytes]:
        command = [
            sys.executable,
            str(ROOT / "scripts" / "build_g40_p0_artifacts.py"),
            "--output-dir",
            str(output_dir),
        ]
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
        return {
            path.name: path.read_bytes()
            for path in output_dir.iterdir()
            if path.is_file()
        }

    first = generate(first_out)
    second = generate(second_out)

    assert FEATURES.read_bytes() == before
    assert second == first
    for name, contents in first.items():
        assert (OUT / name).read_bytes() == contents

    manifest = json.loads((first_out / "g40_p0_model_manifest.json").read_text())
    assert manifest["source_feature_table_sha256"]
    assert "one_norm" in manifest["excluded_columns"]
    assert "ccsd_t1_diagnostic" in manifest["excluded_columns"]
    assert manifest["pending_value_rebuild_columns"] == []
    planned = manifest["planned_columns_excluded_until_populated"]
    current_columns = set(pd.read_csv(FEATURES, nrows=0).columns)
    assert planned == {
        "pending_model_eligible": sorted(
            (P1B_MODEL | P1C_BAS_MODEL | P1C_BAS_ORD_MODEL | P1D_MODEL)
            - current_columns
        ),
        "permanently_audit_only": sorted(
            (P1B_AUDIT | P1C_AUDIT | P1D_AUDIT) - current_columns
        ),
    }

    with (first_out / "feature_column_metadata.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    columns = list(pd.read_csv(FEATURES, nrows=0).columns)
    assert len(rows) == len(columns) + len(set(PLANNED_COLUMNS) - set(columns))
    assert (first_out / "g40_p0_appendix_divergences.md").is_file()
