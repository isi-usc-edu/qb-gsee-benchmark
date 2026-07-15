import json
from pathlib import Path

import pytest

from qb_gsee_benchmark.solvers import batch
from qb_gsee_benchmark.solvers import cli
from qb_gsee_benchmark.solvers import pyscf_adapter
from qb_gsee_benchmark.solvers.base import RunManifest
from qb_gsee_benchmark.solvers.base import load_manifest
from qb_gsee_benchmark.solvers.base import write_manifest

REPO_ROOT = Path(__file__).parents[2]
H2_PROBLEM_INSTANCE = (
    REPO_ROOT
    / "problem_instances"
    / "validation_instances"
    / "problem_instance.validation.H2.cc-PVDZ.9162371c-b23f-45a6-bacd-44cb7aaea917.json"
)
H2_FCIDUMP = (
    REPO_ROOT
    / "scripts"
    / "development"
    / "validation.H2.cc-PVDZ.bbcd09f2-8a89-4f35-9577-7851a76ea17c.fcidump.gz"
)
H2_TASK_UUID = "f847059f-a89f-4008-9ae1-39847c899e75"
H_PROBLEM_INSTANCE = (
    REPO_ROOT
    / "problem_instances"
    / "validation_instances"
    / "problem_instance.validation.H.cc-PVDZ.3aa01b76-53e2-49e8-bc05-72875168a00a.json"
)
H_FCIDUMP = (
    REPO_ROOT
    / "scripts"
    / "development"
    / "validation.H.cc-PVDZ.0b245a9c-7561-423d-bd50-8958b3625a94.fcidump.gz"
)
H_TASK_UUID = "4e1617a3-7a5f-4c86-99b6-4cfc8b547197"

METHOD_CASES = [
    ("pyscf_hf", "HF", "5f5e617a-19c2-4d82-bebc-b2d6b3dcb012", -1.1287110109153249),
    ("pyscf_mp2", "MP2", "b420358b-5def-41e6-8c5d-b9d93b6aecd2", -1.155091625687221),
    ("pyscf_cisd", "CISD", "418f060e-496b-4024-8d2d-9b1f8791e76d", -1.1634029610635777),
    ("pyscf_ccsd", "CCSD", "0a29e54f-bef9-4d19-bafa-d94b1c4b37aa", -1.1634029671742296),
    (
        "pyscf_ccsd_t",
        "CCSD(T)",
        "c09217e6-d0f7-4b0f-81c4-79210b7ac878",
        -1.1634029671742296,
    ),
]


@pytest.mark.parametrize(
    "adapter_name,method,solver_uuid,expected_energy", METHOD_CASES
)
def test_method_adapters_match_legacy_h2_records(
    tmp_path,
    adapter_name,
    method,
    solver_uuid,
    expected_energy,
):
    run_dir = tmp_path / adapter_name
    manifest = pyscf_adapter.prepare_method(
        method=method,
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        campaign=pyscf_adapter.G48_METHOD_CAMPAIGN,
        overwrite=True,
    )

    raw_output = pyscf_adapter.run(run_dir)
    solution = pyscf_adapter.harvest(run_dir)
    data = solution["solution_data"][0]

    assert manifest.adapter == adapter_name
    assert manifest.adapter_version == "0.4.2"
    assert manifest.solver_uuid == solver_uuid
    assert manifest.solver_short_name == method
    assert manifest.config["method"] == method
    assert manifest.config["campaign"] == pyscf_adapter.G48_METHOD_CAMPAIGN
    assert manifest.resources.walltime_seconds == 1800
    assert raw_output["status"] == "completed"
    assert data["energy"] == pytest.approx(expected_energy, abs=1.0e-10)
    assert data["solution_details"]["harness_status"] == "completed"
    assert data["solution_details"]["attempted"] is True
    assert data["solution_details"]["campaign"] == pyscf_adapter.G48_METHOD_CAMPAIGN


