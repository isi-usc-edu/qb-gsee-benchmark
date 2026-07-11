# Copyright 2026 L3Harris Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0

"""TrimCI adapter for the scheduler-agnostic solver harness.

TrimCI is imported as an optional MIT-licensed dependency from
https://github.com/hao-zhang-quantum/TrimCI. No TrimCI source is vendored here.
The panel posture is deliberately defaults-only: one call to
``trimci.ground_state`` per task, using every field from ``trimci.Config`` at
its package default except for a recorded seed and run-local work directory.
TrimCI's default internal multi-start behavior is retained verbatim. An optional
harness-only determinant-budget grid emits correlated Phase-2 checkpoint
solutions without changing the underlying TrimCI configuration or adding solver
invocations.
"""

from __future__ import annotations

import contextlib
import copy
import gzip
import importlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

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

ADAPTER_NAME = "trimci"
ADAPTER_VERSION = "0.3.0"
SOLVER_SHORT_NAME = "TrimCI_default"
SOLVER_UUID = str(
    uuid.uuid5(uuid.NAMESPACE_URL, "qb-gsee-benchmark:solver:trimci-default:v1")
)
TRIMCI_REPOSITORY = "https://github.com/hao-zhang-quantum/TrimCI"
TRIMCI_LICENSE = "MIT"
DEFAULT_SEED = 20260710


class TrimCIUnavailableError(ImportError):
    """Raised when an execution path needs the optional TrimCI package."""


