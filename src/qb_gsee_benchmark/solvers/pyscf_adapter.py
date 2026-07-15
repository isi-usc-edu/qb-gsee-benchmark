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

"""Reference PySCF adapter for the solver harness.

This adapter proves the H1 run-directory contract on local validation
instances. It implements the benchmark's existing PySCF suite shape
(``HF``, ``MP2``, ``CISD``, ``CCSD``, and ``CCSD(T)``) plus direct ``FCI`` for
schema-valid validation smoke tests. The site layer only executes ``run.sh`` and
later calls ``harvest()``; no PBS or cluster-specific state belongs here.
"""

from __future__ import annotations

import gzip
import platform
import shutil
import tempfile
import time
import traceback
import uuid
from dataclasses import dataclass

import numpy as np
from pathlib import Path
from typing import Any

import pyscf
from pyscf import cc
from pyscf import ci
from pyscf import fci
from pyscf import gto
from pyscf import lib
from pyscf import mp
from pyscf import scf

from qb_gsee_benchmark.solvers.base import RAW_OUTPUT
from qb_gsee_benchmark.solvers.base import RUN_MANIFEST
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
from qb_gsee_benchmark.utils import read_fcidump

ADAPTER_NAME = "pyscf_reference"
ADAPTER_VERSION = "0.4.2"
LEGACY_METHOD_CAMPAIGN = "pyscf_methods_2026-07"
G48_METHOD_CAMPAIGN = "g48_pyscf_clean_slate_2026-07_v1"

SOLVER_UUIDS = {
    "HF": "5f5e617a-19c2-4d82-bebc-b2d6b3dcb012",
    "MP2": "b420358b-5def-41e6-8c5d-b9d93b6aecd2",
    "CISD": "418f060e-496b-4024-8d2d-9b1f8791e76d",
    "CCSD": "0a29e54f-bef9-4d19-bafa-d94b1c4b37aa",
    "CCSD(T)": "c09217e6-d0f7-4b0f-81c4-79210b7ac878",
    "FCI": str(uuid.uuid5(uuid.NAMESPACE_URL, "qb-gsee-benchmark:pyscf:fci:v1")),
}

METHOD_ADAPTERS = {
    "pyscf_hf": "HF",
    "pyscf_mp2": "MP2",
    "pyscf_cisd": "CISD",
    "pyscf_ccsd": "CCSD",
    "pyscf_ccsd_t": "CCSD(T)",
}
METHOD_ADAPTER_NAMES = {method: adapter for adapter, method in METHOD_ADAPTERS.items()}
ADAPTER_NAMES = frozenset({ADAPTER_NAME, *METHOD_ADAPTERS})


class _PySCFStageError(RuntimeError):
    """Carry convergence provenance when a PySCF stage raises."""

    def __init__(self, message: str, details: dict[str, Any]):
        super().__init__(message)
        self.details = details