def test_method_adapter_fails_closed_on_non_finite_energy(tmp_path, monkeypatch):
    run_dir = tmp_path / "non-finite-mp2"
    pyscf_adapter.prepare_method(
        method="MP2",
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        campaign=pyscf_adapter.G48_METHOD_CAMPAIGN,
        overwrite=True,
    )
    monkeypatch.setattr(
        pyscf_adapter,
        "_compute_energy",
        lambda **_kwargs: (
            float("nan"),
            {"hf_converged": True, "converged": None},
        ),
    )

    with pytest.raises(RuntimeError, match="non-finite scored energy"):
        pyscf_adapter.run(run_dir)

    raw_output = json.loads((run_dir / "raw_output.json").read_text())
    solution = pyscf_adapter.harvest(run_dir)
    data = solution["solution_data"][0]
    assert raw_output["status"] == "failed"
    assert raw_output["energy"] is None
    assert raw_output["details"]["failure_stage"] == "MP2"
    assert (
        raw_output["details"]["failure_classification"]
        == "non_finite_scored_energy"
    )
    assert data["energy"] is None
    assert data["solution_details"]["harness_status"] == "failed"
    assert data["solution_details"]["attempted"] is True


def test_method_adapter_uses_legacy_uhf_open_shell_convention(tmp_path):
    run_dir = tmp_path / "hf-hydrogen"
    pyscf_adapter.prepare_method(
        method="HF",
        problem_instance_path=H_PROBLEM_INSTANCE,
        task_uuid=H_TASK_UUID,
        fcidump_path=H_FCIDUMP,
        run_dir=run_dir,
        campaign=pyscf_adapter.G48_METHOD_CAMPAIGN,
        overwrite=True,
    )

    raw_output = pyscf_adapter.run(run_dir)

    assert raw_output["energy"] == pytest.approx(-0.4992784034195832, abs=1.0e-12)
    assert raw_output["details"]["hf_reference"] == "UHF"


def test_method_adapter_rejects_mutated_identity(tmp_path):
    run_dir = tmp_path / "mutated"
    pyscf_adapter.prepare_method(
        method="MP2",
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        campaign=pyscf_adapter.G48_METHOD_CAMPAIGN,
        overwrite=True,
    )
    manifest_data = load_manifest(run_dir).to_dict()
    manifest_data["config"]["method"] = "HF"
    write_manifest(run_dir, RunManifest.from_dict(manifest_data))

    with pytest.raises(ValueError, match="identity mismatch"):
        pyscf_adapter.run(run_dir)


def test_method_adapter_timeout_uses_four_state_vocabulary(tmp_path):
    run_dir = tmp_path / "timeout"
    pyscf_adapter.prepare_method(
        method="CCSD",
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        campaign=pyscf_adapter.G48_METHOD_CAMPAIGN,
        overwrite=True,
    )

    solution = pyscf_adapter.harvest(
        run_dir,
        not_attempted_reason="adapter-default wall cap reached",
        missing_output_status="timeout",
        missing_output_elapsed_seconds=1800.25,
    )
    data = solution["solution_data"][0]

    assert data["energy"] is None
    assert data["solution_details"]["harness_status"] == "timeout"
    assert data["solution_details"]["attempted"] is True
    assert data["solution_details"]["campaign"] == pyscf_adapter.G48_METHOD_CAMPAIGN
    assert data["run_time"]["overall_time"]["seconds"] == 1800.25


def test_batch_method_aliases_freeze_method_and_campaign(tmp_path):
    plan = tmp_path / "plan.csv"
    output_root = tmp_path / "runs"
    rows = [
        (
            f"{adapter},{adapter},{H2_PROBLEM_INSTANCE},{H2_TASK_UUID},"
            f"{H2_FCIDUMP},FCI,2,{pyscf_adapter.G48_METHOD_CAMPAIGN}"
        )
        for adapter, _method, _uuid, _energy in METHOD_CASES
    ]
    plan.write_text(
        "adapter,run_name,problem_instance,task_uuid,fcidump,method,num_threads,campaign\n"
        + "\n".join(rows)
        + "\n"
    )

    summary = batch.prepare_batch(plan, output_root, overwrite=True)

    assert summary["prepared_count"] == 5
    for adapter_name, method, _uuid, _energy in METHOD_CASES:
        manifest = load_manifest(output_root / adapter_name)
        assert manifest.adapter == adapter_name
        assert manifest.config["method"] == method
        assert manifest.config["campaign"] == pyscf_adapter.G48_METHOD_CAMPAIGN
        assert manifest.config["num_threads"] == 2