@dataclass(frozen=True)
class TrimCIConfig:
    """Panel-level settings; scientific knobs remain TrimCI defaults."""

    seed: int = DEFAULT_SEED
    num_threads: int = 1
    energy_policy: str = "pt2_if_available"
    checkpoint_ndet_grid: tuple[int, ...] = ()
    campaign: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.energy_policy != "pt2_if_available":
            raise ValueError("TrimCI panel energy_policy is fixed to pt2_if_available")
        checkpoint_grid = _validate_checkpoint_grid(self.checkpoint_ndet_grid)
        trimci = _import_trimci()
        defaults = asdict(
            trimci.Config(seed=int(self.seed), work_dir="trimci_work")
        )
        return {
            "seed": int(self.seed),
            "num_threads": max(1, int(self.num_threads)),
            "energy_policy": self.energy_policy,
            "checkpoint_ndet_grid": list(checkpoint_grid),
            "campaign": self.campaign,
            "defaults_policy": (
                "trimci.Config defaults; only seed and run-local work_dir changed"
            ),
            "trimci_config": defaults,
            "solver_uuid": SOLVER_UUID,
            "solver_short_name": SOLVER_SHORT_NAME,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrimCIConfig":
        return cls(
            seed=int(data.get("seed", DEFAULT_SEED)),
            num_threads=int(data.get("num_threads", 1)),
            energy_policy=str(data.get("energy_policy", "pt2_if_available")),
            checkpoint_ndet_grid=tuple(data.get("checkpoint_ndet_grid", ())),
            campaign=data.get("campaign"),
        )


def prepare(
    problem_instance_path: str | Path,
    task_uuid: str,
    fcidump_path: str | Path,
    run_dir: str | Path,
    config: TrimCIConfig | None = None,
    resources: SolverResources | None = None,
    overwrite: bool = False,
) -> RunManifest:
    """Create a self-contained TrimCI defaults-only run directory."""
    config_dict = (config or TrimCIConfig()).to_dict()
    run_path = Path(run_dir)
    if run_path.exists() and any(run_path.iterdir()) and not overwrite:
        raise FileExistsError(f"{run_path} is not empty; pass overwrite=True.")
    run_path.mkdir(parents=True, exist_ok=True)
    problem_instance, task = load_problem_instance_task(
        problem_instance_path, task_uuid
    )
    input_fcidump = run_path / "input.fcidump"
    _materialize_fcidump(fcidump_path, input_fcidump)
    write_json(run_path / "problem_instance.json", problem_instance)
    write_json(run_path / "task.json", task)
    write_json(run_path / "solver_config.json", config_dict)
    write_executable(
        run_path / "run.sh",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'cd "$(dirname "$0")"\n'
        'python -m qb_gsee_benchmark.solvers.cli run --run-dir "$PWD"\n',
    )
    manifest = RunManifest(
        adapter=ADAPTER_NAME,
        adapter_version=ADAPTER_VERSION,
        run_id=new_run_id(),
        problem_instance_uuid=problem_instance["problem_instance_uuid"],
        task_uuid=task_uuid,
        solver_uuid=SOLVER_UUID,
        solver_short_name=SOLVER_SHORT_NAME,
        resources=resources
        or SolverResources(
            cores=config_dict["num_threads"],
            memory_gb=32.0,
            gpus=0,
            walltime_seconds=43200,
        ),
        config=config_dict,
        files={
            "problem_instance": "problem_instance.json",
            "task": "task.json",
            "fcidump": input_fcidump.name,
            "config": "solver_config.json",
            "stdout": "trimci.stdout",
            "stderr": "trimci.stderr",
            "raw_output": RAW_OUTPUT,
            "solution": SOLUTION_OUTPUT,
        },
    )
    write_manifest(run_path, manifest)
    return manifest


def run(run_dir: str | Path) -> dict[str, Any]:
    """Run one TrimCI default workflow and persist normalized raw output."""
    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    start = time.time()
    start_iso = iso8601_timestamp()
    status = "completed"
    error_message = None
    result_data: dict[str, Any] = {}
    software: dict[str, Any] = {
        "trimci": None,
        "trimci_git_revision": None,
        "trimci_repository": TRIMCI_REPOSITORY,
        "trimci_license": TRIMCI_LICENSE,
        "python_version": platform.python_version(),
    }
    try:
        os.environ["OMP_NUM_THREADS"] = str(manifest.config["num_threads"])
        trimci = _import_trimci()
        software["trimci"] = getattr(trimci, "__version__", "unknown")
        software["trimci_git_revision"] = _trimci_git_revision(trimci)
        settings = dict(manifest.config["trimci_config"])
        settings["work_dir"] = "trimci_work"
        trimci_config = trimci.Config(**settings)
        input_fcidump = Path(manifest.files["fcidump"])
        with (run_path / manifest.files["stdout"]).open("w") as stdout:
            with (run_path / manifest.files["stderr"]).open("w") as stderr:
                with contextlib.chdir(run_path):
                    with contextlib.redirect_stdout(
                        stdout
                    ), contextlib.redirect_stderr(stderr):
                        result = trimci.ground_state(
                            str(input_fcidump),
                            config=trimci_config,
                        )
        result_dict = result.to_dict()
        diagnostics = result_dict["diagnostics"]
        energies = result_dict["energies"]
        phase2_checkpoints = _phase2_checkpoint_history(run_path)
        variational = float(energies["var"])
        pt2_correction = energies.get("pt2_correction")
        selected_energy = (
            variational + float(pt2_correction)
            if pt2_correction is not None
            else variational
        )
        result_data = {
            "energy": selected_energy,
            "variational_energy": variational,
            "pt2_correction": pt2_correction,
            "pt2_energy": (
                selected_energy if pt2_correction is not None else None
            ),
            "energy_history": energies.get("history", []),
            "pt2_history": energies.get("pt2_history", []),
            "phase2_checkpoints": phase2_checkpoints,
            "n_dets_phase0": diagnostics["n_dets_phase0"],
            "n_dets_final": diagnostics["n_dets_final"],
            "n_fci": diagnostics.get("n_fci"),
            "wall_phase0": diagnostics["wall_phase0"],
            "wall_expansion": diagnostics["wall_expansion"],
            "expansion_rounds": diagnostics["expansion_rounds"],
            "resolved_trimci_config": diagnostics["config"],
            "orbopt_phases": {
                "phase0_requested": bool(settings["orbopt"]),
                "phase0_ran": bool(settings["orbopt"])
                and bool(diagnostics.get("orbopt_dir")),
                "phase1_requested": bool(settings["enable_phase1"])
                and bool(settings["orbopt_phase1"]),
                "phase1_ran": bool(settings["enable_phase1"])
                and bool(settings["orbopt_phase1"])
                and int(diagnostics["expansion_rounds"]) > 0,
            },
            "wavefunction_normalized": bool(result.wavefunction.is_normalized),
        }
    except Exception as exc:
        status = "failed"
        error_message = f"{type(exc).__name__}: {exc}"

    stop = time.time()
    raw_output = {
        "adapter": manifest.adapter,
        "adapter_version": manifest.adapter_version,
        "run_id": manifest.run_id,
        "status": status,
        "energy": result_data.get("energy") if status == "completed" else None,
        "energy_units": "Hartree",
        "energy_uncertainty": 0.0,
        "error_message": error_message,
        "details": {
            "energy_policy": manifest.config["energy_policy"],
            "single_panel_invocation": True,
            "settings_provenance": manifest.config,
            "result": result_data,
            "stdout_file": manifest.files["stdout"],
            "stderr_file": manifest.files["stderr"],
        },
        "timing": {
            "wall_clock_start_time": start_iso,
            "wall_clock_stop_time": iso8601_timestamp(),
            "seconds": stop - start,
        },
        "software": software,
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
    missing_output_elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    """Convert TrimCI raw output to a schema-valid benchmark solution."""
    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    raw_path = run_path / manifest.files["raw_output"]
    if raw_path.exists():
        raw_output = read_json(raw_path)
    else:
        raw_output = _not_attempted_raw_output(
            manifest,
            not_attempted_reason,
            missing_output_status,
            missing_output_elapsed_seconds,
        )
        write_json(raw_path, raw_output)
        write_manifest(run_path, manifest.with_status(missing_output_status))
    output_path = (
        Path(output_path) if output_path is not None else run_path / SOLUTION_OUTPUT
    )
    timing = raw_output.get("timing", {})
    status = raw_output.get("status", "failed")
    attempted = harness_attempted(status)
    completed = status == "completed"
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
                "energy": raw_output.get("energy") if completed else None,
                "energy_units": "Hartree",
                "energy_uncertainty": raw_output.get("energy_uncertainty", 0.0),
                "run_time": {
                    "overall_time": {
                        "wall_clock_start_time": timing.get(
                            "wall_clock_start_time"
                        ),
                        "wall_clock_stop_time": timing.get("wall_clock_stop_time"),
                        "seconds": float(timing.get("seconds", 0.0)),
                    },
                    "preprocessing_time": {"seconds": 0.0},
                    "algorithm_run_time": {
                        "wall_clock_start_time": timing.get(
                            "wall_clock_start_time"
                        ),
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
                    "trimci_details": raw_output.get("details", {}),
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
                "name": "TrimCI default three-phase selected-CI workflow",
                "solver_config": manifest.config,
                "harness_adapter": manifest.adapter,
                "harness_adapter_version": manifest.adapter_version,
            },
            "software_details": raw_output.get("software", {}),
        },
        "digital_signature": None,
    }
    write_validated_solution(
        output_path, solution, schema_dir=schema_dir or default_schema_dir()
    )
    checkpoint_solutions = _write_checkpoint_solutions(
        run_path,
        manifest,
        raw_output,
        solution,
        schema_dir=schema_dir or default_schema_dir(),
    )
    write_manifest(run_path, manifest.with_status("harvested"))
    write_json(
        run_path / "harvest_summary.json",
        {
            "solution_file": str(output_path),
            "checkpoint_solution_files": checkpoint_solutions,
            "status": status,
        },
    )
    return solution


def smoke_test(run_dir: str | Path | None = None) -> dict[str, Any]:
    """Run and harvest TrimCI defaults on validation H2/cc-pVDZ."""
    if run_dir is None:
        raise ValueError("TrimCI smoke_test requires a persistent run_dir")
    root = repo_root()
    problem = (
        root
        / "problem_instances"
        / "validation_instances"
        / "problem_instance.validation.H2.cc-PVDZ."
        "9162371c-b23f-45a6-bacd-44cb7aaea917.json"
    )
    fcidump = (
        root
        / "scripts"
        / "development"
        / "validation.H2.cc-PVDZ."
        "bbcd09f2-8a89-4f35-9577-7851a76ea17c.fcidump.gz"
    )
    prepare(
        problem,
        "f847059f-a89f-4008-9ae1-39847c899e75",
        fcidump,
        run_dir,
        overwrite=True,
    )
    run(run_dir)
    solution = harvest(run_dir)
    energy = solution["solution_data"][0]["energy"]
    if energy is None or not (-1.18 < float(energy) < -1.12):
        raise AssertionError(f"TrimCI H2 smoke energy is not sane: {energy}")
    return solution


def _import_trimci():
    try:
        return importlib.import_module("trimci")
    except ImportError as exc:
        raise TrimCIUnavailableError(
            "TrimCI is optional; install qb-gsee-benchmark[trimci]"
        ) from exc


def _trimci_git_revision(trimci: Any) -> str | None:
    candidates = list(Path(trimci.__file__).resolve().parents)
    try:
        direct_url = importlib.metadata.distribution("trimci").read_text(
            "direct_url.json"
        )
        if direct_url:
            url = json.loads(direct_url).get("url", "")
            parsed = urlparse(url)
            if parsed.scheme == "file":
                candidates.insert(0, Path(unquote(parsed.path)).resolve())
    except (importlib.metadata.PackageNotFoundError, json.JSONDecodeError):
        pass
    for candidate in candidates:
        if not (candidate / ".git").exists():
            continue
        result = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    return None


def _validate_checkpoint_grid(values: Any) -> tuple[int, ...]:
    grid = tuple(int(value) for value in values)
    if any(value <= 0 for value in grid):
        raise ValueError("TrimCI checkpoint determinant budgets must be positive")
    if any(left >= right for left, right in zip(grid, grid[1:])):
        raise ValueError(
            "TrimCI checkpoint determinant budgets must be strictly increasing"
        )
    return grid


def _phase2_checkpoint_history(run_path: Path) -> list[dict[str, Any]]:
    """Return aligned Phase-2 checkpoint energies from TrimCI run artifacts."""

    work_dir = run_path / "trimci_work"
    results_path = work_dir / "result_results.json"
    if not results_path.is_file():
        return []
    results = read_json(results_path)
    checkpoint_module = importlib.import_module("trimci.checkpoint")
    phase1 = sorted(
        checkpoint_module.list_checkpoints(work_dir / "checkpoints" / "phase1"),
        key=lambda item: int(item["round"]),
    )
    phase2 = sorted(
        checkpoint_module.list_checkpoints(work_dir / "checkpoints" / "phase2"),
        key=lambda item: int(item["round"]),
    )
    ndets_history = list(results.get("ndets_history", []))
    energy_history = list(results.get("energy_history", []))
    pt2_history = list(results.get("pt2_history", []))
    total_rounds = len(phase1) + len(phase2)
    if not (
        len(ndets_history) == len(energy_history) == len(pt2_history) == total_rounds
    ):
        raise RuntimeError(
            "TrimCI expansion histories do not align with Phase-1/2 checkpoints"
        )
    e_nuc = float(results.get("e_nuc", 0.0))
    records = []
    offset = len(phase1)
    for checkpoint_index, metadata in enumerate(phase2):
        history_index = offset + checkpoint_index
        n_dets = int(metadata["n_dets"])
        electronic_energy = float(metadata["energy"])
        if n_dets != int(ndets_history[history_index]) or not math.isclose(
            electronic_energy,
            float(energy_history[history_index]),
            rel_tol=0.0,
            abs_tol=1e-10,
        ):
            raise RuntimeError(
                "TrimCI Phase-2 checkpoint metadata disagrees with result history"
            )
        pt2 = float(pt2_history[history_index])
        variational = electronic_energy + e_nuc
        correction = pt2 if abs(pt2) > 0.0 else None
        records.append(
            {
                "phase": "phase2",
                "checkpoint_index": checkpoint_index,
                "checkpoint_round": int(metadata["round"]),
                "history_index": history_index,
                "n_dets": n_dets,
                "variational_energy": variational,
                "pt2_correction": correction,
                "selected_energy": variational + (correction or 0.0),
                "checkpoint_file": os.path.relpath(metadata["path"], run_path),
            }
        )
    return records


def _select_phase2_checkpoints(
    records: list[dict[str, Any]],
    grid: tuple[int, ...],
    n_fci: int | None,
) -> list[dict[str, Any]]:
    """Select the last completed Phase-2 state at or below each resource cap."""

    selected = []
    for target in _validate_checkpoint_grid(grid):
        if n_fci is not None and target > n_fci:
            continue
        candidates = [record for record in records if int(record["n_dets"]) <= target]
        if not candidates:
            continue
        record = max(
            candidates,
            key=lambda item: (int(item["n_dets"]), int(item["checkpoint_index"])),
        )
        selected.append({**record, "target_n_dets": target})
    return selected


def _checkpoint_solver_uuid(target_n_dets: int) -> str:
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"qb-gsee-benchmark:solver:trimci-ndet-{target_n_dets}:v1",
        )
    )


