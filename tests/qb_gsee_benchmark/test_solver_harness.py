import json
import shlex
import sys
from pathlib import Path

import pytest

from qb_gsee_benchmark.solvers import pyscf_adapter
from qb_gsee_benchmark.solvers.dmrg_block2 import adapter as dmrg_adapter
from qb_gsee_benchmark.solvers import shci_adapter
from qb_gsee_benchmark.solvers.ipie_afqmc import adapter as ipie_adapter
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
LIH_PROBLEM_INSTANCE = (
    REPO_ROOT
    / "problem_instances"
    / "validation_instances"
    / "problem_instance.validation.LiH.cc-PVDZ.00ec23d5-3e17-46d3-a8b6-9ceff1826377.json"
)
LIH_FCIDUMP = (
    REPO_ROOT
    / "scripts"
    / "development"
    / "validation.LiH.cc-PVDZ.7298a64d-1574-42d7-b092-3e9f686ec162.fcidump.gz"
)
LIH_TASK_UUID = "2b2eefc4-9c8c-4a02-b621-059774f620c4"
H2_PYSCF_GOLDEN = [
    ("HF", "5f5e617a-19c2-4d82-bebc-b2d6b3dcb012", -1.1287110109153249),
    ("MP2", "b420358b-5def-41e6-8c5d-b9d93b6aecd2", -1.155091625687221),
    ("CISD", "418f060e-496b-4024-8d2d-9b1f8791e76d", -1.1634029610635777),
    ("CCSD", "0a29e54f-bef9-4d19-bafa-d94b1c4b37aa", -1.1634029671742296),
    ("CCSD(T)", "c09217e6-d0f7-4b0f-81c4-79210b7ac878", -1.1634029671742296),
]
H2_SHCI_GOLDEN = (
    REPO_ROOT
    / "solution_files"
    / "SHCI"
    / "solution.SHCI.validation.H2.cc-PVDZ.9162371c-b23f-45a6-bacd-44cb7aaea917_3fc1d523-c4dc-46d1-beed-1b5aea9be12f.json"
)


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


def test_shci_adapter_smoke_matches_existing_h2_solution(tmp_path):
    run_dir = tmp_path / "shci-smoke"

    solution = shci_adapter.smoke_test(run_dir=run_dir)
    golden = json.loads(H2_SHCI_GOLDEN.read_text())

    assert (run_dir / "solution.json").exists()
    assert (run_dir / "raw_output.json").exists()
    assert solution["solution_data"][0]["energy"] == (
        golden["solution_data"][0]["energy"]
    )
    assert solution["solver_details"]["solver_uuid"] == (
        golden["solver_details"]["solver_uuid"]
    )
    assert solution["solver_details"]["solver_short_name"] == "SHCI_opt"


def test_shci_adapter_runs_configured_external_command(tmp_path):
    run_dir = tmp_path / "shci-command"
    command = f"{sys.executable} -c 'print(\"Total Energy = -1.2345\")'"

    shci_adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=shci_adapter.SHCIConfig(
            variant="SHCI_var_2e-5",
            num_threads=2,
            command_template=command,
        ),
        overwrite=True,
    )
    raw_output = shci_adapter.run(run_dir)
    solution = shci_adapter.harvest(run_dir)

    assert raw_output["status"] == "completed"
    assert raw_output["energy"] == -1.2345
    assert (run_dir / "shci.stdout").exists()
    assert solution["solver_details"]["solver_uuid"] == (
        "86bfe50c-9342-4d54-bb68-abc8abd95688"
    )
    assert solution["solver_details"]["solver_short_name"] == "SHCI_var_2e-5"
    assert solution["solution_data"][0]["energy"] == -1.2345


def test_shci_harvest_missing_raw_output_marks_not_attempted(tmp_path):
    run_dir = tmp_path / "shci-missing-raw"
    reason = "scheduler exhausted retry budget before SHCI produced raw output"

    shci_adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=shci_adapter.SHCIConfig(variant="SHCI_pt_2e-5"),
        overwrite=True,
    )
    solution = shci_adapter.harvest(run_dir, not_attempted_reason=reason)

    raw_output = json.loads((run_dir / "raw_output.json").read_text())
    data = solution["solution_data"][0]
    assert raw_output["status"] == "not_attempted"
    assert raw_output["error_message"] == reason
    assert data["energy"] is None
    assert data["solution_details"]["attempted"] is False
    assert data["solution_details"]["not_attempted_reason"] == reason
    assert solution["solver_details"]["solver_short_name"] == "SHCI_pt_2e-5"