def test_pyscf_hf_demonstration_record_on_validation_instance(tmp_path, capsys):
    run_dir = tmp_path / "demonstration"
    common = [
        "--problem-instance",
        str(H2_PROBLEM_INSTANCE),
        "--task-uuid",
        H2_TASK_UUID,
        "--fcidump",
        str(H2_FCIDUMP),
        "--run-dir",
        str(run_dir),
    ]
    assert (
        cli.main(
            [
                "prepare-pyscf-method",
                *common,
                "--method",
                "HF",
                "--campaign",
                pyscf_adapter.G48_METHOD_CAMPAIGN,
            ]
        )
        == 0
    )
    assert cli.main(["run", "--run-dir", str(run_dir)]) == 0
    assert cli.main(["harvest", "--run-dir", str(run_dir)]) == 0
    capsys.readouterr()

    record = json.loads((run_dir / "solution.json").read_text())
    data = record["solution_data"][0]
    assert record["problem_instance_uuid"] == "9162371c-b23f-45a6-bacd-44cb7aaea917"
    assert data["task_uuid"] == H2_TASK_UUID
    assert data["energy"] == pytest.approx(-1.1287110109153249, abs=1.0e-10)
    assert record["solver_details"]["solver_short_name"] == "HF"
    assert (
        record["solver_details"]["algorithm_details"]["harness_adapter"] == "pyscf_hf"
    )
    assert data["solution_details"]["campaign"] == pyscf_adapter.G48_METHOD_CAMPAIGN


def test_method_adapter_rejects_unknown_campaign_before_preparation(tmp_path):
    run_dir = tmp_path / "unknown-campaign"

    with pytest.raises(ValueError, match="Unsupported PySCF method campaign"):
        pyscf_adapter.prepare_method(
            method="HF",
            problem_instance_path=H2_PROBLEM_INSTANCE,
            task_uuid=H2_TASK_UUID,
            fcidump_path=H2_FCIDUMP,
            run_dir=run_dir,
            campaign="g48-unreviewed-campaign",
            overwrite=True,
        )

    assert not run_dir.exists()


def test_method_adapter_rejects_legacy_campaign_before_preparation(tmp_path):
    run_dir = tmp_path / "legacy-campaign"

    with pytest.raises(
        ValueError,
        match="expected reviewed G-48 campaign",
    ):
        pyscf_adapter.prepare_method(
            method="HF",
            problem_instance_path=H2_PROBLEM_INSTANCE,
            task_uuid=H2_TASK_UUID,
            fcidump_path=H2_FCIDUMP,
            run_dir=run_dir,
            campaign=pyscf_adapter.LEGACY_METHOD_CAMPAIGN,
            overwrite=True,
        )

    assert not run_dir.exists()


def test_method_adapter_rejects_mutated_campaign_identity(tmp_path):
    run_dir = tmp_path / "mutated-campaign"
    pyscf_adapter.prepare_method(
        method="HF",
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        campaign=pyscf_adapter.G48_METHOD_CAMPAIGN,
        overwrite=True,
    )
    manifest_data = load_manifest(run_dir).to_dict()
    manifest_data["config"]["campaign"] = "g48-unreviewed-campaign"
    write_manifest(run_dir, RunManifest.from_dict(manifest_data))

    with pytest.raises(ValueError, match="Unsupported PySCF method campaign"):
        pyscf_adapter.run(run_dir)


