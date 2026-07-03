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

"""SHCI/Arrow adapter for the solver harness.

The historical SHCI data in this repository are solution JSONs produced with
the Arrow SHCI code, not a checked-in runner script. This adapter therefore
keeps the execution command explicit in the run manifest: ``prepare()`` writes
the FCIDUMP, solver config, and ``run.sh``; ``run()`` executes the configured
external command and normalizes stdout/stderr or a result JSON into
``raw_output.json``; ``harvest()`` schema-validates the benchmark solution.

The site layer may submit the run directory through PBS, but no PBS or local
cluster policy belongs here.
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

ADAPTER_NAME = "shci_arrow"
ADAPTER_VERSION = "0.1.0"

SHCI_SOFTWARE_DETAILS = "SHCI Arrow Code (https://github.com/QMC-Cornell/shci)."
GOLDEN_H2_SOLUTION = (
    "solution_files/SHCI/"
    "solution.SHCI.validation.H2.cc-PVDZ."
    "9162371c-b23f-45a6-bacd-44cb7aaea917_"
    "3fc1d523-c4dc-46d1-beed-1b5aea9be12f.json"
)

SOLVER_VARIANTS: dict[str, dict[str, Any]] = {
    "SHCI_opt": {
        "solver_uuid": "2dde727e-a881-44fa-aabf-bba6248e4baf",
        "eps_var_label": None,
        "pt_correction": True,
        "optimized_orbitals": True,
        "algorithm_label": "SHCI with optimized orbitals followed by SHCI+PT",
    },
    "SHCI_var_1e-4": {
        "solver_uuid": "7e730dfb-57ee-480b-a8a1-4b73f5f07c54",
        "eps_var_label": "1e-4",
        "pt_correction": False,
    },
    "SHCI_var_5e-5": {
        "solver_uuid": "01949b95-c427-4693-9134-01f47f688c09",
        "eps_var_label": "5e-5",
        "pt_correction": False,
    },
    "SHCI_var_2e-5": {
        "solver_uuid": "86bfe50c-9342-4d54-bb68-abc8abd95688",
        "eps_var_label": "2e-5",
        "pt_correction": False,
    },
    "SHCI_var_2e-4": {
        "solver_uuid": "0db183e3-a86d-491b-9125-599556e37c7a",
        "eps_var_label": "2e-4",
        "pt_correction": False,
    },
    "SHCI_pt_1e-4": {
        "solver_uuid": "4ed500f1-0650-41e3-af00-e4d0359394b4",
        "eps_var_label": "1e-4",
        "pt_correction": True,
    },
    "SHCI_pt_5e-5": {
        "solver_uuid": "d626506c-7aae-4ad6-802a-b29af5f2bb93",
        "eps_var_label": "5e-5",
        "pt_correction": True,
    },
    "SHCI_pt_2e-5": {
        "solver_uuid": "c71b90bd-3250-4c0c-b4e7-fc9878f141f6",
        "eps_var_label": "2e-5",
        "pt_correction": True,
    },
    "SHCI_pt_2e-4": {
        "solver_uuid": "ad964781-302e-4728-a26d-39918e0a6cdb",
        "eps_var_label": "2e-4",
        "pt_correction": True,
    },
}

ENERGY_PATTERNS = (
    re.compile(
        r"(?:total\s+energy|final\s+energy|shci\s+energy|energy)\s*[:=]\s*"
        r"(?P<energy>[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bE\s*[:=]\s*(?P<energy>[+-]?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)"
    ),
)


@dataclass(frozen=True)
class SHCIConfig:
    variant: str = "SHCI_opt"
    num_threads: int = 1
    command_template: str | None = None
    result_json: str = "shci_result.json"
    eps_var: float | None = None
    eps_var_label: str | None = None
    pt_correction: bool | None = None
    optimized_orbitals: bool | None = None
    energy_units: str = "Hartree"
    solver_uuid: str | None = None
    solver_short_name: str | None = None

    def normalized_variant(self) -> str:
        return (self.solver_short_name or self.variant).strip()

    def to_dict(self) -> dict[str, Any]:
        variant = self.normalized_variant()
        known = SOLVER_VARIANTS.get(variant, {})
        eps_var_label = self.eps_var_label or known.get("eps_var_label")
        eps_var = self.eps_var
        if eps_var is None and eps_var_label is not None:
            eps_var = float(eps_var_label)
        pt_correction = self.pt_correction
        if pt_correction is None:
            pt_correction = known.get("pt_correction", False)
        optimized_orbitals = self.optimized_orbitals
        if optimized_orbitals is None:
            optimized_orbitals = known.get("optimized_orbitals", False)
        solver_uuid = (
            self.solver_uuid
            or known.get("solver_uuid")
            or str(uuid.uuid5(uuid.NAMESPACE_URL, f"qb-gsee-benchmark:shci:{variant}:v1"))
        )
        algorithm_label = known.get("algorithm_label") or _algorithm_label(
            eps_var_label=eps_var_label,
            pt_correction=bool(pt_correction),
            optimized_orbitals=bool(optimized_orbitals),
        )
        return {
            "variant": variant,
            "num_threads": self.num_threads,
            "command_template": self.command_template,
            "result_json": self.result_json,
            "eps_var": eps_var,
            "eps_var_label": eps_var_label,
            "pt_correction": bool(pt_correction),
            "optimized_orbitals": bool(optimized_orbitals),
            "energy_units": self.energy_units,
            "solver_uuid": solver_uuid,
            "solver_short_name": variant,
            "algorithm_label": algorithm_label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SHCIConfig":
        return cls(
            variant=str(data.get("variant", "SHCI_opt")),
            num_threads=int(data.get("num_threads", 1)),
            command_template=data.get("command_template"),
            result_json=str(data.get("result_json", "shci_result.json")),
            eps_var=data.get("eps_var"),
            eps_var_label=data.get("eps_var_label"),
            pt_correction=data.get("pt_correction"),
            optimized_orbitals=data.get("optimized_orbitals"),
            energy_units=str(data.get("energy_units", "Hartree")),
            solver_uuid=data.get("solver_uuid"),
            solver_short_name=data.get("solver_short_name"),
        )


def prepare(
    problem_instance_path: str | Path,
    task_uuid: str,
    fcidump_path: str | Path,
    run_dir: str | Path,
    config: SHCIConfig | None = None,
    resources: SolverResources | None = None,
    overwrite: bool = False,
) -> RunManifest:
    """Create a self-contained SHCI run directory."""

    config = config or SHCIConfig()
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
    harness_input = run_path / "shci_harness_input.json"
    write_json(problem_copy, problem_instance)
    write_json(task_copy, task)
    write_json(config_copy, config_dict)
    write_json(
        harness_input,
        {
            "fcidump": input_fcidump.name,
            "variant": config_dict["variant"],
            "eps_var": config_dict["eps_var"],
            "eps_var_label": config_dict["eps_var_label"],
            "pt_correction": config_dict["pt_correction"],
            "optimized_orbitals": config_dict["optimized_orbitals"],
            "num_threads": config_dict["num_threads"],
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
            memory_gb=16.0,
            gpus=0,
            walltime_seconds=7200,
        ),
        entrypoint=entrypoint,
        config=config_dict,
        files={
            "problem_instance": problem_copy.name,
            "task": task_copy.name,
            "fcidump": input_fcidump.name,
            "config": config_copy.name,
            "harness_input": harness_input.name,
            "stdout": "shci.stdout",
            "stderr": "shci.stderr",
            "raw_output": RAW_OUTPUT,
            "solution": SOLUTION_OUTPUT,
        },
    )
    write_manifest(run_path, manifest)
    return manifest


def run(run_dir: str | Path) -> dict[str, Any]:
    """Execute the configured external SHCI command and write raw output."""

    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    config = SHCIConfig.from_dict(manifest.config)
    start = time.time()
    start_iso = iso8601_timestamp()
    status = "completed"
    error_message = None
    returncode: int | None = None
    command: list[str] = []
    stdout = ""
    stderr = ""
    energy = None
    result_data: dict[str, Any] = {}

    try:
        if not config.command_template:
            raise ValueError(
                "SHCI command_template is not configured for this run directory."
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
        energy = _coerce_optional_float(result_data.get("energy"))
        if energy is None:
            energy = parse_energy(stdout + "\n" + stderr)
        if returncode != 0:
            raise RuntimeError(f"SHCI command exited with code {returncode}.")
        if energy is None:
            raise RuntimeError("SHCI command completed but no energy was parsed.")
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
        "energy_uncertainty": _coerce_optional_float(
            result_data.get("energy_uncertainty"),
            default=0.0,
        ),
        "error_message": error_message,
        "details": {
            "command": command,
            "returncode": returncode,
            "stdout_file": manifest.files["stdout"],
            "stderr_file": manifest.files["stderr"],
            "result_json": config.result_json,
            "result_data": result_data,
        },
        "timing": {
            "wall_clock_start_time": start_iso,
            "wall_clock_stop_time": iso8601_timestamp(),
            "seconds": stop - start,
        },
        "software": {
            "shci_arrow": SHCI_SOFTWARE_DETAILS,
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
) -> dict[str, Any]:
    """Convert SHCI raw output to a schema-valid benchmark solution JSON."""

    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    problem_instance = read_json(run_path / manifest.files["problem_instance"])
    raw_path = run_path / manifest.files["raw_output"]
    if raw_path.exists():
        raw_output = read_json(raw_path)
    else:
        raw_output = _not_attempted_raw_output(manifest, not_attempted_reason)
        write_json(raw_path, raw_output)
        write_manifest(run_path, manifest.with_status("not_attempted"))
    output_path = Path(output_path) if output_path is not None else run_path / SOLUTION_OUTPUT
    config = SHCIConfig.from_dict(manifest.config)
    timing = raw_output.get("timing", {})
    status = raw_output.get("status", "failed")
    attempted = status == "completed"
    energy = raw_output.get("energy") if attempted else None

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
        "solution_data": [
            {
                "task_uuid": manifest.task_uuid,
                "energy": energy,
                "energy_units": config.energy_units,
                "energy_uncertainty": raw_output.get("energy_uncertainty", 0.0),
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
                    "attempted": attempted,
                    "not_attempted_reason": None
                    if attempted
                    else raw_output.get("error_message", "run did not complete"),
                    "run_directory_id": manifest.run_id,
                    "raw_output_file": manifest.files["raw_output"],
                    "shci_details": raw_output.get("details", {}),
                },
            }
        ],
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
    """Golden-master SHCI harvest smoke test on H2/cc-pVDZ."""

    cleanup = None
    if run_dir is None:
        cleanup = tempfile.TemporaryDirectory()
        run_dir = cleanup.name

    root = repo_root()
    problem_instance_path = (
        root
        / "problem_instances"
        / "validation_instances"
        / "problem_instance.validation.H2.cc-PVDZ.9162371c-b23f-45a6-bacd-44cb7aaea917.json"
    )
    fcidump_path = (
        root
        / "scripts"
        / "development"
        / "validation.H2.cc-PVDZ.bbcd09f2-8a89-4f35-9577-7851a76ea17c.fcidump.gz"
    )
    golden_solution_path = root / GOLDEN_H2_SOLUTION
    golden_solution = read_json(golden_solution_path)
    golden_data = golden_solution["solution_data"][0]
    prepare(
        problem_instance_path=problem_instance_path,
        task_uuid=golden_data["task_uuid"],
        fcidump_path=fcidump_path,
        run_dir=run_dir,
        config=SHCIConfig(variant="SHCI_opt"),
        overwrite=True,
    )
    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    write_json(
        run_path / RAW_OUTPUT,
        raw_output_from_solution(golden_solution, manifest, golden_solution_path),
    )
    solution = harvest(run_path)
    energy = solution["solution_data"][0]["energy"]
    if abs(energy - golden_data["energy"]) > 1.0e-12:
        raise AssertionError(
            f"SHCI golden smoke energy {energy} did not match {golden_data['energy']}."
        )
    if cleanup is not None:
        cleanup.cleanup()
    return solution


def raw_output_from_solution(
    solution: dict[str, Any],
    manifest: RunManifest,
    source_path: str | Path,
) -> dict[str, Any]:
    """Create raw SHCI output from an existing solution file for golden tests."""

    data = solution["solution_data"][0]
    timing = data.get("run_time", {}).get("overall_time", {})
    timestamp = iso8601_timestamp()
    return {
        "adapter": manifest.adapter,
        "adapter_version": manifest.adapter_version,
        "run_id": manifest.run_id,
        "status": "completed",
        "variant": manifest.solver_short_name,
        "energy": data.get("energy"),
        "energy_units": data.get("energy_units", "Hartree"),
        "energy_uncertainty": data.get("energy_uncertainty", 0.0),
        "error_message": None,
        "details": {
            "golden_solution_uuid": solution.get("solution_uuid"),
            "source_solution_file": str(source_path),
            "source_solver_details": solution.get("solver_details", {}),
        },
        "timing": {
            "wall_clock_start_time": timing.get("wall_clock_start_time", timestamp),
            "wall_clock_stop_time": timing.get("wall_clock_stop_time", timestamp),
            "seconds": float(timing.get("seconds", 0.0)),
        },
        "software": {
            "shci_arrow": SHCI_SOFTWARE_DETAILS,
            "python_version": platform.python_version(),
        },
    }


def parse_energy(text: str) -> float | None:
    """Parse the last recognizable SHCI energy from text output."""

    matches: list[float] = []
    for pattern in ENERGY_PATTERNS:
        matches.extend(float(match.group("energy")) for match in pattern.finditer(text))
    return matches[-1] if matches else None


def _algorithm_label(
    eps_var_label: str | None,
    pt_correction: bool,
    optimized_orbitals: bool,
) -> str:
    if optimized_orbitals:
        return "SHCI with optimized orbitals followed by SHCI+PT"
    if eps_var_label is None:
        return "SHCI"
    suffix = " + PT" if pt_correction else ""
    return f"SHCI with eps_var {eps_var_label}{suffix}"


def _render_command(
    command_template: str,
    run_path: Path,
    manifest: RunManifest,
) -> list[str]:
    config = SHCIConfig.from_dict(manifest.config)
    placeholders = {
        "run_dir": str(run_path),
        "fcidump": manifest.files["fcidump"],
        "fcidump_abs": str((run_path / manifest.files["fcidump"]).resolve()),
        "config": manifest.files["config"],
        "config_abs": str((run_path / manifest.files["config"]).resolve()),
        "harness_input": manifest.files["harness_input"],
        "harness_input_abs": str((run_path / manifest.files["harness_input"]).resolve()),
        "num_threads": str(config.num_threads),
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
) -> dict[str, Any]:
    message = reason or "run did not produce raw_output.json"
    timestamp = iso8601_timestamp()
    return {
        "adapter": manifest.adapter,
        "adapter_version": manifest.adapter_version,
        "run_id": manifest.run_id,
        "status": "not_attempted",
        "variant": manifest.config.get("variant"),
        "energy": None,
        "energy_units": manifest.config.get("energy_units", "Hartree"),
        "energy_uncertainty": 0.0,
        "error_message": message,
        "details": {"not_attempted_reason": message},
        "timing": {
            "wall_clock_start_time": timestamp,
            "wall_clock_stop_time": timestamp,
            "seconds": 0.0,
        },
        "software": {
            "shci_arrow": SHCI_SOFTWARE_DETAILS,
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


def _coerce_optional_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    return float(value)
