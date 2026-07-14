import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from qb_gsee_benchmark.features.feature_schema import metadata_for_column

ROOT = Path(__file__).resolve().parents[2]
from qb_gsee_benchmark.features.corpus_runner import CorpusFcidump, file_checksum
import qb_gsee_benchmark.features.mfproto_extractor as extractor_module
from qb_gsee_benchmark.features.mfproto_extractor import compute_mfproto_features
from qb_gsee_benchmark.features.mfproto_features import (
    CanonicalSpectrum,
    MeanFieldBranch,
    MeanFieldResult,
    ParticleSector,
)
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
    selected = extraction.audit["branch_outcomes"][
        extraction.audit["selected_branch_index"]
    ]
    for spin in ("alpha", "beta"):
        branch_audit = selected[f"fock_canonical_audit_{spin}"]
        for key, value in branch_audit.items():
            assert features[f"mf_tie_selected_fock_{spin}_{key}"] == value


def test_science_panels_use_selected_state_when_stability_follows(monkeypatch) -> None:
    def branch(energy: float) -> MeanFieldBranch:
        return MeanFieldBranch(
            method="RHF",
            guess="G1",
            converged=True,
            fallback_used=False,
            engine_converged=True,
            energy=energy,
            final_delta_energy=0.0,
            maximum_ov_gradient=0.0,
            density_alpha=np.diag([1.0, 0.0]),
            density_beta=np.diag([1.0, 0.0]),
            fock_alpha=np.diag([-1.0, 1.0]),
            fock_beta=np.diag([-1.0, 1.0]),
            orbitals_alpha=np.eye(2),
            orbitals_beta=np.eye(2),
            energies_alpha=np.array([-1.0, 1.0]),
            energies_beta=np.array([-1.0, 1.0]),
            fock_canonical_audit_alpha={},
            fock_canonical_audit_beta={},
            s2=0.0,
            cycles=1,
        )

    selected = branch(-2.0)
    followed = branch(-2.1)
    mean_field = MeanFieldResult(
        sector=ParticleSector(2, 2, 0, 1, 1),
        branches=[selected],
        components=[[0]],
        selected_branch_index=0,
        core_spectrum=CanonicalSpectrum(np.array([-1.0, 1.0]), np.eye(2), 2.0, 0, 0, 0),
        tie_audit={},
    )
    consumed = {}
    monkeypatch.setattr(
        extractor_module,
        "read_sparse_fcidump",
        lambda *_args, **_kwargs: SimpleNamespace(dense_eri=lambda: np.zeros((2,) * 4)),
    )
    monkeypatch.setattr(extractor_module, "run_mean_field", lambda *_args: mean_field)
    monkeypatch.setattr(
        extractor_module, "mean_field_feature_values", lambda _result: {}
    )
    monkeypatch.setattr(
        extractor_module,
        "run_stability",
        lambda *_args: SimpleNamespace(final_branch=followed, follow_outcomes=[]),
    )
    monkeypatch.setattr(
        extractor_module, "stability_feature_values", lambda _result: {}
    )

    def variance(_eri, state, _sector):
        consumed["variance"] = state
        return object()

    def mp2(_data, _eri, state, _sector):
        consumed["mp2"] = state
        return SimpleNamespace(features={"mfproto_pair_graph_seconds": 0.0})

    monkeypatch.setattr(extractor_module, "exact_hf_variance", variance)
    monkeypatch.setattr(
        extractor_module, "hf_variance_feature_values", lambda _result: {}
    )
    monkeypatch.setattr(extractor_module, "run_mp2", mp2)

    extraction = compute_mfproto_features(FIXTURE)
    assert consumed == {"variance": selected, "mp2": selected}
    assert extraction.audit["science_panel_branch_index"] == 0
    assert extraction.audit["science_panel_state"] == "protocol_selected_solution"
    assert extraction.audit["stability_follow_is_diagnostic_only"] is True
    assert extraction.audit["stability_final_branch"]["energy_hartree"] == -2.1
    certificate = extraction.audit["selected_state_certificate"]
    assert certificate["selected_energy_hartree"] == -2.0
    assert certificate["certificate_version"] == (
        "g40_mfproto_selected_stationary_point_v1"
    )


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
    assert not metadata["mf_stability_external_eigenvalue_hartree"].model_eligible
    assert metadata["mp2_pair_cut_fiedler_max_normalized"].model_eligible
    for column in (
        "mf_selected_method",
        "mf_selected_energy_hartree",
        "mf_tie_g1_alpha_boundary_tie",
        "mp2_amplitude_shape_boundary_ambiguous",
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