@pytest.mark.parametrize(
    "method,details,expected_stages",
    [
        (
            "HF",
            {
                "hf_energy": -1.0,
                "hf_converged": False,
                "hf_reference": "RHF",
            },
            ["HF"],
        ),
        (
            "MP2",
            {
                "hf_energy": -1.0,
                "hf_converged": True,
                "hf_reference": "RHF",
                "converged": False,
            },
            ["MP2"],
        ),
        (
            "CCSD",
            {
                "hf_energy": -1.0,
                "hf_converged": True,
                "hf_reference": "RHF",
                "converged": False,
            },
            ["CCSD"],
        ),
        (
            "CCSD(T)",
            {
                "hf_energy": -1.0,
                "hf_converged": False,
                "hf_reference": "UHF",
                "converged": False,
            },
            ["HF", "CCSD(T)"],
        ),
    ],
)
def test_nonconvergence_is_attempted_failure_with_diagnostic_only_energy(
    tmp_path, monkeypatch, method, details, expected_stages
):
    run_dir = tmp_path / method.replace("(", "_").replace(")", "")
    pyscf_adapter.prepare_method(
        method=method,
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        campaign=pyscf_adapter.G48_METHOD_CAMPAIGN,
        overwrite=True,
    )
    monkeypatch.setattr(
        pyscf_adapter,
        "_compute_energy",
        lambda **_kwargs: (-1.2345, dict(details)),
    )

    with pytest.raises(RuntimeError, match="did not converge at default settings"):
        pyscf_adapter.run(run_dir)

    raw = json.loads((run_dir / "raw_output.json").read_text())
    assert raw["status"] == "failed"
    assert raw["energy"] is None
    assert raw["details"]["diagnostic_energy_hartree"] == -1.2345
    assert raw["details"]["nonconverged_stages"] == expected_stages

    solution = pyscf_adapter.harvest(run_dir)
    data = solution["solution_data"][0]
    assert data["energy"] is None
    assert data["solution_details"]["harness_status"] == "failed"
    assert data["solution_details"]["attempted"] is True
    assert data["solution_details"]["campaign"] == pyscf_adapter.G48_METHOD_CAMPAIGN
    assert (
        data["solution_details"]["pyscf_details"]["diagnostic_energy_hartree"]
        == -1.2345
    )


def test_ccsd_kernel_exception_preserves_hf_provenance(monkeypatch):
    class FailingCCSD:
        converged = None

        def kernel(self):
            raise RuntimeError("Singular matrix")

    details = {
        "hf_energy": -1.0,
        "hf_converged": True,
        "hf_reference": "UHF",
    }
    monkeypatch.setattr(
        pyscf_adapter,
        "_run_hf",
        lambda *_args, **_kwargs: (object(), dict(details)),
    )
    monkeypatch.setattr(pyscf_adapter.cc, "CCSD", lambda _mf: FailingCCSD())

    with pytest.raises(pyscf_adapter._PySCFStageError) as captured:
        pyscf_adapter._compute_energy(
            method="CCSD(T)",
            fcidump_path=H2_FCIDUMP,
            legacy_open_shell_uhf=True,
        )

    failure = captured.value.details
    assert str(captured.value) == "Singular matrix"
    assert failure["failure_stage"] == "CCSD"
    assert failure["convergence_metadata_status"] == "partial"
    assert failure["hf_converged"] is True
    assert failure["converged"] is None


def test_unexpected_exception_records_explicit_unknown_convergence(
    tmp_path, monkeypatch
):
    run_dir = tmp_path / "unexpected"
    pyscf_adapter.prepare_method(
        method="CCSD(T)",
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        campaign=pyscf_adapter.G48_METHOD_CAMPAIGN,
        overwrite=True,
    )

    def fail(**_kwargs):
        raise RuntimeError("unexpected solver failure")

    monkeypatch.setattr(pyscf_adapter, "_compute_energy", fail)
    with pytest.raises(RuntimeError, match="unexpected solver failure"):
        pyscf_adapter.run(run_dir)

    raw = json.loads((run_dir / "raw_output.json").read_text())
    details = raw["details"]
    assert raw["status"] == "failed"
    assert raw["energy"] is None
    assert details["failure_stage"] == "unresolved"
    assert details["convergence_metadata_status"] == "unavailable_before_stage_return"
    assert details["hf_converged"] is None
    assert details["converged"] is None

    solution = pyscf_adapter.harvest(run_dir)
    data = solution["solution_data"][0]
    assert data["solution_details"]["harness_status"] == "failed"
