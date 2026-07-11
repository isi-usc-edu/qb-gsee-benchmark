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


@pytest.mark.parametrize("adapter_name,method,solver_uuid,expected_energy", METHOD_CASES)
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
        overwrite=True,
    )

    raw_output = pyscf_adapter.run(run_dir)
    solution = pyscf_adapter.harvest(run_dir)
    data = solution["solution_data"][0]

    assert manifest.adapter == adapter_name
    assert manifest.adapter_version == "0.3.0"
    assert manifest.solver_uuid == solver_uuid
    assert manifest.solver_short_name == method
    assert manifest.config["method"] == method
    assert manifest.config["campaign"] == pyscf_adapter.METHOD_CAMPAIGN
    assert manifest.resources.walltime_seconds == 1800
    assert raw_output["status"] == "completed"
    assert data["energy"] == pytest.approx(expected_energy, abs=1.0e-10)
    assert data["solution_details"]["harness_status"] == "completed"
    assert data["solution_details"]["attempted"] is True
    assert data["solution_details"]["campaign"] == pyscf_adapter.METHOD_CAMPAIGN


def test_method_adapter_uses_legacy_uhf_open_shell_convention(tmp_path):
    run_dir = tmp_path / "hf-hydrogen"
    pyscf_adapter.prepare_method(
        method="HF",
        problem_instance_path=H_PROBLEM_INSTANCE,
        task_uuid=H_TASK_UUID,
        fcidump_path=H_FCIDUMP,
        run_dir=run_dir,
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
    assert data["solution_details"]["campaign"] == pyscf_adapter.METHOD_CAMPAIGN
    assert data["run_time"]["overall_time"]["seconds"] == 1800.25


def test_batch_method_aliases_freeze_method_and_campaign(tmp_path):
    plan = tmp_path / "plan.csv"
    output_root = tmp_path / "runs"
    rows = [
        (
            f"{adapter},{adapter},{H2_PROBLEM_INSTANCE},{H2_TASK_UUID},"
            f"{H2_FCIDUMP},FCI,2"
        )
        for adapter, _method, _uuid, _energy in METHOD_CASES
    ]
    plan.write_text(
        "adapter,run_name,problem_instance,task_uuid,fcidump,method,num_threads\n"
        + "\n".join(rows)
        + "\n"
    )

    summary = batch.prepare_batch(plan, output_root, overwrite=True)

    assert summary["prepared_count"] == 5
    for adapter_name, method, _uuid, _energy in METHOD_CASES:
        manifest = load_manifest(output_root / adapter_name)
        assert manifest.adapter == adapter_name
        assert manifest.config["method"] == method
        assert manifest.config["campaign"] == pyscf_adapter.METHOD_CAMPAIGN
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
    assert cli.main(["prepare-pyscf-method", *common, "--method", "HF"]) == 0
    assert cli.main(["run", "--run-dir", str(run_dir)]) == 0
    assert cli.main(["harvest", "--run-dir", str(run_dir)]) == 0
    capsys.readouterr()

    record = json.loads((run_dir / "solution.json").read_text())
    data = record["solution_data"][0]
    assert record["problem_instance_uuid"] == "9162371c-b23f-45a6-bacd-44cb7aaea917"
    assert data["task_uuid"] == H2_TASK_UUID
    assert data["energy"] == pytest.approx(-1.1287110109153249, abs=1.0e-10)
    assert record["solver_details"]["solver_short_name"] == "HF"
    assert record["solver_details"]["algorithm_details"]["harness_adapter"] == "pyscf_hf"
    assert data["solution_details"]["campaign"] == pyscf_adapter.METHOD_CAMPAIGN
