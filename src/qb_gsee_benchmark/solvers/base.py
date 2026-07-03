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

"""Scheduler-agnostic solver harness contract.

Adapters in :mod:`qb_gsee_benchmark.solvers` communicate with any execution
backend through a self-contained run directory. The repo layer writes inputs,
``run.sh``, and ``run_manifest.json``. Site layers such as PBS or Slurm only
execute the entrypoint and later call harvest; they should never inspect
adapter-private files or import site-specific code into this package.
"""

from __future__ import annotations

import json
import os
import stat
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.utils import iso8601_timestamp
from qb_gsee_benchmark.utils import validate_json

RUN_MANIFEST = "run_manifest.json"
RAW_OUTPUT = "raw_output.json"
SOLUTION_OUTPUT = "solution.json"


@dataclass(frozen=True)
class SolverResources:
    """Scheduler-neutral resource request for one run directory."""

    cores: int = 1
    memory_gb: float = 4.0
    gpus: int = 0
    walltime_seconds: int = 3600
    hardware_tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "cores": self.cores,
            "memory_gb": self.memory_gb,
            "gpus": self.gpus,
            "walltime_seconds": self.walltime_seconds,
            "hardware_tags": list(self.hardware_tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SolverResources":
        return cls(
            cores=int(data.get("cores", 1)),
            memory_gb=float(data.get("memory_gb", 4.0)),
            gpus=int(data.get("gpus", 0)),
            walltime_seconds=int(data.get("walltime_seconds", 3600)),
            hardware_tags=tuple(data.get("hardware_tags", ())),
        )


@dataclass(frozen=True)
class RunManifest:
    """Machine-readable description of a prepared solver run."""

    adapter: str
    adapter_version: str
    run_id: str
    problem_instance_uuid: str
    task_uuid: str
    solver_uuid: str
    solver_short_name: str
    resources: SolverResources
    entrypoint: str = "run.sh"
    status: str = "prepared"
    config: dict[str, Any] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=iso8601_timestamp)
    updated_at: str = field(default_factory=iso8601_timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter": self.adapter,
            "adapter_version": self.adapter_version,
            "run_id": self.run_id,
            "problem_instance_uuid": self.problem_instance_uuid,
            "task_uuid": self.task_uuid,
            "solver_uuid": self.solver_uuid,
            "solver_short_name": self.solver_short_name,
            "resources": self.resources.to_dict(),
            "entrypoint": self.entrypoint,
            "status": self.status,
            "config": self.config,
            "files": self.files,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunManifest":
        return cls(
            adapter=str(data["adapter"]),
            adapter_version=str(data["adapter_version"]),
            run_id=str(data["run_id"]),
            problem_instance_uuid=str(data["problem_instance_uuid"]),
            task_uuid=str(data["task_uuid"]),
            solver_uuid=str(data["solver_uuid"]),
            solver_short_name=str(data["solver_short_name"]),
            resources=SolverResources.from_dict(data["resources"]),
            entrypoint=str(data.get("entrypoint", "run.sh")),
            status=str(data.get("status", "prepared")),
            config=dict(data.get("config", {})),
            files=dict(data.get("files", {})),
            created_at=str(data.get("created_at", iso8601_timestamp())),
            updated_at=str(data.get("updated_at", iso8601_timestamp())),
        )

    def with_status(self, status: str) -> "RunManifest":
        return RunManifest(
            adapter=self.adapter,
            adapter_version=self.adapter_version,
            run_id=self.run_id,
            problem_instance_uuid=self.problem_instance_uuid,
            task_uuid=self.task_uuid,
            solver_uuid=self.solver_uuid,
            solver_short_name=self.solver_short_name,
            resources=self.resources,
            entrypoint=self.entrypoint,
            status=status,
            config=self.config,
            files=self.files,
            created_at=self.created_at,
            updated_at=iso8601_timestamp(),
        )


def new_run_id() -> str:
    return str(uuid.uuid4())


def read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r") as handle:
        return json.load(handle)


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_manifest(run_dir: str | Path) -> RunManifest:
    return RunManifest.from_dict(read_json(Path(run_dir) / RUN_MANIFEST))


def write_manifest(run_dir: str | Path, manifest: RunManifest) -> None:
    write_json(Path(run_dir) / RUN_MANIFEST, manifest.to_dict())


def write_executable(path: str | Path, text: str) -> None:
    target = Path(path)
    target.write_text(text)
    current_mode = target.stat().st_mode
    target.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def load_problem_instance_task(
    problem_instance_path: str | Path,
    task_uuid: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    problem_instance = read_json(problem_instance_path)
    for task in problem_instance.get("tasks", []):
        if task.get("task_uuid") == task_uuid:
            return problem_instance, task
    raise ValueError(
        f"Task {task_uuid} was not found in {problem_instance_path}."
    )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_schema_dir() -> Path:
    return repo_root() / "schemas"


def validate_solution_payload(
    solution: dict[str, Any],
    schema_dir: str | Path | None = None,
) -> None:
    schema_root = Path(schema_dir) if schema_dir is not None else default_schema_dir()
    schema = read_json(schema_root / "solution.schema.0.0.1.json")
    validate_json(
        json_dict=solution,
        schema=schema,
        local_resolver_directory=str(schema_root),
    )


def write_validated_solution(
    output_path: str | Path,
    solution: dict[str, Any],
    schema_dir: str | Path | None = None,
) -> None:
    validate_solution_payload(solution, schema_dir=schema_dir)
    write_json(output_path, solution)


def relative_to_run_dir(run_dir: str | Path, path: str | Path) -> str:
    return os.path.relpath(Path(path), start=Path(run_dir))