@dataclass(frozen=True)
class PySCFConfig:
    method: str = "FCI"
    num_threads: int = 1
    energy_units: str = "Hartree"
    campaign: str | None = None
    solver_uuid: str | None = None
    solver_short_name: str | None = None

    def normalized_method(self) -> str:
        return self.method.strip().upper()

    def to_dict(self) -> dict[str, Any]:
        method = self.normalized_method()
        if method not in SOLVER_UUIDS:
            raise ValueError(f"Unsupported PySCF harness method: {method}")
        return {
            "method": method,
            "num_threads": self.num_threads,
            "energy_units": self.energy_units,
            "campaign": self.campaign,
            "solver_uuid": self.solver_uuid or SOLVER_UUIDS[method],
            "solver_short_name": self.solver_short_name or method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PySCFConfig":
        return cls(
            method=str(data.get("method", "FCI")),
            num_threads=int(data.get("num_threads", 1)),
            energy_units=str(data.get("energy_units", "Hartree")),
            campaign=data.get("campaign"),
            solver_uuid=data.get("solver_uuid"),
            solver_short_name=data.get("solver_short_name"),
        )


def prepare(
    problem_instance_path: str | Path,
    task_uuid: str,
    fcidump_path: str | Path,
    run_dir: str | Path,
    config: PySCFConfig | None = None,
    resources: SolverResources | None = None,
    overwrite: bool = False,
) -> RunManifest:
    """Create a self-contained PySCF run directory."""

    return _prepare(
        problem_instance_path=problem_instance_path,
        task_uuid=task_uuid,
        fcidump_path=fcidump_path,
        run_dir=run_dir,
        config=config or PySCFConfig(),
        resources=resources,
        overwrite=overwrite,
        adapter_name=ADAPTER_NAME,
    )


def prepare_method(
    method: str,
    problem_instance_path: str | Path,
    task_uuid: str,
    fcidump_path: str | Path,
    run_dir: str | Path,
    campaign: str,
    num_threads: int = 1,
    resources: SolverResources | None = None,
    overwrite: bool = False,
) -> RunManifest:
    """Prepare one fixed-identity PySCF method adapter for the reviewed G-48 campaign."""

    normalized_method = method.strip().upper()
    try:
        adapter_name = METHOD_ADAPTER_NAMES[normalized_method]
    except KeyError as exc:
        allowed = ", ".join(METHOD_ADAPTER_NAMES)
        raise ValueError(
            f"Unsupported PySCF method adapter {normalized_method!r}; choose {allowed}."
        ) from exc
    _validate_method_campaign(campaign)
    return _prepare(
        problem_instance_path=problem_instance_path,
        task_uuid=task_uuid,
        fcidump_path=fcidump_path,
        run_dir=run_dir,
        config=PySCFConfig(
            method=normalized_method,
            num_threads=num_threads,
            campaign=campaign,
        ),
        resources=resources,
        overwrite=overwrite,
        adapter_name=adapter_name,
    )


def _prepare(
    problem_instance_path: str | Path,
    task_uuid: str,
    fcidump_path: str | Path,
    run_dir: str | Path,
    config: PySCFConfig,
    resources: SolverResources | None,
    overwrite: bool,
    adapter_name: str,
) -> RunManifest:
    """Shared run-directory preparation for reference and method adapters."""

    config_dict = config.to_dict()
    method = config.normalized_method()
    if method not in SOLVER_UUIDS:
        raise ValueError(f"Unsupported PySCF harness method: {method}")

    run_path = Path(run_dir)
    if run_path.exists() and any(run_path.iterdir()) and not overwrite:
        raise FileExistsError(f"{run_path} is not empty; pass overwrite=True.")
    run_path.mkdir(parents=True, exist_ok=True)

    problem_instance, task = load_problem_instance_task(
        problem_instance_path, task_uuid
    )
    input_fcidump = run_path / "input.fcidump"
    _materialize_fcidump(fcidump_path, input_fcidump)

    problem_copy = run_path / "problem_instance.json"
    task_copy = run_path / "task.json"
    config_copy = run_path / "solver_config.json"
    write_json(problem_copy, problem_instance)
    write_json(task_copy, task)
    write_json(config_copy, config_dict)

    entrypoint = "run.sh"
    write_executable(
        run_path / entrypoint,
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'cd "$(dirname "$0")"\n'
        'python -m qb_gsee_benchmark.solvers.cli run --run-dir "$PWD"\n',
    )

    manifest = RunManifest(
        adapter=adapter_name,
        adapter_version=ADAPTER_VERSION,
        run_id=new_run_id(),
        problem_instance_uuid=problem_instance["problem_instance_uuid"],
        task_uuid=task_uuid,
        solver_uuid=config_dict["solver_uuid"],
        solver_short_name=config_dict["solver_short_name"],
        resources=resources
        or SolverResources(
            cores=max(1, int(config_dict["num_threads"])),
            memory_gb=4.0,
            gpus=0,
            walltime_seconds=1800,
        ),
        entrypoint=entrypoint,
        config=config_dict,
        files={
            "problem_instance": problem_copy.name,
            "task": task_copy.name,
            "fcidump": input_fcidump.name,
            "config": config_copy.name,
            "raw_output": RAW_OUTPUT,
            "solution": SOLUTION_OUTPUT,
        },
    )
    write_manifest(run_path, manifest)
    return manifest


def run(run_dir: str | Path) -> dict[str, Any]:
    """Execute the prepared PySCF run directory and write ``raw_output.json``."""

    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    config = PySCFConfig.from_dict(manifest.config)
    _validate_adapter_identity(manifest, config)
    start = time.time()
    start_iso = iso8601_timestamp()
    status = "completed"
    error_message = None
    energy = None
    details: dict[str, Any] = {}

    try:
        lib.num_threads(max(1, int(config.num_threads)))
        energy, details = _compute_energy(
            method=config.normalized_method(),
            fcidump_path=run_path / manifest.files["fcidump"],
            legacy_open_shell_uhf=manifest.adapter in METHOD_ADAPTERS,
        )
        nonconverged_stages = _nonconverged_stages(config.normalized_method(), details)
        if not np.isfinite(float(energy)):
            details["failure_stage"] = config.normalized_method()
            details["failure_classification"] = "non_finite_scored_energy"
            details["non_finite_energy_repr"] = repr(float(energy))
            error_message = (
                f"PySCF {config.normalized_method()} produced a non-finite scored energy"
            )
            status = "failed"
            energy = None
        elif nonconverged_stages:
            details["diagnostic_energy_hartree"] = energy
            details["nonconverged_stages"] = nonconverged_stages
            error_message = "PySCF did not converge at default settings: " + ", ".join(
                nonconverged_stages
            )
            status = "failed"
            energy = None
    except _PySCFStageError as exc:
        status = "failed"
        error_message = str(exc)
        details = dict(exc.details)
        details["traceback"] = traceback.format_exc()
    except Exception as exc:
        status = "failed"
        error_message = str(exc)
        details = {
            "failure_stage": "unresolved",
            "convergence_metadata_status": "unavailable_before_stage_return",
            "traceback": traceback.format_exc(),
        }
        if config.normalized_method() != "FCI":
            details["hf_converged"] = None
        if config.normalized_method() not in {"FCI", "HF"}:
            details["converged"] = None

    stop = time.time()
    raw_output = {
        "adapter": manifest.adapter,
        "adapter_version": manifest.adapter_version,
        "run_id": manifest.run_id,
        "status": status,
        "method": config.normalized_method(),
        "energy": energy,
        "energy_units": config.energy_units,
        "error_message": error_message,
        "details": details,
        "timing": {
            "wall_clock_start_time": start_iso,
            "wall_clock_stop_time": iso8601_timestamp(),
            "seconds": stop - start,
        },
        "software": {
            "pyscf_version": pyscf.__version__,
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
    missing_output_elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    """Convert raw output to a schema-valid benchmark solution JSON."""

    run_path = Path(run_dir)
    manifest = load_manifest(run_path)
    config = PySCFConfig.from_dict(manifest.config)
    _validate_adapter_identity(manifest, config)
    problem_instance = read_json(run_path / manifest.files["problem_instance"])
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
    energy = raw_output.get("energy") if completed else None

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
                    "not_attempted_reason": (
                        None
                        if completed
                        else raw_output.get("error_message", "run did not complete")
                    ),
                    "run_directory_id": manifest.run_id,
                    "raw_output_file": manifest.files["raw_output"],
                    "pyscf_details": raw_output.get("details", {}),
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
                "name": f"PySCF {config.normalized_method()}",
                "solver_config": manifest.config,
                "harness_adapter": manifest.adapter,
                "harness_adapter_version": manifest.adapter_version,
            },
            "software_details": {
                "pyscf": raw_output.get("software", {}).get("pyscf_version"),
                "python": raw_output.get("software", {}).get("python_version"),
            },
        },
        "digital_signature": None,
    }
    write_validated_solution(
        output_path,
        solution,
        schema_dir=schema_dir or default_schema_dir(),
    )
    write_manifest(run_path, manifest.with_status("harvested"))

    # Keep a small proof target in the run directory for status tools.
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
    """Run H2/cc-pVDZ direct FCI and assert the validation reference energy."""

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
    problem_instance, task = load_problem_instance_task(
        problem_instance_path,
        "f847059f-a89f-4008-9ae1-39847c899e75",
    )
    prepare(
        problem_instance_path=problem_instance_path,
        task_uuid=task["task_uuid"],
        fcidump_path=fcidump_path,
        run_dir=run_dir,
        config=PySCFConfig(method="FCI", num_threads=1),
        overwrite=True,
    )
    run(run_dir)
    solution = harvest(run_dir)
    energy = solution["solution_data"][0]["energy"]
    reference = task["requirements"]["reference_energy"]
    tolerance = min(task["requirements"]["absolute_accuracy_threshold"], 1.0e-10)
    if abs(energy - reference) > tolerance:
        raise AssertionError(
            f"PySCF FCI smoke energy {energy} did not match {reference}."
        )
    if cleanup is not None:
        cleanup.cleanup()
    return solution


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
        "method": manifest.config.get("method"),
        "energy": None,
        "energy_units": manifest.config.get("energy_units", "Hartree"),
        "error_message": message,
        "details": {"not_attempted_reason": message},
        "timing": {
            "wall_clock_start_time": timestamp,
            "wall_clock_stop_time": timestamp,
            "seconds": float(elapsed_seconds or 0.0),
        },
        "software": {
            "pyscf_version": pyscf.__version__,
            "python_version": platform.python_version(),
        },
    }


