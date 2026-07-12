from dataclasses import replace

import numpy as np
import pytest
from pyscf import ao2mo, fci, mp

from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump, canonical_eri_key
from qb_gsee_benchmark.features.mfproto_features import (
    pyscf_solver_for_branch,
    run_mean_field,
)
from qb_gsee_benchmark.features.mfproto_mp2 import _masked_amplitude, run_mp2
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
