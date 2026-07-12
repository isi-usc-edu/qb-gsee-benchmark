import hashlib
from pathlib import Path

from qb_gsee_benchmark.features.corpus_runner import CorpusFcidump, cache_path
from qb_gsee_benchmark.features.orderability_runner import run_orderability_task

ROOT = Path(__file__).resolve().parents[2]


def test_orderability_runner_is_checksum_and_configuration_resumable(
    tmp_path: Path,
) -> None:
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
    first = run_orderability_task(record, tmp_path / "cache", state_dir, offline=True)
    state_path = state_dir / "task.orderability.json"
    first_bytes = state_path.read_bytes()
    second = run_orderability_task(record, tmp_path / "cache", state_dir, offline=True)
    assert first["status"] == "success"
    assert second == first
    assert state_path.read_bytes() == first_bytes