def _raise_stage_error(
    exc: Exception,
    details: dict[str, Any],
    stage: str,
    solver: Any | None = None,
) -> None:
    payload = dict(details)
    payload["failure_stage"] = stage
    payload["convergence_metadata_status"] = "partial"
    if solver is not None:
        payload["converged"] = _optional_bool(getattr(solver, "converged", None))
    raise _PySCFStageError(str(exc), payload) from exc


def _compute_energy(
    method: str,
    fcidump_path: str | Path,
    legacy_open_shell_uhf: bool = False,
) -> tuple[float, dict[str, Any]]:
    if method == "FCI":
        data = read_fcidump(str(fcidump_path))
        energy, _ci = fci.direct_spin1.kernel(
            data["H1"],
            data["H2"],
            data["NORB"],
            data["NELEC"],
            ecore=data.get("ECORE", 0.0),
        )
        return float(energy), {
            "norb": int(data["NORB"]),
            "nelec": data["NELEC"],
            "method_note": "direct_spin1 FCI from FCIDUMP integrals",
        }

    if method == "HF":
        mf, details = _run_hf(fcidump_path, legacy_open_shell_uhf=legacy_open_shell_uhf)
        details["method_note"] = (
            "SCF object reconstructed from symmetrized FCIDUMP integrals"
        )
        return float(mf.e_tot), details

    if method == "MP2":
        mf, details = _run_hf(fcidump_path, legacy_open_shell_uhf=legacy_open_shell_uhf)
        solver = mp.MP2(mf)
        solver.verbose = 0
        details["method_note"] = "PySCF MP2 on the FCIDUMP-reconstructed SCF object"
        try:
            correlation_energy, _t2 = solver.kernel()
        except Exception as exc:
            _raise_stage_error(exc, details, "MP2", solver)
        details.update(
            {
                "correlation_energy": float(correlation_energy),
                "converged": _optional_bool(getattr(solver, "converged", None)),
            }
        )
        return float(solver.e_tot), details

    if method == "CISD":
        mf, details = _run_hf(fcidump_path, legacy_open_shell_uhf=legacy_open_shell_uhf)
        solver = ci.CISD(mf)
        solver.verbose = 0
        details["method_note"] = "PySCF CISD on the FCIDUMP-reconstructed SCF object"
        try:
            correlation_energy, _civec = solver.kernel()
        except Exception as exc:
            _raise_stage_error(exc, details, "CISD", solver)
        details.update(
            {
                "correlation_energy": float(correlation_energy),
                "converged": _optional_bool(getattr(solver, "converged", None)),
            }
        )
        return float(solver.e_tot), details

    if method in {"CCSD", "CCSD(T)"}:
        mf, details = _run_hf(fcidump_path, legacy_open_shell_uhf=legacy_open_shell_uhf)
        solver = cc.CCSD(mf)
        solver.verbose = 0
        details["method_note"] = (
            f"PySCF {method} on the FCIDUMP-reconstructed SCF object"
        )
        try:
            correlation_energy, _t1, _t2 = solver.kernel()
        except Exception as exc:
            _raise_stage_error(exc, details, "CCSD", solver)
        details.update(
            {
                "correlation_energy": float(correlation_energy),
                "converged": _optional_bool(getattr(solver, "converged", None)),
            }
        )
        triples_correction = 0.0
        if method == "CCSD(T)":
            try:
                triples_correction = float(solver.ccsd_t())
            except Exception as exc:
                _raise_stage_error(exc, details, "CCSD(T)", solver)
        details["triples_correction"] = triples_correction
        return float(mf.e_tot + solver.e_corr + triples_correction), details

    raise ValueError(f"Unsupported PySCF harness method: {method}")