def test_ipie_adapter_runs_configured_external_command(tmp_path):
    run_dir = tmp_path / "ipie-command"
    code = (
        "import json; "
        "json.dump(dict(energy=-1.2345, error_bound=0.0007, "
        "confidence_level=0.95), open('ipie_result.json', 'w'))"
    )
    command = f"{sys.executable} -c {shlex.quote(code)}"

    manifest = ipie_adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=ipie_adapter.IPIEConfig(
            variant="ipie_msd_trial",
            num_threads=2,
            num_walkers=64,
            timestep=0.01,
            num_steps_per_block=5,
            num_blocks=7,
            determinant_count=128,
            command_template=command,
        ),
        overwrite=True,
    )
    raw_output = ipie_adapter.run(run_dir)
    solution = ipie_adapter.harvest(run_dir)

    data = solution["solution_data"][0]
    assert manifest.resources.gpus == 1
    assert raw_output["status"] == "completed"
    assert raw_output["energy"] == -1.2345
    assert raw_output["error_bound"] == 0.0007
    assert raw_output["confidence_level"] == 0.95
    assert (run_dir / "ipie.stdout").exists()
    assert solution["solver_details"]["solver_uuid"] == (
        ipie_adapter.SOLVER_VARIANTS["ipie_msd_trial"]["solver_uuid"]
    )
    assert solution["solver_details"]["solver_short_name"] == "ipie_msd_trial"
    assert data["energy"] == -1.2345
    assert data["error_bound"] == 0.0007
    assert data["confidence_level"] == 0.95
    assert data["solution_details"]["trial_wavefunction"] == "MSD"
    assert data["solution_details"]["determinant_count"] == 128


def test_ipie_harvest_missing_raw_output_marks_not_attempted(tmp_path):
    run_dir = tmp_path / "ipie-missing-raw"
    reason = "scheduler exhausted GPU allocation before ipie produced raw output"

    ipie_adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=ipie_adapter.IPIEConfig(variant="ipie_uhf_trial"),
        overwrite=True,
    )
    solution = ipie_adapter.harvest(run_dir, not_attempted_reason=reason)

    raw_output = json.loads((run_dir / "raw_output.json").read_text())
    data = solution["solution_data"][0]
    assert raw_output["status"] == "not_attempted"
    assert raw_output["error_message"] == reason
    assert data["energy"] is None
    assert "error_bound" not in data
    assert data["solution_details"]["attempted"] is False
    assert data["solution_details"]["not_attempted_reason"] == reason
    assert solution["solver_details"]["solver_short_name"] == "ipie_uhf_trial"


def test_ipie_adapter_smoke_exercises_h2_and_lih(tmp_path):
    run_dir = tmp_path / "ipie-smoke"

    summary = ipie_adapter.smoke_test(run_dir=run_dir)

    assert set(summary["solutions"]) == {"H2", "LiH"}
    assert (run_dir / "H2" / "solution.json").exists()
    assert (run_dir / "LiH" / "solution.json").exists()
    h2_data = summary["solutions"]["H2"]["solution_data"][0]
    lih_data = summary["solutions"]["LiH"]["solution_data"][0]
    assert h2_data["task_uuid"] == H2_TASK_UUID
    assert lih_data["task_uuid"] == LIH_TASK_UUID
    for solution in summary["solutions"].values():
        data = solution["solution_data"][0]
        assert solution["solver_details"]["solver_short_name"] == "ipie_uhf_trial"
        assert data["error_bound"] == pytest.approx(1.0e-6)
        assert data["confidence_level"] == pytest.approx(
            ipie_adapter.DEFAULT_CONFIDENCE_LEVEL
        )



def test_dmrg_adapter_runs_configured_external_command(tmp_path):
    run_dir = tmp_path / "dmrg-command"
    code = (
        "import json; "
        "json.dump(dict(energy=-1.2345, bond_dimension=64, "
        "discarded_weight=1.0e-8), open('dmrg_result.json', 'w'))"
    )
    command = f"{sys.executable} -c {shlex.quote(code)}"

    manifest = dmrg_adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=dmrg_adapter.DMRGConfig(
            variant="DMRG_fixed_budget",
            num_threads=2,
            max_bond_dimension=64,
            command_template=command,
        ),
        overwrite=True,
    )
    raw_output = dmrg_adapter.run(run_dir)
    solution = dmrg_adapter.harvest(run_dir)

    data = solution["solution_data"][0]
    assert manifest.resources.cores == 2
    assert manifest.resources.gpus == 0
    assert raw_output["status"] == "completed"
    assert raw_output["energy"] == -1.2345
    assert (run_dir / "dmrg.stdout").exists()
    assert solution["solver_details"]["solver_uuid"] == (
        dmrg_adapter.EXISTING_NIAGARA_DMRG_UUID
    )
    assert solution["solver_details"]["solver_short_name"] == (
        dmrg_adapter.EXISTING_NIAGARA_DMRG_SHORT_NAME
    )
    assert data["energy"] == -1.2345
    assert data["solution_details"]["bond_dimension"] == 64
    assert data["solution_details"]["discarded_weight"] == 1.0e-8


