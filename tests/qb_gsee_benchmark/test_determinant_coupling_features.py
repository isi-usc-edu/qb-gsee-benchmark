from pathlib import Path
import hashlib

import numpy as np
import pytest
from pyscf import fci

from qb_gsee_benchmark.features.determinant_coupling_features import (
    DETERMINANT_COUPLING_VERSION,
    Occupation,
    compute_determinant_coupling_features,
    diagonal_one_body_reference,
    reference_coupling_magnitudes,
    random_determinant_branching_profile,
)
from qb_gsee_benchmark.features.corpus_runner import CorpusFcidump, cache_path
from qb_gsee_benchmark.features.determinant_coupling_runner import (
    run_determinant_coupling_task,
)

from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump

ROOT = Path(__file__).resolve().parents[2]


def _data(
    h1: np.ndarray,
    eri: dict[tuple[int, int, int, int], float],
    *,
    nelec: int = 2,
    ms2: int = 0,
) -> SparseFcidump:
    return SparseFcidump(
        norb=len(h1),
        nelec=nelec,
        ms2=ms2,
        h1=h1,
        eri_records=eri,
        ecore=0.0,
        one_body_duplicate_orientations=0,
        one_body_duplicate_max_abs_difference=0.0,
        one_body_duplicate_max_rel_difference=0.0,
        one_body_symmetry_conflict_records=0,
        two_body_input_records=len(eri),
        two_body_duplicate_orientations=0,
        two_body_duplicate_max_abs_difference=0.0,
        two_body_duplicate_max_rel_difference=0.0,
        two_body_symmetry_conflict_records=0,
        container_format="plain",
        container_member=None,
        ms2_source="fcidump_header",
    )


def test_reference_uses_lowest_diagonal_orbitals() -> None:
    data = _data(np.diag([2.0, -1.0, 0.5]), {})
    assert diagonal_one_body_reference(data) == Occupation(alpha=(1,), beta=(1,))


def test_opposite_spin_double_and_singles_are_counted() -> None:
    h1 = np.array([[0.0, 0.25], [0.25, 1.0]])
    data = _data(h1, {(0, 1, 0, 1): 0.5})
    values = np.sort(reference_coupling_magnitudes(data, Occupation((0,), (0,))))
    assert values == pytest.approx([0.25, 0.25, 0.5])

    _, determinant_hamiltonian = fci.direct_spin1.pspace(
        data.h1, data.dense_eri(), data.norb, (data.nalpha, data.nbeta), np=4
    )
    assert values == pytest.approx(np.sort(np.abs(determinant_hamiltonian[0, 1:])))


def test_open_shell_reference_row_matches_pyscf() -> None:
    rng = np.random.default_rng(17)
    h1 = np.diag([-3.0, -2.0, 1.0])
    h1[0, 1] = h1[1, 0] = 0.2
    eri = {}
    for i in range(3):
        for j in range(i, 3):
            for k in range(3):
                for l in range(k, 3):
                    key = min((i, j, k, l), (k, l, i, j))
                    eri.setdefault(key, float(rng.normal(scale=0.1)))
    data = _data(h1, eri, nelec=3, ms2=1)
    values = np.sort(reference_coupling_magnitudes(data, Occupation((0, 1), (0,))))
    addresses, determinant_hamiltonian = fci.direct_spin1.pspace(
        data.h1, data.dense_eri(), data.norb, (data.nalpha, data.nbeta), np=9
    )
    reference_row = int(np.flatnonzero(addresses == 0)[0])
    oracle = np.delete(np.abs(determinant_hamiltonian[reference_row]), reference_row)
    oracle = np.sort(oracle[oracle > 0.0])
    assert values == pytest.approx(oracle)


def test_runner_is_checksum_and_configuration_resumable(tmp_path: Path) -> None:
    source = ROOT / "tests/qb_gsee_benchmark/fcidump.h2_sto-3g"
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    record = CorpusFcidump(
        problem_instance_short_name="fixture",
        task_uuid="task",
        instance_data_object_uuid="object",
        url="https://example.invalid/FCIDUMP",
        checksum=checksum,
        checksum_type="sha256",
        file_name="FCIDUMP",
        norb_metadata=2,
        ms2_metadata=0,
    )
    cached = cache_path(tmp_path / "cache", record)
    cached.parent.mkdir(parents=True)
    cached.write_bytes(source.read_bytes())
    state_dir = tmp_path / "state"
    first = run_determinant_coupling_task(
        record,
        tmp_path / "cache",
        state_dir,
        offline=True,
        random_determinants=4,
        excitation_samples_per_class=64,
    )
    state_path = state_dir / "task.coupling.json"
    first_bytes = state_path.read_bytes()
    second = run_determinant_coupling_task(
        record,
        tmp_path / "cache",
        state_dir,
        offline=True,
        random_determinants=4,
        excitation_samples_per_class=64,
    )
    assert first["status"] == "success"
    assert second == first
    assert state_path.read_bytes() == first_bytes


def test_stratified_branching_resolves_sparse_hopping_degree() -> None:
    norb = 20
    h1 = np.zeros((norb, norb))
    for orbital in range(norb - 1):
        h1[orbital, orbital + 1] = h1[orbital + 1, orbital] = 1.0
    data = _data(h1, {}, nelec=20, ms2=0)
    result = random_determinant_branching_profile(
        data, 1.0, determinants=32, excitation_samples_per_class=128
    )
    mean = result["random_det_expected_degree_rel_1e_8"]
    standard_error = result["random_det_expected_degree_mc_se_rel_1e_8"]
    assert mean == pytest.approx(20.0, abs=3.0)
    assert standard_error / mean < 0.15


def test_feature_block_is_deterministic_and_bounded() -> None:
    path = ROOT / "tests/qb_gsee_benchmark/fcidump.h2_sto-3g"
    first = compute_determinant_coupling_features(
        path, random_determinants=4, excitation_samples_per_class=64
    )
    second = compute_determinant_coupling_features(
        path, random_determinants=4, excitation_samples_per_class=64
    )
    assert first == second
    assert (
        first["determinant_coupling_features_version"] == DETERMINANT_COUPLING_VERSION
    )
    assert first["det_coupling_nonzero_degree"] > 0
    assert first["det_coupling_top_1_l2_mass_fraction"] <= 1.0
    assert first["random_det_expected_degree_mc_se_rel_1e_8"] >= 0.0
