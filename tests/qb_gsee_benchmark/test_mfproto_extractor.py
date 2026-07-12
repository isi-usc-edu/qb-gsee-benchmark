import json
import shutil
import subprocess
import sys
from pathlib import Path
from qb_gsee_benchmark.features.feature_schema import metadata_for_column

ROOT = Path(__file__).resolve().parents[2]
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
    assert features["mfproto_pair_graph_seconds"] >= 0.0
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


def test_every_p2_output_has_fail_closed_metadata() -> None:
    features = compute_mfproto_features(FIXTURE).features
    metadata = {column: metadata_for_column(column) for column in features}
    assert all(
        item.representation == "BAS+ORD"
        for item in metadata.values()
        if item.model_eligible
    )
    assert all(
        item.protocol == "MF-PROTO" for item in metadata.values() if item.model_eligible
    )
    assert metadata["mf_selected_s2"].model_eligible
    assert metadata["mf_symmetry_breaking_energy_per_electron"].model_eligible
    assert metadata["mf_hf_variance_per_electron_hartree_squared"].model_eligible
    assert metadata["mp2_correlation_energy_per_electron_hartree"].model_eligible
    assert metadata["mp2_pair_cut_fiedler_max_normalized"].model_eligible
    for column in (
        "mf_selected_method",
        "mf_selected_energy_hartree",
        "mf_tie_g1_alpha_boundary_tie",
        "mfproto_scf_seconds",
        "mp2_denominator_masked_count",
        "mp2_natural_occupation_minimum_raw",
        "mp2_pair_cut_fiedler_max",
    ):
        assert not metadata[column].model_eligible


def test_p2_feature_contract_rebuild_is_byte_exact(tmp_path) -> None:
    rebuilt = tmp_path / "contract.json"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_g40_p2_feature_contract.py"),
            "--output",
            str(rebuilt),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    committed = ROOT / "analysis" / "feature_schema" / "g40_p2_feature_contract.json"
    assert rebuilt.read_bytes() == committed.read_bytes()
    payload = json.loads(committed.read_text())
    assert payload["output_column_count"] == len(payload["metadata"])
    assert payload["model_eligible_columns"]
