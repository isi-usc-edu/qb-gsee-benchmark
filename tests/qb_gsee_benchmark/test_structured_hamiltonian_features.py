# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

import gzip
import json
from pathlib import Path

import numpy as np

from qb_gsee_benchmark.features.fragment_features import (
    FRAGMENT_FEATURE_COLUMNS,
    compute_fragment_features,
    infer_equal_size_fragment_partition,
)
from qb_gsee_benchmark.features.pair_structure_features import (
    PAIR_STRUCTURE_FEATURE_COLUMNS,
    compute_pair_structure_features,
)
from qb_gsee_benchmark.features.representation_features import (
    REPRESENTATION_COVARIANT_NAMES,
    REPRESENTATION_FEATURE_COLUMNS,
    REPRESENTATION_INVARIANT_NAMES,
    compute_representation_features,
)
from qb_gsee_benchmark.features.sign_free_features import (
    SIGN_FREE_FEATURE_COLUMNS,
    detect_sign_free_features,
)


def test_structured_feature_contract_has_62_unique_columns():
    columns = (
        *REPRESENTATION_FEATURE_COLUMNS,
        *FRAGMENT_FEATURE_COLUMNS,
        *SIGN_FREE_FEATURE_COLUMNS,
        *PAIR_STRUCTURE_FEATURE_COLUMNS,
    )
    assert len(columns) == len(set(columns)) == 62


def test_representation_invariants_and_covariants_under_rotation():
    h1 = np.array([[-1.0, 0.2], [0.2, 0.5]])
    eri = np.arange(16, dtype=float).reshape((2,) * 4) / 20.0
    theta = 0.37
    rotation = np.array(
        [[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]]
    )
    rotated_h1 = rotation.T @ h1 @ rotation
    rotated_eri = np.einsum(
        "pa,qb,rc,sd,pqrs->abcd",
        rotation,
        rotation,
        rotation,
        rotation,
        eri,
        optimize=True,
    )
    kwargs = {
        "num_electrons": 2,
        "ms2": 0,
        "ecore_hartree": 0.3,
        "fci_energy_hartree": -1.2,
        "equivalence_group_id": "pair-1",
    }
    source = compute_representation_features(
        h1, eri, orbital_representation="source", **kwargs
    )
    rotated = compute_representation_features(
        rotated_h1, rotated_eri, orbital_representation="rotated", **kwargs
    )
    for name in REPRESENTATION_INVARIANT_NAMES:
        assert np.isclose(source[name], rotated[name])
    assert source["representation_invariant_feature_names"] == list(
        REPRESENTATION_INVARIANT_NAMES
    )
    assert source["representation_covariant_feature_names"] == list(
        REPRESENTATION_COVARIANT_NAMES
    )
    assert not np.isclose(
        source["h1_offdiag_frobenius"], rotated["h1_offdiag_frobenius"]
    )


def test_fragment_detector_keeps_oracle_and_inferred_tracks():
    h1 = np.diag([1.0, 2.0, 3.0, 4.0])
    h1[0, 2] = h1[2, 0] = 0.5
    eri = np.zeros((4,) * 4)
    for index in range(4):
        eri[(index,) * 4] = index + 1.0
    eri[0, 0, 2, 2] = eri[2, 2, 0, 0] = 0.25
    inferred = infer_equal_size_fragment_partition([0.1, 0.2, 2.1, 2.2], 2)
    result = compute_fragment_features(
        h1,
        eri,
        oracle_assignment=[0, 0, 1, 1],
        inferred_assignment=inferred,
        fragment_count=2,
        h2_bond_length_angstrom=0.74,
        fragment_center_separation_angstrom=2.0,
        lambda_interfragment=0.5,
        calibration_role="physical_grid",
    )
    assert result["fragment_partition_assignments_agree"] is True
    assert result["fragment_ml_default_track"] == "inferred_orbital_centers"
    assert result["fragment_oracle_permission"] == "calibration_and_audit_only"
    assert result["fragment_oracle_one_body_inter_intra_ratio"] > 0.0


def test_sign_free_detector_preregistered_cases():
    attractive = detect_sign_free_features(
        lattice_model_family="hubbard",
        bipartite=True,
        filling=0.75,
        interaction=-4.0,
        ms2=0,
    )
    repulsive = detect_sign_free_features(
        lattice_model_family="hubbard",
        bipartite=True,
        filling=1.0,
        interaction=4.0,
        ms2=0,
    )
    spinless = detect_sign_free_features(
        lattice_model_family="spinless_t_v_2d",
        bipartite=True,
        filling=5 / 16,
        interaction=2.0,
        ms2=5,
        spinless=True,
    )
    assert attractive["sign_free_condition_flag"] is True
    assert repulsive["sign_free_condition"] == "repulsive_hubbard_half_filled_bipartite"
    assert spinless["sign_free_condition_flag"] is False


def test_pair_structure_matches_checked_in_h2_feature_row():
    repo = Path(__file__).resolve().parents[2]
    path = (
        repo
        / "scripts"
        / "development"
        / "validation.H2.cc-PVDZ.bbcd09f2-8a89-4f35-9577-7851a76ea17c.fcidump.gz"
    )
    assert path.exists()
    result = compute_pair_structure_features(path, coverage_group="diatomic")
    expected = {
        "eri_full_l2_norm": 5.876668535646244,
        "pair_scattering_eri_l2_fraction": 0.011073294883807462,
        "mp2_os_corr_energy_hartree": -0.026380614774785312,
        "mp2_ss_corr_energy_hartree": 0.0,
    }
    for key, value in expected.items():
        assert np.isclose(result[key], value, atol=1.0e-12)
    assert result["g24_coverage_group"] == "diatomic"
    assert result["mp2_spin_decomposition_status"] == "ok"
