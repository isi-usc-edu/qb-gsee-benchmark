import hashlib
import math
from pathlib import Path

import numpy as np
import pytest

from qb_gsee_benchmark.features.corpus_runner import CorpusFcidump, cache_path
from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump
from qb_gsee_benchmark.features.interaction_spectrum_features import (
    compute_interaction_spectrum_features,
    exact_symmetric_pair_eigenvalues,
    symmetric_pair_matrix,
)
from qb_gsee_benchmark.features.interaction_spectrum_runner import (
    run_interaction_spectrum_task,
)

ROOT = Path(__file__).resolve().parents[2]


def _data(norb: int, eri: dict[tuple[int, int, int, int], float]) -> SparseFcidump:
    return SparseFcidump(
        norb=norb,
        nelec=2,
        ms2=0,
        h1=np.zeros((norb, norb)),
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


def _from_dense(eri: np.ndarray) -> SparseFcidump:
    norb = len(eri)
    records = {}
    pairs = [(p, q) for p in range(norb) for q in range(p + 1)]
    for left_index, (p, q) in enumerate(pairs):
        for r, s in pairs[: left_index + 1]:
            value = float(eri[p, q, r, s])
            if value:
                records[(p, q, r, s)] = value
    return _data(norb, records)


def test_symmetric_pair_matrix_uses_sqrt2_offdiagonal_weight() -> None:
    data = _data(2, {(0, 1, 0, 1): 0.5})
    matrix, full_dimension = symmetric_pair_matrix(data)
    assert full_dimension == 3
    assert np.allclose(matrix, [[1.0]])


def test_interaction_spectrum_statistics_include_negative_mass() -> None:
    data = _data(2, {(0, 0, 0, 0): 3.0, (1, 1, 1, 1): -1.0})
    features = compute_interaction_spectrum_features(data)
    assert features["interaction_spectrum_rank_rel_1e_2"] == 2
    assert features["interaction_spectrum_rank_rel_1e_4"] == 2
    assert features["interaction_spectrum_rank_rel_1e_6"] == 2
    assert features["interaction_spectrum_effective_rank"] == pytest.approx(
        math.exp(-(0.75 * math.log(0.75) + 0.25 * math.log(0.25)))
    )
    assert features["interaction_spectrum_participation_rank"] == pytest.approx(1.6)
    assert features["interaction_spectrum_relative_gap"] == pytest.approx(2.0 / 3.0)
    assert features["interaction_spectrum_negative_mass_fraction"] == pytest.approx(0.25)
    assert features["interaction_spectrum_pair_dimension"] == 3
    assert features["interaction_spectrum_active_pair_dimension"] == 2


def test_support_reduction_preserves_full_nonzero_spectrum() -> None:
    data = _data(
        3,
        {
            (0, 0, 0, 0): 2.0,
            (0, 0, 1, 1): 0.25,
            (1, 1, 1, 1): 1.0,
        },
    )
    eigenvalues, full_dimension, active_dimension = exact_symmetric_pair_eigenvalues(data)
    assert full_dimension == 6
    assert active_dimension == 2
    expected = np.linalg.eigvalsh(np.array([[2.0, 0.25], [0.25, 1.0]]))
    assert eigenvalues == pytest.approx(expected)


def test_symmetric_pair_spectrum_is_orbital_rotation_invariant() -> None:
    rng = np.random.default_rng(31)
    norb = 3
    pairs = [(p, q) for p in range(norb) for q in range(p + 1)]
    pair_matrix = rng.normal(size=(len(pairs), len(pairs)))
    pair_matrix = 0.5 * (pair_matrix + pair_matrix.T)
    eri = np.zeros((norb,) * 4)
    for left_index, (p, q) in enumerate(pairs):
        left_weight = math.sqrt(2.0) if p != q else 1.0
        for right_index, (r, s) in enumerate(pairs):
            right_weight = math.sqrt(2.0) if r != s else 1.0
            value = pair_matrix[left_index, right_index] / (
                left_weight * right_weight
            )
            for indices in {
                (p, q, r, s), (q, p, r, s), (p, q, s, r), (q, p, s, r),
                (r, s, p, q), (s, r, p, q), (r, s, q, p), (s, r, q, p),
            }:
                eri[indices] = value
    rotation, _ = np.linalg.qr(rng.normal(size=(norb, norb)))
    rotated = np.einsum(
        "pa,qb,rc,sd,pqrs->abcd",
        rotation, rotation, rotation, rotation, eri, optimize=True,
    )
    original_values = exact_symmetric_pair_eigenvalues(_from_dense(eri))[0]
    rotated_values = exact_symmetric_pair_eigenvalues(_from_dense(rotated))[0]
    assert rotated_values == pytest.approx(
        original_values, rel=1.0e-11, abs=1.0e-11
    )


def test_interaction_spectrum_runner_is_checksum_resumable(tmp_path: Path) -> None:
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
    first = run_interaction_spectrum_task(
        record, tmp_path / "cache", tmp_path / "state", offline=True
    )
    state = tmp_path / "state/task.interaction-spectrum.json"
    first_bytes = state.read_bytes()
    second = run_interaction_spectrum_task(
        record, tmp_path / "cache", tmp_path / "state", offline=True
    )
    assert first["status"] == "success"
    assert second == first
    assert state.read_bytes() == first_bytes
