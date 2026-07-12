import numpy as np
import pytest

from qb_gsee_benchmark.features.mfproto_features import (
    canonical_eigh,
    fermi_occupations,
    initial_spin_density_guesses,
    occupation_boundary_tie,
    particle_sector,
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
        assert panel == {
            "applicable": False,
            "reason": "empty_or_full_spin_sector",
            "gap": None,
            "center": None,
            "edge_degenerate": None,
        }
