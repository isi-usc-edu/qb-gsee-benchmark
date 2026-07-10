from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from scripts.polyene_ladder import generate_polyene_ladder as generator


def test_polyene_geometry_matches_frozen_hachmann_parameters():
    for k in generator.MEMBERS:
        atoms = generator.polyene_geometry(k)
        carbons = np.asarray([coords for symbol, coords in atoms if symbol == "C"])
        hydrogens = np.asarray([coords for symbol, coords in atoms if symbol == "H"])

        assert len(carbons) == k
        assert len(hydrogens) == k + 2
        assert np.max(np.abs(np.concatenate((carbons[:, 2], hydrogens[:, 2])))) == 0.0

        carbon_distances = np.linalg.norm(np.diff(carbons, axis=0), axis=1)
        expected_distances = np.asarray(
            [
                generator.CC_DOUBLE_ANGSTROM
                if index % 2 == 0
                else generator.CC_SINGLE_ANGSTROM
                for index in range(k - 1)
            ]
        )
        assert carbon_distances == pytest.approx(expected_distances, abs=1.0e-12)

        for index in range(1, k - 1):
            left = carbons[index - 1] - carbons[index]
            right = carbons[index + 1] - carbons[index]
            cosine = np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right))
            assert math.degrees(math.acos(float(cosine))) == pytest.approx(
                generator.BOND_ANGLE_DEGREES, abs=1.0e-12
            )

        nearest_ch = np.min(
            np.linalg.norm(hydrogens[:, None, :] - carbons[None, :, :], axis=2),
            axis=1,
        )
        assert nearest_ch == pytest.approx(generator.CH_ANGSTROM, abs=1.0e-12)


def test_c4_generation_reproduces_rhf_fci_and_historical_crosscheck(tmp_path: Path):
    row = generator.build_member(4, tmp_path, run_fci=True)
    certificate = row["fci_certificate"]
    historical = row["historical_crosscheck_only"]

    assert abs(row["rhf_consistency_delta_hartree"]) < 1.0e-9
    assert row["active_orthonormality_max_abs"] < 1.0e-10
    assert certificate["determinant_dimension"] == 36
    assert certificate["root_residual_l2_hartree"] < 1.0e-10
    assert certificate["energy_hartree"] == pytest.approx(
        -153.0978661842132, abs=1.0e-10
    )
    assert abs(historical["our_minus_historical_total_hartree"]) < 1.0e-6
    assert (tmp_path / row["fcidump"]).is_file()
    assert (tmp_path / row["fcidump_gzip"]).is_file()
    assert (tmp_path / row["generation_sidecar"]).is_file()
