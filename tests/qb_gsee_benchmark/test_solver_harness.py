import json
from pathlib import Path

import pytest

from qb_gsee_benchmark.solvers import pyscf_adapter
from qb_gsee_benchmark.solvers.base import RUN_MANIFEST
from qb_gsee_benchmark.solvers.base import RunManifest
from qb_gsee_benchmark.solvers.base import SolverResources
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
H2_PYSCF_GOLDEN = [
    ("HF", "5f5e617a-19c2-4d82-bebc-b2d6b3dcb012", -1.1287110109153249),
    ("MP2", "b420358b-5def-41e6-8c5d-b9d93b6aecd2", -1.155091625687221),
    ("CISD", "418f060e-496b-4024-8d2d-9b1f8791e76d", -1.1634029610635777),
    ("CCSD", "0a29e54f-bef9-4d19-bafa-d94b1c4b37aa", -1.1634029671742296),
    ("CCSD(T)", "c09217e6-d0f7-4b0f-81c4-79210b7ac878", -1.1634029671742296),
]


def test_run_manifest_round_trip(tmp_path):
    manifest = RunManifest(
        adapter="dummy",
        adapter_version="0.0",
        run_id="run-1",
        problem_instance_uuid="9162371c-b23f-45a6-bacd-44cb7aaea917",
        task_uuid="f847059f-a89f-4008-9ae1-39847c899e75",
        solver_uuid="5f5e617a-19c2-4d82-bebc-b2d6b3dcb012",
        solver_short_name="HF",
        resources=SolverResources(
            cores=2,
            memory_gb=8,
            gpus=1,
            walltime_seconds=600,
            hardware_tags=("gpu",),
        ),
        files={"fcidump": "input.fcidump"},
    )
    write_manifest(tmp_path, manifest)

    loaded = load_manifest(tmp_path)

    assert (tmp_path / RUN_MANIFEST).exists()
    assert loaded == manifest
    assert loaded.resources.hardware_tags == ("gpu",)


def test_pyscf_reference_adapter_smoke(tmp_path):
    run_dir = tmp_path / "pyscf-smoke"

    solution = pyscf_adapter.smoke_test(run_dir=run_dir)

    solution_path = run_dir / "solution.json"
    raw_output_path = run_dir / "raw_output.json"
    assert solution_path.exists()
    assert raw_output_path.exists()
    assert (run_dir / "run.sh").exists()
    assert solution["solution_data"][0]["energy"] == -1.1634029610645866
    assert solution["solver_details"]["solver_short_name"] == "FCI"

    persisted = json.loads(solution_path.read_text())
    assert persisted["solution_data"][0]["task_uuid"] == (
        "f847059f-a89f-4008-9ae1-39847c899e75"
    )


@pytest.mark.parametrize("method,solver_uuid,expected_energy", H2_PYSCF_GOLDEN)
def test_pyscf_reference_adapter_matches_h2_validation_suite(
    tmp_path,
    method,
    solver_uuid,
    expected_energy,
):
    run_dir = tmp_path / method.replace("(", "_").replace(")", "_")

    pyscf_adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=pyscf_adapter.PySCFConfig(method=method, num_threads=1),
        overwrite=True,
    )
    raw_output = pyscf_adapter.run(run_dir)
    solution = pyscf_adapter.harvest(run_dir)

    assert raw_output["status"] == "completed"
    assert solution["solver_details"]["solver_uuid"] == solver_uuid
    assert solution["solver_details"]["solver_short_name"] == method
    assert solution["solution_data"][0]["energy"] == pytest.approx(
        expected_energy,
        abs=1.0e-10,
    )
    assert solution["solution_data"][0]["solution_details"]["harness_status"] == "completed"


def test_pyscf_harvest_missing_raw_output_marks_not_attempted(tmp_path):
    run_dir = tmp_path / "missing-raw"
    reason = "scheduler killed the job before the adapter wrote raw output"

    pyscf_adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=pyscf_adapter.PySCFConfig(method="HF", num_threads=1),
        overwrite=True,
    )
    solution = pyscf_adapter.harvest(run_dir, not_attempted_reason=reason)

    raw_output = json.loads((run_dir / "raw_output.json").read_text())
    data = solution["solution_data"][0]
    assert raw_output["status"] == "not_attempted"
    assert raw_output["error_message"] == reason
    assert data["energy"] is None
    assert data["solution_details"]["attempted"] is False
    assert data["solution_details"]["not_attempted_reason"] == reason
    assert solution["solver_details"]["solver_short_name"] == "HF"


def test_repo_layer_does_not_reference_hpc_site_layer():
    source_root = Path(__file__).parents[2] / "src" / "qb_gsee_benchmark"
    for path in source_root.rglob("*.py"):
        text = path.read_text()
        assert "hpc/" not in text
        assert "qsub" not in text

