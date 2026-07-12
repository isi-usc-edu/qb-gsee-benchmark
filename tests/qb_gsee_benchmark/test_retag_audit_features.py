import hashlib
from pathlib import Path

from qb_gsee_benchmark.features.corpus_runner import CorpusFcidump, cache_path
from qb_gsee_benchmark.features.retag_audit_features import (
    RETAG_AUDIT_VERSION,
    compute_retag_audit_features,
)
from qb_gsee_benchmark.features.retag_audit_runner import run_retag_audit_task

ROOT = Path(__file__).resolve().parents[2]


def test_retag_audit_flags_cover_tie_and_mpo_applicability() -> None:
    root = ROOT / "tests/qb_gsee_benchmark/fixtures/g40_permutation_pairs"
    molecular = compute_retag_audit_features(root / "molecular_h2_original.FCIDUMP")
    lattice = compute_retag_audit_features(root / "lattice_hubbard_original.FCIDUMP")
    assert molecular == {
        "det_coupling_reference_boundary_tie": False,
        "mpo_pair_rank_applicable": True,
        "retag_audit_features_version": RETAG_AUDIT_VERSION,
    }
    assert lattice == {
        "det_coupling_reference_boundary_tie": True,
        "mpo_pair_rank_applicable": False,
        "retag_audit_features_version": RETAG_AUDIT_VERSION,
    }


def test_retag_audit_runner_is_checksum_resumable(tmp_path: Path) -> None:
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
    first = run_retag_audit_task(record, tmp_path / "cache", tmp_path / "state", offline=True)
    state = tmp_path / "state/task.retag-audit.json"
    first_bytes = state.read_bytes()
    second = run_retag_audit_task(record, tmp_path / "cache", tmp_path / "state", offline=True)
    assert first["status"] == "success"
    assert second == first
    assert state.read_bytes() == first_bytes
