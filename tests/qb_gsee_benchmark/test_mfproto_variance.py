from dataclasses import replace

import numpy as np
import pytest
from pyscf import ao2mo, fci, mp

from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump, canonical_eri_key
from qb_gsee_benchmark.features.mfproto_features import (
    pyscf_solver_for_branch,
    run_mean_field,
)
from qb_gsee_benchmark.features.mfproto_mp2 import (
    KAPPA_GRID,
    _kappa_features,
    _masked_amplitude,
    _masked_amplitude_summary,
    _regularized_amplitude,
    run_mp2,
)
from qb_gsee_benchmark.features.mfproto_variance import exact_hf_variance


def _random_symmetric_data() -> SparseFcidump:
    rng = np.random.default_rng(7)
    norb = 3
    raw = rng.normal(scale=0.08, size=(norb,) * 4)
    eri = np.zeros_like(raw)
    for p in range(norb):
        for q in range(norb):
            for r in range(norb):
                for s in range(norb):
                    eri[p, q, r, s] = np.mean(
                        [
                            raw[p, q, r, s],
                            raw[q, p, r, s],
                            raw[p, q, s, r],
                            raw[q, p, s, r],
                            raw[r, s, p, q],
                            raw[s, r, p, q],
                            raw[r, s, q, p],
                            raw[s, r, q, p],
                        ]
                    )
    records = {
        canonical_eri_key(p, q, r, s): eri[p, q, r, s]
        for p in range(norb)
        for q in range(norb)
        for r in range(norb)
        for s in range(norb)
    }
    return SparseFcidump(
        norb=3,
        nelec=2,
        ms2=0,
        h1=np.diag([-1.0, 0.2, 1.3]),
        eri_records=records,
        ecore=0.0,
        one_body_duplicate_orientations=0,
        one_body_duplicate_max_abs_difference=0.0,
        one_body_duplicate_max_rel_difference=0.0,
        one_body_symmetry_conflict_records=0,
        two_body_input_records=len(records),
        two_body_duplicate_orientations=0,
        two_body_duplicate_max_abs_difference=0.0,
        two_body_duplicate_max_rel_difference=0.0,
        two_body_symmetry_conflict_records=0,
        container_format="plain",
        container_member=None,
        ms2_source="test",
    )


def test_exact_hf_variance_matches_full_ci_off_diagonal_norm() -> None:
    data = _random_symmetric_data()
    result = run_mean_field(data)
    selected = result.selected
    assert selected is not None and selected.method == "RHF"
    dense_eri = data.dense_eri()
    variance = exact_hf_variance(dense_eri, selected, result.sector)

    orbitals = selected.orbitals_alpha
    h1_mo = orbitals.T @ data.h1 @ orbitals
    eri_mo = np.einsum(
        "pqrs,pi,qj,rk,sl->ijkl",
        dense_eri,
        orbitals,
        orbitals,
        orbitals,
        orbitals,
        optimize=True,
    )
    addresses, hamiltonian = fci.direct_spin1.pspace(
        h1_mo, eri_mo, data.norb, (1, 1), np=100
    )
    reference = int(np.where(addresses == 0)[0][0])
    oracle = float(
        np.sum(hamiltonian[:, reference] ** 2) - hamiltonian[reference, reference] ** 2
    )
    assert variance.total == pytest.approx(oracle, abs=5e-15)
    assert variance.per_electron == pytest.approx(oracle / 2.0, abs=5e-15)


def test_noninteracting_eigenstate_has_zero_variance() -> None:
    data = _random_symmetric_data()
    data = SparseFcidump(
        **{**data.__dict__, "eri_records": {}, "two_body_input_records": 0}
    )
    result = run_mean_field(data)
    variance = exact_hf_variance(data.dense_eri(), result.selected, result.sector)
    assert variance.total == pytest.approx(0.0, abs=1e-24)


def _native_mp2_energy(data, selected):
    dense_eri = data.dense_eri()
    solver = pyscf_solver_for_branch(data, dense_eri, selected)
    solver._eri = ao2mo.restore(8, dense_eri, data.norb)
    native = mp.MP2(solver)
    native.verbose = 0
    native.kernel()
    return native


def test_rmp2_panels_match_native_pyscf_energy_and_spin_split() -> None:
    data = _random_symmetric_data()
    mean_field = run_mean_field(data)
    selected = mean_field.selected
    result = run_mp2(data, data.dense_eri(), selected, mean_field.sector)
    native = _native_mp2_energy(data, selected)
    assert result.features["mp2_reference"] == "RMP2"
    assert result.features["mp2_correlation_energy_hartree"] == pytest.approx(
        native.e_corr, abs=1e-15
    )
    assert result.features["mp2_same_spin_correlation_energy_hartree"] == pytest.approx(
        native.e_corr_ss, abs=1e-15
    )
    assert result.features[
        "mp2_opposite_spin_correlation_energy_hartree"
    ] == pytest.approx(native.e_corr_os, abs=1e-15)
    assert result.features["mp2_natural_occupation_applicable"] is True