def _write_checkpoint_solutions(
    run_path: Path,
    manifest: RunManifest,
    raw_output: dict[str, Any],
    base_solution: dict[str, Any],
    schema_dir: str | Path,
) -> list[str]:
    grid = _validate_checkpoint_grid(manifest.config.get("checkpoint_ndet_grid", ()))
    if not grid or raw_output.get("status") != "completed":
        return []
    result = raw_output.get("details", {}).get("result", {})
    records = list(result.get("phase2_checkpoints", []))
    if not records:
        raise RuntimeError(
            "TrimCI checkpoint grid was requested but no Phase-2 checkpoints "
            "were recorded"
        )
    n_fci_value = result.get("n_fci")
    n_fci = int(n_fci_value) if n_fci_value is not None else None
    selected = _select_phase2_checkpoints(records, grid, n_fci)
    output_dir = run_path / "checkpoint_solutions"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for checkpoint in selected:
        target = int(checkpoint["target_n_dets"])
        solver_short_name = f"TrimCI_ndet_{target}"
        solution = copy.deepcopy(base_solution)
        solution["solution_uuid"] = str(uuid.uuid4())
        solution["creation_timestamp"] = iso8601_timestamp()
        row = solution["solution_data"][0]
        row["energy"] = float(checkpoint["selected_energy"])
        row["solution_details"]["trimci_checkpoint"] = {
            **checkpoint,
            "selection_rule": "last completed Phase-2 state with n_dets <= target",
            "shared_parent_run_id": manifest.run_id,
            "runtime_not_separately_measured": True,
        }
        solver = solution["solver_details"]
        solver["solver_uuid"] = _checkpoint_solver_uuid(target)
        solver["solver_short_name"] = solver_short_name
        algorithm = solver["algorithm_details"]
        algorithm["name"] = "TrimCI Phase-2 determinant-budget checkpoint"
        algorithm["solver_config"] = {
            **manifest.config,
            "checkpoint_target_n_dets": target,
            "checkpoint_actual_n_dets": int(checkpoint["n_dets"]),
            "checkpoint_index": int(checkpoint["checkpoint_index"]),
            "checkpoint_selection_rule": (
                "last completed Phase-2 state with n_dets <= target"
            ),
            "shared_parent_solver_uuid": manifest.solver_uuid,
            "shared_parent_run_id": manifest.run_id,
        }
        path = output_dir / f"solution.{solver_short_name}.{manifest.task_uuid}.json"
        write_validated_solution(path, solution, schema_dir=schema_dir)
        outputs.append(os.path.relpath(path, run_path))
    return outputs


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
    elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    harness_attempted(status)
    message = reason or "run did not produce raw_output.json"
    timestamp = iso8601_timestamp()
    return {
        "adapter": manifest.adapter,
        "adapter_version": manifest.adapter_version,
        "run_id": manifest.run_id,
        "status": status,
        "energy": None,
        "energy_units": "Hartree",
        "energy_uncertainty": 0.0,
        "error_message": message,
        "details": {"not_attempted_reason": message},
        "timing": {
            "wall_clock_start_time": timestamp,
            "wall_clock_stop_time": timestamp,
            "seconds": float(elapsed_seconds or 0.0),
        },
        "software": {
            "trimci": None,
            "trimci_repository": TRIMCI_REPOSITORY,
            "trimci_license": TRIMCI_LICENSE,
            "python_version": platform.python_version(),
        },
    }
