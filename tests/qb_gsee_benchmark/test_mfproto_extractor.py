import json
import shutil
from pathlib import Path

from qb_gsee_benchmark.features.corpus_runner import CorpusFcidump, file_checksum
from qb_gsee_benchmark.features.mfproto_extractor import compute_mfproto_features
from qb_gsee_benchmark.features.mfproto_runner import run_mfproto_task

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "g40_permutation_pairs"
    / "molecular_h2_original.FCIDUMP"
)


def test_complete_extractor_populates_independent_panels() -> None:
    extraction = compute_mfproto_features(FIXTURE)
    features = extraction.features
    assert features["mf_selected_applicable"] is True
    assert features["mf_stability_applicable"] is True
    assert features["mf_hf_variance_applicable"] is True
    assert features["mp2_applicable"] is True
    assert features["mp2_natural_occupation_applicable"] is True
    assert features["mfproto_scf_seconds"] >= 0.0
    assert features["mfproto_stability_seconds"] >= 0.0
    assert features["mfproto_hf_variance_seconds"] >= 0.0
    assert features["mfproto_mp2_seconds"] >= 0.0
    assert extraction.audit["panel_errors"] == {}
    assert len(extraction.audit["branch_outcomes"]) == 8


def test_runner_binds_checksum_protocol_code_and_resumes(tmp_path) -> None:
    cache = tmp_path / "cache"
    states = tmp_path / "states"
    cache.mkdir()
    object_uuid = "fixture-object"
    cached = cache / f"{object_uuid}.FCIDUMP"
    shutil.copyfile(FIXTURE, cached)
    record = CorpusFcidump(
        problem_instance_short_name="fixture",
        task_uuid="fixture-task",
        instance_data_object_uuid=object_uuid,
        url="https://invalid.example/fixture.FCIDUMP",
        checksum=file_checksum(FIXTURE, "sha256"),
        checksum_type="sha256",
        file_name="fixture.FCIDUMP",
        norb_metadata=2,
        ms2_metadata=0,
    )
    first = run_mfproto_task(
        record, cache, states, code_revision="revision-a", offline=True
    )
    assert first["status"] == "success"
    assert first["source_sha256"] == file_checksum(FIXTURE, "sha256")
    assert first["code_revision"] == "revision-a"
    assert first["features"]["mp2_applicable"] is True
    state_path = states / "fixture-task.mfproto.json"
    original_bytes = state_path.read_bytes()

    resumed = run_mfproto_task(
        record, cache, states, code_revision="revision-a", offline=True
    )
    assert resumed == first
    assert state_path.read_bytes() == original_bytes

    replaced = run_mfproto_task(
        record, cache, states, code_revision="revision-b", offline=True
    )
    assert replaced["status"] == "success"
    assert replaced["code_revision"] == "revision-b"
    assert json.loads(state_path.read_text()) == replaced
