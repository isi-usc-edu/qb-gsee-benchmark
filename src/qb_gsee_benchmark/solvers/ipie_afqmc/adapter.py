# Copyright 2026 L3Harris Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""ipie ph-AFQMC adapter for the solver harness.

ipie is not invoked implicitly by this repository layer. ``prepare()`` writes a
self-contained run directory with FCIDUMP, harness input, solver config, and
``run.sh``. ``run()`` executes the configured external command and normalizes an
ipie result JSON or text output into ``raw_output.json``. ``harvest()`` then
emits a schema-valid benchmark solution with stochastic error bars.

Trial-wavefunction preparation belongs inside the configured command; the wall
clock measured here therefore includes UHF/MSD trial setup, AFQMC propagation,
and result extraction.
"""

from __future__ import annotations

import gzip
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.solvers.base import RAW_OUTPUT
from qb_gsee_benchmark.solvers.base import SOLUTION_OUTPUT
from qb_gsee_benchmark.solvers.base import RunManifest
from qb_gsee_benchmark.solvers.base import SolverResources
from qb_gsee_benchmark.solvers.base import default_schema_dir
from qb_gsee_benchmark.solvers.base import harness_attempted
from qb_gsee_benchmark.solvers.base import load_manifest
from qb_gsee_benchmark.solvers.base import load_problem_instance_task
from qb_gsee_benchmark.solvers.base import new_run_id
from qb_gsee_benchmark.solvers.base import read_json
from qb_gsee_benchmark.solvers.base import repo_root
from qb_gsee_benchmark.solvers.base import write_executable
from qb_gsee_benchmark.solvers.base import write_json
from qb_gsee_benchmark.solvers.base import write_manifest
from qb_gsee_benchmark.solvers.base import write_validated_solution
from qb_gsee_benchmark.utils import iso8601_timestamp

ADAPTER_NAME = "ipie_afqmc"
ADAPTER_VERSION = "0.2.0"

IPIE_SOFTWARE_DETAILS = "ipie ph-AFQMC (https://github.com/linusjoonho/ipie)."
DEFAULT_CONFIDENCE_LEVEL = 0.682689492137

SOLVER_VARIANTS: dict[str, dict[str, Any]] = {
    "ipie_uhf_trial": {
        "solver_uuid": str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "qb-gsee-benchmark:ipie_afqmc:uhf_trial:v1",
            )
        ),
        "trial_wavefunction": "UHF",
        "determinant_count": 1,
        "algorithm_label": "ipie ph-AFQMC with UHF trial",
    },
    "ipie_msd_trial": {
        "solver_uuid": str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "qb-gsee-benchmark:ipie_afqmc:msd_trial:v1",
            )
        ),
        "trial_wavefunction": "MSD",
        "determinant_count": None,
        "algorithm_label": (
            "ipie ph-AFQMC with multi-Slater determinant trial"
        ),
    },
}

ENERGY_PATTERNS = (
    re.compile(
        r"(?:total\s+energy|final\s+energy|mixed\s+estimate|afqmc\s+energy|energy)"
        r"\s*[:=]\s*(?P<energy>[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bE\s*[:=]\s*(?P<energy>[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)"
    ),
)

ERROR_PATTERNS = (
    re.compile(
        r"(?:error\s+bound|energy\s+uncertainty|statistical\s+error|"
        r"standard\s+error|stderr|sem|sigma)\s*[:=]\s*"
        r"(?P<error>[+]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class IPIEConfig:
    variant: str = "ipie_uhf_trial"
    num_threads: int = 1
    num_walkers: int = 512
    timestep: float = 0.005
    num_steps_per_block: int = 25
    num_blocks: int = 1000
    trial_wavefunction: str | None = None
    determinant_count: int | None = None
    command_template: str | None = None
    result_json: str = "ipie_result.json"
    energy_units: str = "Hartree"
    campaign: str | None = None
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL
    phaseless: bool = True
    random_seed: int | None = None
    solver_uuid: str | None = None
    solver_short_name: str | None = None

    def normalized_variant(self) -> str:
        return (self.solver_short_name or self.variant).strip()

    def to_dict(self) -> dict[str, Any]:
        variant = self.normalized_variant()
        if variant not in SOLVER_VARIANTS:
            known = ", ".join(sorted(SOLVER_VARIANTS))
            raise ValueError(
                f"Unsupported ipie AFQMC variant {variant}; choose {known}."
            )
        known = SOLVER_VARIANTS[variant]
        trial_wavefunction = self.trial_wavefunction or known["trial_wavefunction"]
        determinant_count = self.determinant_count
        if determinant_count is None:
            determinant_count = known["determinant_count"]
        return {
            "variant": variant,
            "num_threads": self.num_threads,
            "num_walkers": self.num_walkers,
            "timestep": self.timestep,
            "num_steps_per_block": self.num_steps_per_block,
            "num_blocks": self.num_blocks,
            "trial_wavefunction": trial_wavefunction,
            "determinant_count": determinant_count,
            "command_template": self.command_template,
            "result_json": self.result_json,
            "energy_units": self.energy_units,
            "campaign": self.campaign,
            "confidence_level": self.confidence_level,
            "phaseless": self.phaseless,
            "random_seed": self.random_seed,
            "solver_uuid": self.solver_uuid or known["solver_uuid"],
            "solver_short_name": variant,
            "algorithm_label": known["algorithm_label"],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IPIEConfig":
        return cls(
            variant=str(data.get("variant", "ipie_uhf_trial")),
            num_threads=int(data.get("num_threads", 1)),
            num_walkers=int(data.get("num_walkers", 512)),
            timestep=float(data.get("timestep", 0.005)),
            num_steps_per_block=int(data.get("num_steps_per_block", 25)),
            num_blocks=int(data.get("num_blocks", 1000)),
            trial_wavefunction=data.get("trial_wavefunction"),
            determinant_count=data.get("determinant_count"),
            command_template=data.get("command_template"),
            result_json=str(data.get("result_json", "ipie_result.json")),
            energy_units=str(data.get("energy_units", "Hartree")),
            campaign=data.get("campaign"),
            confidence_level=float(
                data.get("confidence_level", DEFAULT_CONFIDENCE_LEVEL)
            ),
            phaseless=bool(data.get("phaseless", True)),
            random_seed=data.get("random_seed"),
            solver_uuid=data.get("solver_uuid"),
            solver_short_name=data.get("solver_short_name"),
        )


def prepare(
    problem_instance_path: str | Path,
    task_uuid: str,
    fcidump_path: str | Path,
    run_dir: str | Path,
    config: IPIEConfig | None = None,
    resources: SolverResources | None = None,
    overwrite: bool = False,
) -> RunManifest:
    """Create a self-contained ipie ph-AFQMC run directory."""

    config = config or IPIEConfig()
    config_dict = config.to_dict()
    run_path = Path(run_dir)
    if run_path.exists() and any(run_path.iterdir()) and not overwrite:
        raise FileExistsError(f"{run_path} is not empty; pass overwrite=True.")
    run_path.mkdir(parents=True, exist_ok=True)

    problem_instance, task = load_problem_instance_task(problem_instance_path, task_uuid)
    input_fcidump = run_path / "input.fcidump"
    _materialize_fcidump(fcidump_path, input_fcidump)

    problem_copy = run_path / "problem_instance.json"
    task_copy = run_path / "task.json"
    config_copy = run_path / "solver_config.json"
    harness_input = run_path / "ipie_harness_input.json"
    write_json(problem_copy, problem_instance)
    write_json(task_copy, task)
    write_json(config_copy, config_dict)
    write_json(
        harness_input,
        {
            "fcidump": input_fcidump.name,
            "variant": config_dict["variant"],
            "phaseless": config_dict["phaseless"],
            "trial_wavefunction": config_dict["trial_wavefunction"],
            "determinant_count": config_dict["determinant_count"],
            "num_walkers": config_dict["num_walkers"],
            "timestep": config_dict["timestep"],
            "num_steps_per_block": config_dict["num_steps_per_block"],
            "num_blocks": config_dict["num_blocks"],
            "random_seed": config_dict["random_seed"],
        },
    )

    entrypoint = "run.sh"
    write_executable(
        run_path / entrypoint,
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "cd \"$(dirname \"$0\")\"\n"
        "python -m qb_gsee_benchmark.solvers.cli run --run-dir \"$PWD\"\n",
    )

    manifest = RunManifest(
        adapter=ADAPTER_NAME,
        adapter_version=ADAPTER_VERSION,
        run_id=new_run_id(),
        problem_instance_uuid=problem_instance["problem_instance_uuid"],
        task_uuid=task_uuid,
        solver_uuid=config_dict["solver_uuid"],
        solver_short_name=config_dict["solver_short_name"],
        resources=resources
        or SolverResources(
            cores=max(1, int(config_dict["num_threads"])),
            memory_gb=32.0,
            gpus=1,
            walltime_seconds=14400,
            hardware_tags=("gpu", "afqmc"),
        ),
        entrypoint=entrypoint,
        config=config_dict,
        files={
            "problem_instance": problem_copy.name,
            "task": task_copy.name,
            "fcidump": input_fcidump.name,
            "config": config_copy.name,
            "harness_input": harness_input.name,
            "stdout": "ipie.stdout",
            "stderr": "ipie.stderr",
            "raw_output": RAW_OUTPUT,
            "solution": SOLUTION_OUTPUT,
        },
    )
    write_manifest(run_path, manifest)
    return manifest


def run(run_dir: str | Path) -> dict[str, Any]:
    """Execute the configured external ipie command and write raw output."""

    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    config = IPIEConfig.from_dict(manifest.config)
    start = time.time()
    start_iso = iso8601_timestamp()
    status = "completed"
    error_message = None
    returncode: int | None = None
    command: list[str] = []
    stdout = ""
    stderr = ""
    energy = None
    error_bound = None
    confidence_level = config.confidence_level
    result_data: dict[str, Any] = {}

    try:
        if not config.command_template:
            raise ValueError(
                "ipie command_template is not configured for this run directory."
            )
        command = _render_command(config.command_template, run_path, manifest)
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(max(1, int(config.num_threads)))
        result = subprocess.run(
            command,
            cwd=run_path,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        returncode = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        (run_path / manifest.files["stdout"]).write_text(stdout)
        (run_path / manifest.files["stderr"]).write_text(stderr)
        result_data = _read_result_json(run_path / config.result_json)
        energy = _first_float(
            result_data,
            ("energy", "total_energy", "afqmc_energy", "mixed_estimate", "etot"),
        )
        if energy is None:
            energy = parse_energy(stdout + "\n" + stderr)
        error_bound = _first_float(
            result_data,
            (
                "error_bound",
                "energy_uncertainty",
                "statistical_error",
                "standard_error",
                "sem",
            ),
        )
        if error_bound is None:
            error_bound = parse_error_bound(stdout + "\n" + stderr)
        parsed_confidence = _first_float(result_data, ("confidence_level",))
        if parsed_confidence is not None:
            confidence_level = parsed_confidence
        if returncode != 0:
            raise RuntimeError(f"ipie command exited with code {returncode}.")
        if energy is None:
            raise RuntimeError("ipie command completed but no energy was parsed.")
        if error_bound is None:
            raise RuntimeError(
                "ipie command completed but no stochastic error bound was parsed."
            )
        if error_bound < 0:
            raise RuntimeError("ipie stochastic error bound must be non-negative.")
        if not 0 <= confidence_level <= 1:
            raise RuntimeError("ipie confidence_level must be between 0 and 1.")
    except Exception as exc:
        status = "failed"
        error_message = str(exc)

    stop = time.time()
    raw_output = {
        "adapter": manifest.adapter,
        "adapter_version": manifest.adapter_version,
        "run_id": manifest.run_id,
        "status": status,
        "variant": config.normalized_variant(),
        "energy": energy if status == "completed" else None,
        "energy_units": config.energy_units,
        "error_bound": error_bound if status == "completed" else None,
        "energy_uncertainty": error_bound if status == "completed" else None,
        "confidence_level": confidence_level,
        "error_message": error_message,
        "details": {
            "command": command,
            "returncode": returncode,
            "stdout_file": manifest.files["stdout"],
            "stderr_file": manifest.files["stderr"],
            "result_json": config.result_json,
            "result_data": result_data,
            "trial_wavefunction": manifest.config["trial_wavefunction"],
            "determinant_count": manifest.config["determinant_count"],
            "num_walkers": manifest.config["num_walkers"],
            "timestep": manifest.config["timestep"],
            "num_steps_per_block": manifest.config["num_steps_per_block"],
            "num_blocks": manifest.config["num_blocks"],
            "timing_note": (
                "Measured wall clock includes trial preparation and AFQMC "
                "propagation performed by the configured external command."
            ),
        },
        "timing": {
            "wall_clock_start_time": start_iso,
            "wall_clock_stop_time": iso8601_timestamp(),
            "seconds": stop - start,
        },
        "software": {
            "ipie": IPIE_SOFTWARE_DETAILS,
            "python_version": platform.python_version(),
        },
    }
    write_json(run_path / RAW_OUTPUT, raw_output)
    write_manifest(run_path, manifest.with_status(status))
    if status != "completed":
        raise RuntimeError(error_message)
    return raw_output


def harvest(
    run_dir: str | Path,
    output_path: str | Path | None = None,
    schema_dir: str | Path | None = None,
    not_attempted_reason: str | None = None,
    missing_output_status: str = "not_attempted",
) -> dict[str, Any]:
    """Convert ipie raw output to a schema-valid benchmark solution JSON."""

    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    problem_instance = read_json(run_path / manifest.files["problem_instance"])
    raw_path = run_path / manifest.files["raw_output"]
    if raw_path.exists():
        raw_output = read_json(raw_path)
    else:
        raw_output = _not_attempted_raw_output(
            manifest, not_attempted_reason, missing_output_status
        )
        write_json(raw_path, raw_output)
        write_manifest(run_path, manifest.with_status(missing_output_status))
    output_path = (
        Path(output_path) if output_path is not None else run_path / SOLUTION_OUTPUT
    )
    config = IPIEConfig.from_dict(manifest.config)
    timing = raw_output.get("timing", {})
    status = raw_output.get("status", "failed")
    attempted = harness_attempted(status)
    completed = status == "completed"
    energy = raw_output.get("energy") if completed else None

    solution_data = {
        "task_uuid": manifest.task_uuid,
        "energy": energy,
        "energy_units": config.energy_units,
        "run_time": {
            "overall_time": {
                "wall_clock_start_time": timing.get("wall_clock_start_time"),
                "wall_clock_stop_time": timing.get("wall_clock_stop_time"),
                "seconds": float(timing.get("seconds", 0.0)),
            },
            "preprocessing_time": {"seconds": 0.0},
            "algorithm_run_time": {
                "wall_clock_start_time": timing.get("wall_clock_start_time"),
                "wall_clock_stop_time": timing.get("wall_clock_stop_time"),
                "seconds": float(timing.get("seconds", 0.0)),
            },
            "postprocessing_time": {"seconds": 0.0},
        },
        "solution_details": {
            "harness_status": status,
            "campaign": manifest.config.get("campaign"),
            "attempted": attempted,
            "not_attempted_reason": None
            if completed
            else raw_output.get("error_message", "run did not complete"),
            "run_directory_id": manifest.run_id,
            "raw_output_file": manifest.files["raw_output"],
            "ipie_afqmc_details": raw_output.get("details", {}),
            "trial_wavefunction": manifest.config["trial_wavefunction"],
            "determinant_count": manifest.config["determinant_count"],
            "num_walkers": manifest.config["num_walkers"],
            "timestep": manifest.config["timestep"],
            "num_steps_per_block": manifest.config["num_steps_per_block"],
            "num_blocks": manifest.config["num_blocks"],
        },
    }
    if completed:
        solution_data["error_bound"] = float(raw_output["error_bound"])
        solution_data["confidence_level"] = float(raw_output["confidence_level"])

    solution = {
        "$schema": (
            "https://raw.githubusercontent.com/isi-usc-edu/qb-gsee-benchmark/"
            "main/schemas/solution.schema.0.0.1.json"
        ),
        "solution_uuid": str(uuid.uuid4()),
        "problem_instance_uuid": manifest.problem_instance_uuid,
        "creation_timestamp": iso8601_timestamp(),
        "contact_info": [
            {
                "name": "QB-GSEE Benchmark Harness",
                "email": "bobqat@l3harris.com",
                "institution": "L3Harris Technologies, Inc.",
            }
        ],
        "is_resource_estimate": False,
        "solution_data": [solution_data],
        "solver_details": {
            "solver_uuid": manifest.solver_uuid,
            "solver_short_name": manifest.solver_short_name,
            "compute_hardware_type": "classical_computer",
            "classical_hardware_details": {
                "total_num_cores": manifest.resources.cores,
                "ram_available_gb": manifest.resources.memory_gb,
                "computing_environment_name": "harness run directory",
            },
            "algorithm_details": {
                "name": config.to_dict()["algorithm_label"],
                "solver_config": manifest.config,
                "harness_adapter": manifest.adapter,
                "harness_adapter_version": manifest.adapter_version,
            },
            "software_details": raw_output.get("software", {}),
        },
        "digital_signature": None,
    }
    write_validated_solution(
        output_path,
        solution,
        schema_dir=schema_dir or default_schema_dir(),
    )
    write_manifest(run_path, manifest.with_status("harvested"))
    write_json(
        run_path / "harvest_summary.json",
        {
            "solution_file": str(output_path),
            "task_count": len(problem_instance.get("tasks", [])),
            "status": status,
        },
    )
    return solution


def smoke_test(run_dir: str | Path | None = None) -> dict[str, Any]:
    """Exercise H2 and LiH validation instances through the ipie harness path."""

    cleanup = None
    if run_dir is None:
        cleanup = tempfile.TemporaryDirectory()
        run_dir = cleanup.name

    root = repo_root()
    output_root = Path(run_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    cases = [
        {
            "name": "H2",
            "problem_instance": root
            / "problem_instances"
            / "validation_instances"
            / (
                "problem_instance.validation.H2.cc-PVDZ."
                "9162371c-b23f-45a6-bacd-44cb7aaea917.json"
            ),
            "fcidump": root
            / "scripts"
            / "development"
            / (
                "validation.H2.cc-PVDZ."
                "bbcd09f2-8a89-4f35-9577-7851a76ea17c.fcidump.gz"
            ),
            "task_uuid": "f847059f-a89f-4008-9ae1-39847c899e75",
        },
        {
            "name": "LiH",
            "problem_instance": root
            / "problem_instances"
            / "validation_instances"
            / (
                "problem_instance.validation.LiH.cc-PVDZ."
                "00ec23d5-3e17-46d3-a8b6-9ceff1826377.json"
            ),
            "fcidump": root
            / "scripts"
            / "development"
            / (
                "validation.LiH.cc-PVDZ."
                "7298a64d-1574-42d7-b092-3e9f686ec162.fcidump.gz"
            ),
            "task_uuid": "2b2eefc4-9c8c-4a02-b621-059774f620c4",
        },
    ]

    solutions: dict[str, Any] = {}
    for case in cases:
        _problem_instance, task = load_problem_instance_task(
            case["problem_instance"],
            str(case["task_uuid"]),
        )
        reference_energy = float(task["requirements"]["reference_energy"])
        error_bound = min(
            float(task["requirements"]["absolute_accuracy_threshold"]),
            1.0e-6,
        )
        case_dir = output_root / case["name"]
        prepare(
            problem_instance_path=case["problem_instance"],
            task_uuid=str(case["task_uuid"]),
            fcidump_path=case["fcidump"],
            run_dir=case_dir,
            config=IPIEConfig(
                variant="ipie_uhf_trial",
                num_threads=1,
                num_walkers=16,
                timestep=0.005,
                num_steps_per_block=2,
                num_blocks=3,
                command_template=_fake_result_command(reference_energy, error_bound),
            ),
            overwrite=True,
        )
        run(case_dir)
        solution = harvest(case_dir)
        data = solution["solution_data"][0]
        if abs(data["energy"] - reference_energy) > data["error_bound"]:
            raise AssertionError(
                f"ipie smoke {case['name']} energy {data['energy']} was not "
                f"within {data['error_bound']} of {reference_energy}."
            )
        solutions[str(case["name"])] = solution

    if cleanup is not None:
        cleanup.cleanup()
    return {
        "adapter": ADAPTER_NAME,
        "problem_instances": {
            name: solution["problem_instance_uuid"]
            for name, solution in solutions.items()
        },
        "solutions": solutions,
    }


def parse_energy(text: str) -> float | None:
    """Parse the last recognizable AFQMC energy from text output."""

    matches: list[float] = []
    for pattern in ENERGY_PATTERNS:
        matches.extend(float(match.group("energy")) for match in pattern.finditer(text))
    return matches[-1] if matches else None


def parse_error_bound(text: str) -> float | None:
    """Parse the last recognizable stochastic error bound from text output."""

    matches: list[float] = []
    for pattern in ERROR_PATTERNS:
        matches.extend(float(match.group("error")) for match in pattern.finditer(text))
    return matches[-1] if matches else None


def _render_command(
    command_template: str,
    run_path: Path,
    manifest: RunManifest,
) -> list[str]:
    config = IPIEConfig.from_dict(manifest.config)
    determinant_count = manifest.config.get("determinant_count")
    placeholders = {
        "run_dir": str(run_path),
        "fcidump": manifest.files["fcidump"],
        "fcidump_abs": str((run_path / manifest.files["fcidump"]).resolve()),
        "config": manifest.files["config"],
        "config_abs": str((run_path / manifest.files["config"]).resolve()),
        "harness_input": manifest.files["harness_input"],
        "harness_input_abs": str(
            (run_path / manifest.files["harness_input"]).resolve()
        ),
        "num_threads": str(config.num_threads),
        "num_walkers": str(config.num_walkers),
        "timestep": str(config.timestep),
        "num_steps_per_block": str(config.num_steps_per_block),
        "num_blocks": str(config.num_blocks),
        "trial_wavefunction": str(manifest.config["trial_wavefunction"]),
        "determinant_count": ""
        if determinant_count is None
        else str(determinant_count),
    }
    return shlex.split(command_template.format(**placeholders))


def _materialize_fcidump(source: str | Path, destination: str | Path) -> None:
    source_path = Path(source)
    destination_path = Path(destination)
    if source_path.suffix == ".gz":
        with gzip.open(source_path, "rb") as src, destination_path.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    else:
        shutil.copy2(source_path, destination_path)


def _not_attempted_raw_output(
    manifest: RunManifest,
    reason: str | None,
    status: str = "not_attempted",
) -> dict[str, Any]:
    harness_attempted(status)
    message = reason or "run did not produce raw_output.json"
    timestamp = iso8601_timestamp()
    return {
        "adapter": manifest.adapter,
        "adapter_version": manifest.adapter_version,
        "run_id": manifest.run_id,
        "status": status,
        "variant": manifest.config.get("variant"),
        "energy": None,
        "energy_units": manifest.config.get("energy_units", "Hartree"),
        "error_bound": None,
        "energy_uncertainty": None,
        "confidence_level": manifest.config.get(
            "confidence_level",
            DEFAULT_CONFIDENCE_LEVEL,
        ),
        "error_message": message,
        "details": {"not_attempted_reason": message},
        "timing": {
            "wall_clock_start_time": timestamp,
            "wall_clock_stop_time": timestamp,
            "seconds": 0.0,
        },
        "software": {
            "ipie": IPIE_SOFTWARE_DETAILS,
            "python_version": platform.python_version(),
        },
    }


def _read_result_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def _first_float(data: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return float(value)
    return None


def _fake_result_command(energy: float, error_bound: float) -> str:
    code = (
        "import json; "
        f"json.dump(dict(energy={energy!r}, error_bound={error_bound!r}, "
        f"confidence_level={DEFAULT_CONFIDENCE_LEVEL!r}), "
        "open('ipie_result.json', 'w'))"
    )
    return f"{sys.executable} -c {shlex.quote(code)}"
