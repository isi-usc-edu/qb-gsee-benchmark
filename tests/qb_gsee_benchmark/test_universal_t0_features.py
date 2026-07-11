import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from qb_gsee_benchmark.features.corpus_runner import (
    CorpusFcidump,
    cache_path,
    load_corpus_fcidumps,
    run_linear_task,
    write_corpus_manifest_jsonl,
)
from qb_gsee_benchmark.features.fcidump_sparse import read_sparse_fcidump
from qb_gsee_benchmark.features.integral_features import effective_one_body
from qb_gsee_benchmark.features.universal_t0_features import (
    compute_universal_t0_linear_features,
    effective_one_body_from_sparse,
)


FCIDUMP_TEXT = """&FCI NORB=2, NELEC=2, MS2=0,
 ORBSYM=1,1,
 ISYM=1,
/
 2.0 1 1 1 1
 4.0 2 2 2 2
 1.0 1 1 2 2
 0.25 1 2 1 2
 0.25 2 1 2 1
 1.0 1 1 0 0
 3.0 2 2 0 0
 0.5 1 2 0 0
 0.5 2 1 0 0
 7.0 0 0 0 0
"""


def _write_fcidump(path: Path, text: str = FCIDUMP_TEXT) -> Path:
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="ascii") as handle:
            handle.write(text)
    else:
        path.write_text(text, encoding="ascii")
    return path


@pytest.mark.parametrize("suffix", ["", ".gz"])
def test_sparse_reader_handles_compressed_and_duplicate_orientations(
    tmp_path: Path, suffix: str
) -> None:
    data = read_sparse_fcidump(
        _write_fcidump(tmp_path / f"FCIDUMP{suffix}")
    )

    assert (data.norb, data.nelec, data.ms2) == (2, 2, 0)
    assert (data.nalpha, data.nbeta) == (1, 1)
    assert data.ecore == pytest.approx(7.0)
    assert data.two_body_input_records == 5
    assert data.two_body_duplicate_orientations == 1
    assert len(data.eri_records) == 4
    assert np.allclose(data.h1, [[1.0, 0.5], [0.5, 3.0]])
    assert data.eri_value(1, 0, 0, 1) == pytest.approx(0.25)


def test_sparse_effective_one_body_matches_dense_definition(
    tmp_path: Path,
) -> None:
    data = read_sparse_fcidump(_write_fcidump(tmp_path / "FCIDUMP"))
    sparse_result = effective_one_body_from_sparse(data)
    dense_result = effective_one_body(data.h1, data.dense_eri())

    assert np.allclose(sparse_result, dense_result)
    assert np.allclose(sparse_result, [[-0.125, 0.5], [0.5, 0.875]])


def test_universal_linear_features_have_declared_full_tensor_denominators(
    tmp_path: Path,
) -> None:
    features = compute_universal_t0_linear_features(
        _write_fcidump(tmp_path / "FCIDUMP")
    )

    assert features["log_fci_dim"] == pytest.approx(math.log10(4))
    assert features["effective_h1_entrywise_l1_norm"] == pytest.approx(2.0)
    assert features["eri_full_l1_norm"] == pytest.approx(9.0)
    assert features["eri_full_l2_norm"] == pytest.approx(math.sqrt(22.25))
    assert features["fermionic_coefficient_l1_norm"] == pytest.approx(6.5)
    assert features["rho_offdiag"] == pytest.approx(0.5)
    assert features["bare_one_body_bandwidth"] == pytest.approx(math.sqrt(5))
    assert features["bare_one_body_gap_alpha"] == pytest.approx(math.sqrt(5))
    assert features["bare_one_body_gap_beta"] == pytest.approx(math.sqrt(5))
    assert features["U_eff_over_W"] == pytest.approx(3.0 / math.sqrt(5))
    assert features["effective_h1_fraction_above_rel_1e_12"] == 1.0
    assert features["eri_fraction_above_rel_1e_12"] == 0.5


def test_sparse_reader_rejects_conflicting_symmetry_duplicates(
    tmp_path: Path,
) -> None:
    conflicting = FCIDUMP_TEXT.replace(
        " 0.25 2 1 2 1", " 0.30 2 1 2 1"
    )
    path = _write_fcidump(tmp_path / "FCIDUMP", conflicting)

    with pytest.raises(ValueError, match="Conflicting two-body"):
        read_sparse_fcidump(path)


def test_sparse_reader_rejects_iuhf(tmp_path: Path) -> None:
    text = FCIDUMP_TEXT.replace("MS2=0,", "MS2=0, IUHF=1,")
    path = _write_fcidump(tmp_path / "FCIDUMP", text)

    with pytest.raises(ValueError, match="IUHF"):
        read_sparse_fcidump(path)


def test_manifest_is_driven_by_every_current_corpus_task() -> None:
    root = Path(__file__).resolve().parents[2]
    records = load_corpus_fcidumps(root / "problem_instances")

    assert records
    assert len(records) == len({record.task_uuid for record in records})
    assert all(record.url.startswith("https://") for record in records)
    assert all(record.checksum for record in records)



def test_manifest_writer_creates_parent_directory(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    records = load_corpus_fcidumps(root / "problem_instances")[:2]
    destination = tmp_path / "new" / "manifest.jsonl"

    write_corpus_manifest_jsonl(records, destination)

    assert len(destination.read_text().splitlines()) == 2

def test_linear_task_is_checksum_bound_and_resumable(tmp_path: Path) -> None:
    payload = FCIDUMP_TEXT.encode("ascii")
    record = CorpusFcidump(
        problem_instance_short_name="fixture",
        task_uuid="00000000-0000-0000-0000-000000000001",
        instance_data_object_uuid="00000000-0000-0000-0000-000000000002",
        url="https://example.invalid/fixture.fcidump",
        checksum=hashlib.sha1(payload).hexdigest(),
        checksum_type="sha1sum",
        file_name="fixture.fcidump",
        norb_metadata=2,
    )
    cache = tmp_path / "cache"
    state = tmp_path / "state"
    source = cache_path(cache, record)
    source.parent.mkdir()
    source.write_bytes(payload)

    first = run_linear_task(record, cache, state, offline=True)
    state_bytes = next(state.glob("*.json")).read_bytes()
    second = run_linear_task(record, cache, state, offline=True)

    assert first["status"] == "success"
    assert second == first
    assert next(state.glob("*.json")).read_bytes() == state_bytes
    assert first["features"]["n_orbs"] == 2
    assert json.loads(state_bytes)["source_sha256"] == hashlib.sha256(
        payload
    ).hexdigest()