def test_dmrg_extrapolated_adapter_records_extrapolation_metadata(tmp_path):
    run_dir = tmp_path / "dmrg-extrapolated"
    code = (
        "import json; "
        "json.dump(dict(variational_energy=-1.2, extrapolated_energy=-1.25, "
        "bond_dimension=256, discarded_weight=2.0e-6, "
        "extrapolation_distance=0.003, extrapolation_model='linear'), "
        "open('dmrg_result.json', 'w'))"
    )
    command = f"{sys.executable} -c {shlex.quote(code)}"

    dmrg_adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=dmrg_adapter.DMRGConfig(
            variant="DMRG_extrapolated",
            num_threads=4,
            bond_dimensions=(64, 128, 256),
            orbital_reordering="Fiedler",
            extrapolation_model="linear_discarded_weight",
            command_template=command,
        ),
        overwrite=True,
    )
    raw_output = dmrg_adapter.run(run_dir)
    solution = dmrg_adapter.harvest(run_dir)

    data = solution["solution_data"][0]
    assert raw_output["energy"] == -1.25
    assert solution["solver_details"]["solver_short_name"] == "DMRG_extrapolated"
    assert data["energy"] == -1.25
    assert data["solution_details"]["variant"] == "DMRG_extrapolated"
    assert data["solution_details"]["orbital_reordering"] == "Fiedler"
    assert data["solution_details"]["extrapolation_distance"] == 0.003
    assert data["solution_details"]["extrapolation_model"] == (
        "linear_discarded_weight"
    )


def test_dmrg_harvest_missing_raw_output_marks_not_attempted(tmp_path):
    run_dir = tmp_path / "dmrg-missing-raw"
    reason = "scheduler exhausted Niagara allocation before DMRG produced raw output"

    dmrg_adapter.prepare(
        problem_instance_path=H2_PROBLEM_INSTANCE,
        task_uuid=H2_TASK_UUID,
        fcidump_path=H2_FCIDUMP,
        run_dir=run_dir,
        config=dmrg_adapter.DMRGConfig(variant="DMRG_fixed_budget"),
        overwrite=True,
    )
    solution = dmrg_adapter.harvest(run_dir, not_attempted_reason=reason)

    raw_output = json.loads((run_dir / "raw_output.json").read_text())
    data = solution["solution_data"][0]
    assert raw_output["status"] == "not_attempted"
    assert raw_output["error_message"] == reason
    assert data["energy"] is None
    assert data["solution_details"]["attempted"] is False
    assert data["solution_details"]["not_attempted_reason"] == reason
    assert solution["solver_details"]["solver_short_name"] == (
        dmrg_adapter.EXISTING_NIAGARA_DMRG_SHORT_NAME
    )


def test_dmrg_adapter_smoke_exercises_h2_and_lih(tmp_path):
    run_dir = tmp_path / "dmrg-smoke"

    summary = dmrg_adapter.smoke_test(run_dir=run_dir)

    assert set(summary["solutions"]) == {"H2", "LiH"}
    assert (run_dir / "H2" / "solution.json").exists()
    assert (run_dir / "LiH" / "solution.json").exists()
    h2_data = summary["solutions"]["H2"]["solution_data"][0]
    lih_data = summary["solutions"]["LiH"]["solution_data"][0]
    assert h2_data["task_uuid"] == H2_TASK_UUID
    assert lih_data["task_uuid"] == LIH_TASK_UUID
    for solution in summary["solutions"].values():
        assert solution["solver_details"]["solver_short_name"] == (
            dmrg_adapter.EXISTING_NIAGARA_DMRG_SHORT_NAME
        )


def test_repo_layer_does_not_reference_hpc_site_layer():
    source_root = Path(__file__).parents[2] / "src" / "qb_gsee_benchmark"
    for path in source_root.rglob("*.py"):
        text = path.read_text()
        assert "hpc/" not in text
        assert "qsub" not in text

