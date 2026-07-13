import numpy as np
from pathlib import Path
from types import SimpleNamespace
import pytest

from qb_gsee_benchmark.features.fcidump_sparse import (
    SparseFcidump,
    read_sparse_fcidump,
)
from qb_gsee_benchmark.features.mfproto_features import (
    _coordinate_pinned_basis,
    _select_branch,
    canonical_eigh,
    configure_newton_fallback,
    fermi_occupations,
    initial_spin_density_guesses,
    mean_field_feature_values,
    occupation_boundary_tie,
    particle_sector,
    run_mean_field,
    spectral_panel,
)


def test_particle_sector_validates_parity_and_bounds() -> None:
    sector = particle_sector(6, 7, 3)
    assert (sector.nalpha, sector.nbeta) == (5, 2)
    with pytest.raises(ValueError, match="parity"):
        particle_sector(6, 7, 0)
    with pytest.raises(ValueError, match="fit NORB"):
        particle_sector(2, 6, 0)


def test_canonical_eigh_resolves_degenerate_subspace_by_shipped_index() -> None:
    rotation = np.array(
        [
            [1.0 / np.sqrt(2.0), -1.0 / np.sqrt(2.0), 0.0],
            [1.0 / np.sqrt(2.0), 1.0 / np.sqrt(2.0), 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    matrix = rotation @ np.diag([0.0, 0.0, 2.0]) @ rotation.T
    result = canonical_eigh(matrix)
    np.testing.assert_allclose(result.eigenvalues, [0.0, 0.0, 2.0], atol=1e-14)
    np.testing.assert_allclose(result.eigenvectors, np.eye(3), atol=1e-14)
    assert result.minimum_adjacent_split == 0.0
    assert result.degenerate_subspace_count == 1


def test_fermi_bisection_conserves_particles_and_handles_edge_sectors() -> None:
    values = np.array([-2.0, -0.5, 0.3, 1.7])
    occupations, chemical_potential = fermi_occupations(values, 2, 0.25)
    assert abs(np.sum(occupations) - 2.0) < 1e-13
    assert values[1] < chemical_potential < values[2]
    np.testing.assert_array_equal(fermi_occupations(values, 0, 0.25)[0], 0.0)
    np.testing.assert_array_equal(fermi_occupations(values, 4, 0.25)[0], 1.0)


def test_all_four_guesses_conserve_spin_particles_and_g3_spills() -> None:
    h1 = np.diag([-3.0, -2.0, -1.0, 0.0, 1.0])
    guesses = initial_spin_density_guesses(h1, nelec=7, ms2=1)
    assert list(guesses) == ["G1", "G2", "G3", "G4"]
    for alpha, beta in guesses.values():
        assert np.trace(alpha) == pytest.approx(4.0, abs=2e-13)
        assert np.trace(beta) == pytest.approx(3.0, abs=2e-13)
        np.testing.assert_allclose(alpha, alpha.T, atol=1e-14)
        np.testing.assert_allclose(beta, beta.T, atol=1e-14)
    np.testing.assert_array_equal(np.diag(guesses["G3"][0]), [1, 1, 1, 0, 1])
    np.testing.assert_array_equal(np.diag(guesses["G3"][1]), [1, 1, 0, 1, 0])


def test_boundary_tie_and_spectral_panel_follow_inclusive_rules() -> None:
    values = np.array([-1.0, 0.0, 0.0, 0.1, 2.0])
    assert occupation_boundary_tie(values, 2)
    panel = spectral_panel(values, np.eye(5), particles=3)
    assert panel["applicable"]
    assert panel["gap"] == pytest.approx(0.1)
    assert panel["center"] == pytest.approx(0.05)
    assert panel["ipr_window_orbital_count_0.1"] == 3
    assert panel["ipr_window_0.1_applicable"] is True
    assert panel["ipr_window_0.1_reason"] is None
    assert panel["ipr_window_0.1"] == pytest.approx(1.0 / 3.0)
    assert 0.0 <= panel["thermal_active_fraction_kt_0.1"] <= 1.0
    assert panel["dos_total_eta_0.05"] > 0.0
    assert panel["dos_per_orbital_eta_0.05"] == pytest.approx(
        panel["dos_total_eta_0.05"] / 5.0
    )


def test_spectral_panel_masks_empty_and_full_spin_sectors() -> None:
    values = np.array([-1.0, 1.0])
    for particles in (0, 2):
        panel = spectral_panel(values, np.eye(2), particles)
        assert panel["applicable"] is False
        assert panel["reason"] == "empty_or_full_spin_sector"
        assert panel["gap"] is None
        assert panel["thermal_active_fraction_kt_0.1"] is None
        assert panel["dos_total_eta_0.05"] is None
        assert panel["ipr_window_0.1_applicable"] is False
        assert panel["ipr_window_0.1_reason"] == "empty_or_full_spin_sector"
        assert panel["ipr_window_0.1"] is None


def test_spectral_panel_masks_empty_projector_windows_independently() -> None:
    panel = spectral_panel(np.array([-1.0, 1.0]), np.eye(2), particles=1)
    for width in ("0.1", "0.5"):
        assert panel[f"ipr_window_{width}_applicable"] is False
        assert panel[f"ipr_window_{width}_reason"] == "empty_spectral_projector"
        assert panel[f"ipr_window_{width}"] is None


def _sparse_data(norb: int, nelec: int, ms2: int, h1: np.ndarray) -> SparseFcidump:
    return SparseFcidump(
        norb=norb,
        nelec=nelec,
        ms2=ms2,
        h1=h1,
        eri_records={},
        ecore=0.0,
        one_body_duplicate_orientations=0,
        one_body_duplicate_max_abs_difference=0.0,
        one_body_duplicate_max_rel_difference=0.0,
        one_body_symmetry_conflict_records=0,
        two_body_input_records=0,
        two_body_duplicate_orientations=0,
        two_body_duplicate_max_abs_difference=0.0,
        two_body_duplicate_max_rel_difference=0.0,
        two_body_symmetry_conflict_records=0,
        container_format="plain",
        container_member=None,
        ms2_source="test",
    )


def test_mean_field_panel_runs_all_closed_shell_branches_and_deduplicates() -> None:
    data = _sparse_data(2, 2, 0, np.diag([-1.0, 1.0]))
    result = run_mean_field(data)
    assert [(branch.method, branch.guess) for branch in result.branches] == [
        (method, guess)
        for method in ("RHF", "UHF")
        for guess in ("G1", "G2", "G3", "G4")
    ]
    assert all(branch.converged for branch in result.branches)
    assert not any(branch.fallback_used for branch in result.branches)
    assert result.components == [list(range(8))]
    assert result.selected_branch_index == 0
    features = mean_field_feature_values(result)
    assert features["mf_distinct_solution_count"] == 1
    assert features["mf_selected_method"] == "RHF"
    assert features["mf_selected_guess"] == "G1"
    assert features["mf_selected_energy_hartree"] == pytest.approx(-2.0)
    assert features["mf_symmetry_breaking_energy_hartree"] == pytest.approx(0.0)
    assert features["mf_symmetry_breaking_applicable"] is True
    assert features["mf_symmetry_breaking_reason"] is None
    assert features["mf_selected_fock_gap_min_hartree"] == pytest.approx(2.0)
    assert features["mf_gap_mismatch_min_applicable"] is True
    assert features["mf_gap_mismatch_min_hartree"] == pytest.approx(0.0)


def test_mean_field_open_shell_runs_only_uhf_and_masks_empty_beta_gap() -> None:
    data = _sparse_data(3, 1, 1, np.diag([-2.0, 0.0, 2.0]))
    result = run_mean_field(data)
    assert len(result.branches) == 4
    assert all(branch.method == "UHF" for branch in result.branches)
    assert all(branch.converged for branch in result.branches)
    features = mean_field_feature_values(result)
    assert features["mf_lowest_rhf_energy_hartree"] is None
    assert features["mf_symmetry_breaking_applicable"] is False
    assert features["mf_symmetry_breaking_reason"] == "ms2_nonzero"
    assert features["mf_selected_fock_beta_applicable"] is False
    assert features["mf_selected_fock_beta_reason"] == "empty_or_full_spin_sector"
    assert features["mf_selected_fock_beta_thermal_active_fraction_kt_0.1"] is None
    assert features["mf_selected_fock_beta_ipr_window_0.1_applicable"] is False
    assert features["mf_selected_s2"] == pytest.approx(0.75)


def test_newton_fallback_controls_are_all_overridden() -> None:
    class Solver:
        max_cycle = None
        max_cycle_inner = None
        max_stepsize = None
        ah_start_cycle = None
        ah_start_tol = None
        ah_conv_tol = None
        ah_lindep = None
        ah_max_cycle = None
        ah_level_shift = None
        ah_grad_trust_region = None
        kf_interval = None
        kf_trust_region = None
        conv_tol = None
        conv_tol_grad = None

    solver = configure_newton_fallback(Solver())
    assert solver.max_cycle == 50
    assert solver.max_cycle_inner == 12
    assert solver.max_stepsize == 0.05
    assert solver.ah_start_tol == 1.0e9
    assert solver.ah_conv_tol == 1.0e-12
    assert solver.ah_lindep == 1.0e-14
    assert solver.ah_grad_trust_region == 2.5
    assert solver.kf_interval == 4
    assert solver.kf_trust_region == 5


def test_recursive_coordinate_pin_is_independent_of_subspace_rotation() -> None:
    subspace = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 0.0],
            [0.0, 0.0],
        ]
    )
    angle = 0.731
    rotation = np.array(
        [
            [np.cos(angle), -np.sin(angle)],
            [np.sin(angle), np.cos(angle)],
        ]
    )
    np.testing.assert_allclose(
        _coordinate_pinned_basis(subspace),
        _coordinate_pinned_basis(subspace @ rotation),
        atol=1.0e-14,
    )


def test_real_lattice_fixtures_exercise_recursive_projected_index_pin() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "g40_permutation_pairs"
    for name in (
        "qsz_l4x4_u2_original.FCIDUMP",
        "varbench_tv_square16_v0p01_original.FCIDUMP",
    ):
        spectrum = canonical_eigh(read_sparse_fcidump(fixture_root / name).h1)
        assert spectrum.projected_index_tied_subspace_count >= 1


def test_degeneracy_hysteresis_absorbs_scf_noise_scale_split() -> None:
    spectrum = canonical_eigh(np.diag([0.0, 1.304e-10, 2.0]))
    assert spectrum.degenerate_subspace_count == 1
    assert spectrum.hysteresis_band_split_count == 1


def test_selection_tie_band_uses_guess_then_explicit_method_order() -> None:
    branches = [
        SimpleNamespace(energy=-1.0, guess="G2", method="UHF"),
        SimpleNamespace(energy=-1.0 + 5.0e-11, guess="G1", method="UHF"),
        SimpleNamespace(energy=-1.0 + 7.0e-11, guess="G1", method="RHF"),
    ]
    assert _select_branch([0, 1, 2], branches) == 2