def _run_hf(
    fcidump_path: str | Path,
    legacy_open_shell_uhf: bool = False,
) -> tuple[Any, dict[str, Any]]:
    data = read_fcidump(str(fcidump_path))
    norb = int(data["NORB"])
    mol = gto.M()
    mol.nelectron = int(data["NELEC"])
    mol.spin = int(data.get("MS2", 0))
    mol.nao = norb
    mol.incore_anyway = True
    ecore = float(data.get("ECORE", 0.0))
    mol.energy_nuc = lambda *args: ecore

    if legacy_open_shell_uhf and mol.spin > 0:
        mf = scf.UHF(mol)
        hcore = np.asarray((data["H1"], data["H1"]))
    else:
        mf = scf.RHF(mol)
        hcore = data["H1"]
    mf.verbose = 0
    mf.get_hcore = lambda *args: hcore
    mf.get_ovlp = lambda *args: np.eye(norb)
    mf._eri = data["H2"]
    mf.kernel()
    return mf, {
        "hf_energy": float(mf.e_tot),
        "hf_converged": bool(mf.converged),
        "hf_reference": "UHF" if isinstance(mf, scf.uhf.UHF) else "RHF",
        "h1_symmetrized_on_read": True,
    }


def _nonconverged_stages(method: str, details: dict[str, Any]) -> list[str]:
    stages = []
    if details.get("hf_converged") is False:
        stages.append("HF")
    if method != "HF" and details.get("converged") is False:
        stages.append(method)
    return stages


def _validate_method_campaign(campaign: str | None) -> None:
    if campaign != G48_METHOD_CAMPAIGN:
        raise ValueError(
            f"Unsupported PySCF method campaign {campaign!r}; "
            f"expected reviewed G-48 campaign {G48_METHOD_CAMPAIGN!r}."
        )


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _validate_adapter_identity(manifest: RunManifest, config: PySCFConfig) -> None:
    if manifest.adapter not in ADAPTER_NAMES:
        raise ValueError(f"Unsupported PySCF adapter identity {manifest.adapter!r}.")
    fixed_method = METHOD_ADAPTERS.get(manifest.adapter)
    if fixed_method is None:
        return
    _validate_method_campaign(config.campaign)
    expected = {
        "method": fixed_method,
        "solver_uuid": SOLVER_UUIDS[fixed_method],
        "solver_short_name": fixed_method,
    }
    actual = {
        "method": config.normalized_method(),
        "solver_uuid": manifest.solver_uuid,
        "solver_short_name": manifest.solver_short_name,
    }
    if actual != expected:
        raise ValueError(
            f"Adapter {manifest.adapter!r} identity mismatch: "
            f"expected {expected!r}, got {actual!r}."
        )