def test_ump2_panels_match_native_pyscf_energy_and_spin_split() -> None:
    data = replace(_random_symmetric_data(), nelec=3, ms2=1)
    mean_field = run_mean_field(data)
    selected = mean_field.selected
    result = run_mp2(data, data.dense_eri(), selected, mean_field.sector)
    native = _native_mp2_energy(data, selected)
    assert result.features["mp2_reference"] == "UMP2"
    assert result.features["mp2_correlation_energy_hartree"] == pytest.approx(
        native.e_corr, abs=1e-15
    )
    assert result.features["mp2_same_spin_correlation_energy_hartree"] == pytest.approx(
        native.e_corr_ss, abs=1e-15
    )
    assert result.features[
        "mp2_opposite_spin_correlation_energy_hartree"
    ] == pytest.approx(native.e_corr_os, abs=1e-15)


def test_mp2_small_denominators_are_masked_from_amplitudes() -> None:
    integrals = np.array([1.0, 2.0])
    denominators = np.array([1.0e-7, -2.0])
    amplitudes, mask = _masked_amplitude(integrals, denominators)
    np.testing.assert_array_equal(mask, [True, False])
    np.testing.assert_allclose(amplitudes, [0.0, -1.0])


def test_kappa_regularization_retains_small_denominator_terms() -> None:
    denominator = np.array([1.0e-7, 0.0, -2.0])
    numerator = np.array([4.0, 9.0, 16.0])
    masked_energy = np.array([0.0, 0.0, -8.0])
    features = _kappa_features(
        [masked_energy],
        [numerator],
        [denominator],
        unregularized_applicable=True,
        unregularized_partial_mask=True,
    )

    assert features["mp2_kappa_inf_correlation_energy_hartree"] == -8.0
    for kappa in KAPPA_GRID:
        label = str(kappa).replace(".", "p")
        damping = 1.0 - np.exp(-kappa * np.abs(denominator))
        expected = np.sum(
            numerator
            * np.divide(
                damping**2,
                denominator,
                out=np.zeros_like(denominator),
                where=denominator != 0.0,
            )
        )
        assert features[
            f"mp2_kappa_{label}_correlation_energy_hartree"
        ] == pytest.approx(expected, abs=1e-15)
        masked_only = -8.0 * damping[-1] ** 2
        assert abs(expected - masked_only) > 1.0e-8
        regularized = _regularized_amplitude(numerator, denominator, kappa)
        assert regularized[0] != 0.0
        assert regularized[1] == pytest.approx(-kappa * numerator[1], abs=1e-15)


def test_fully_masked_unregularized_panels_are_not_encoded_as_zero() -> None:
    values = np.array([0.0, 0.0])
    mask = np.array([True, True])
    amplitudes = _masked_amplitude_summary(values, mask, "test_amplitude")
    assert amplitudes["test_amplitude_applicable"] is False
    assert amplitudes["test_amplitude_reason"] == "all_amplitudes_masked"
    assert amplitudes["test_amplitude_partial_mask"] is True
    assert amplitudes["test_amplitude_max_abs"] is None

    denominator = np.array([-1.0e-8])
    kappa = _kappa_features(
        [np.array([0.0])],
        [np.array([4.0])],
        [denominator],
        unregularized_applicable=False,
        unregularized_partial_mask=True,
    )
    assert kappa["mp2_kappa_inf_applicable"] is False
    assert kappa["mp2_kappa_inf_correlation_energy_hartree"] is None
    assert kappa["mp2_kappa_1p45_correlation_energy_hartree"] != 0.0
    assert kappa["mp2_kappa_1p45_vs_inf_difference_hartree"] is None
    assert kappa["mp2_kappa_1p45_vs_inf_difference_applicable"] is False


def test_rmp2_amplitude_spin_blocks_match_equivalent_ump2() -> None:
    data = _random_symmetric_data()
    mean_field = run_mean_field(data)
    selected = mean_field.selected
    restricted = run_mp2(data, data.dense_eri(), selected, mean_field.sector)
    unrestricted = run_mp2(
        data,
        data.dense_eri(),
        replace(selected, method="UHF"),
        mean_field.sector,
    )
    for label in ("inf", "1p45", "1p1"):
        key = f"mp2_kappa_{label}_correlation_energy_hartree"
        assert restricted.features[key] == pytest.approx(
            unrestricted.features[key], abs=1e-14
        )
    for prefix in (
        "mp2_amplitude",
        "mp2_same_spin_amplitude",
        "mp2_opposite_spin_amplitude",
    ):
        for suffix in (
            "max_abs",
            "l1_norm",
            "l2_norm",
            "participation_ratio",
            "top_16_l2_mass_fraction",
            "top_128_l2_mass_fraction",
        ):
            assert restricted.features[f"{prefix}_{suffix}"] == pytest.approx(
                unrestricted.features[f"{prefix}_{suffix}"], abs=1e-14
            )
    for label in ("1p45", "1p1"):
        for spin in ("", "same_spin_", "opposite_spin_"):
            prefix = f"mp2_kappa_{label}_{spin}amplitude"
            for suffix in (
                "max_abs",
                "l1_norm",
                "l2_norm",
                "participation_ratio",
                "top_16_l2_mass_fraction",
                "top_128_l2_mass_fraction",
            ):
                assert restricted.features[f"{prefix}_{suffix}"] == pytest.approx(
                    unrestricted.features[f"{prefix}_{suffix}"], abs=1e-14
                )
