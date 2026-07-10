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

"""Batch preparation for scheduler-agnostic solver run directories."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.solvers import pyscf_adapter
from qb_gsee_benchmark.solvers import shci_adapter
from qb_gsee_benchmark.solvers.dmrg_block2 import adapter as dmrg_adapter
from qb_gsee_benchmark.solvers.ipie_afqmc import adapter as ipie_adapter
from qb_gsee_benchmark.solvers.trimci import adapter as trimci_adapter
from qb_gsee_benchmark.solvers.base import RunManifest
from qb_gsee_benchmark.solvers.base import SolverResources


DEFAULT_RUN_DIR_FILE = "run_dirs.txt"
BATCH_MANIFEST = "batch_manifest.json"


def prepare_batch(
    plan_path: str | Path,
    output_root: str | Path,
    *,
    run_dir_file: str | Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Prepare run directories from a CSV plan.

    Required CSV columns are ``adapter``, ``problem_instance``, ``task_uuid``,
    and ``fcidump``. ``run_name`` is optional; if omitted a stable directory name
    is derived from the adapter and task UUID. Paths in the plan are resolved
    relative to the plan file when that path exists, otherwise relative to
    the caller's current working directory. Extra columns are adapter config
    fields and are ignored when empty. Optional scheduler-neutral resource
    columns are ``cores``, ``memory_gb``, ``gpus``, ``walltime_seconds``, and
    comma-separated ``hardware_tags``.
    """

    plan = Path(plan_path).resolve()
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    rows = _read_plan(plan)
    prepared: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        adapter_name = _required(row, "adapter", index).strip().lower()
        problem_instance = _resolve_path(plan, _required(row, "problem_instance", index))
        fcidump = _resolve_path(plan, _required(row, "fcidump", index))
        task_uuid = _required(row, "task_uuid", index)
        run_name = row.get("run_name") or _default_run_name(adapter_name, task_uuid, index)
        run_dir = root / _slug(run_name)
        manifest = _prepare_one(
            adapter_name=adapter_name,
            row=row,
            problem_instance=problem_instance,
            task_uuid=task_uuid,
            fcidump=fcidump,
            run_dir=run_dir,
            resources=_resources(row),
            overwrite=overwrite,
        )
        prepared.append(
            {
                "index": index,
                "adapter": manifest.adapter,
                "solver_short_name": manifest.solver_short_name,
                "problem_instance_uuid": manifest.problem_instance_uuid,
                "task_uuid": manifest.task_uuid,
                "run_dir": str(run_dir),
                "run_id": manifest.run_id,
            }
        )

    run_dir_file_path = Path(run_dir_file).resolve() if run_dir_file else root / DEFAULT_RUN_DIR_FILE
    run_dir_file_path.parent.mkdir(parents=True, exist_ok=True)
    run_dir_file_path.write_text("\n".join(item["run_dir"] for item in prepared) + "\n")
    batch = {
        "plan_path": str(plan),
        "output_root": str(root),
        "run_dir_file": str(run_dir_file_path),
        "prepared_count": len(prepared),
        "runs": prepared,
    }
    (root / BATCH_MANIFEST).write_text(json.dumps(batch, indent=2, sort_keys=True) + "\n")
    return batch


def _prepare_one(
    *,
    adapter_name: str,
    row: dict[str, str],
    problem_instance: Path,
    task_uuid: str,
    fcidump: Path,
    run_dir: Path,
    resources: SolverResources | None,
    overwrite: bool,
) -> RunManifest:
    if adapter_name in {"pyscf", "pyscf_reference"}:
        return pyscf_adapter.prepare(
            problem_instance_path=problem_instance,
            task_uuid=task_uuid,
            fcidump_path=fcidump,
            run_dir=run_dir,
            config=pyscf_adapter.PySCFConfig(
                method=row.get("method") or "FCI",
                num_threads=_int(row.get("num_threads"), 1),
            ),
            resources=resources,
            overwrite=overwrite,
        )
    if adapter_name in {"shci", "shci_arrow"}:
        return shci_adapter.prepare(
            problem_instance_path=problem_instance,
            task_uuid=task_uuid,
            fcidump_path=fcidump,
            run_dir=run_dir,
            config=shci_adapter.SHCIConfig(
                variant=row.get("variant") or "SHCI_opt",
                num_threads=_int(row.get("num_threads"), 1),
                command_template=_none(row.get("command_template")),
                result_json=row.get("result_json") or "shci_result.json",
                eps_var=_float_or_none(row.get("eps_var")),
                eps_var_label=_none(row.get("eps_var_label")),
                pt_correction=_bool_or_none(row.get("pt_correction")),
                optimized_orbitals=_bool_or_none(row.get("optimized_orbitals")),
            ),
            resources=resources,
            overwrite=overwrite,
        )
    if adapter_name in {"trimci", "trimci_default"}:
        return trimci_adapter.prepare(
            problem_instance_path=problem_instance,
            task_uuid=task_uuid,
            fcidump_path=fcidump,
            run_dir=run_dir,
            config=trimci_adapter.TrimCIConfig(
                seed=_int(row.get("seed"), trimci_adapter.DEFAULT_SEED),
                num_threads=_int(row.get("num_threads"), 1),
            ),
            resources=resources,
            overwrite=overwrite,
        )
    if adapter_name in {"ipie", "ipie_afqmc"}:
        return ipie_adapter.prepare(
            problem_instance_path=problem_instance,
            task_uuid=task_uuid,
            fcidump_path=fcidump,
            run_dir=run_dir,
            config=ipie_adapter.IPIEConfig(
                variant=row.get("variant") or "ipie_uhf_trial",
                num_threads=_int(row.get("num_threads"), 1),
                num_walkers=_int(row.get("num_walkers"), 512),
                timestep=_float(row.get("timestep"), 0.005),
                num_steps_per_block=_int(row.get("num_steps_per_block"), 25),
                num_blocks=_int(row.get("num_blocks"), 1000),
                trial_wavefunction=_none(row.get("trial_wavefunction")),
                determinant_count=_int_or_none(row.get("determinant_count")),
                command_template=_none(row.get("command_template")),
                result_json=row.get("result_json") or "ipie_result.json",
                confidence_level=_float(row.get("confidence_level"), ipie_adapter.DEFAULT_CONFIDENCE_LEVEL),
                phaseless=_bool(row.get("phaseless"), True),
                random_seed=_int_or_none(row.get("random_seed")),
            ),
            resources=resources,
            overwrite=overwrite,
        )
    if adapter_name in {"dmrg", "dmrg_block2"}:
        return dmrg_adapter.prepare(
            problem_instance_path=problem_instance,
            task_uuid=task_uuid,
            fcidump_path=fcidump,
            run_dir=run_dir,
            config=dmrg_adapter.DMRGConfig(
                variant=row.get("variant") or "DMRG_fixed_budget",
                num_threads=_int(row.get("num_threads"), 40),
                max_bond_dimension=_int_or_none(row.get("max_bond_dimension")),
                bond_dimensions=_int_tuple(row.get("bond_dimensions")),
                truncation_cutoff=_float_or_none(row.get("truncation_cutoff")),
                orbital_reordering=_none(row.get("orbital_reordering")),
                extrapolation_model=_none(row.get("extrapolation_model")),
                command_template=_none(row.get("command_template")),
                result_json=row.get("result_json") or "dmrg_result.json",
            ),
            resources=resources,
            overwrite=overwrite,
        )
    raise ValueError(f"Unsupported batch adapter {adapter_name!r}")


def _resources(row: dict[str, str]) -> SolverResources | None:
    keys = {"cores", "memory_gb", "gpus", "walltime_seconds", "hardware_tags"}
    if not any(row.get(key) for key in keys):
        return None
    return SolverResources(
        cores=_int(row.get("cores"), 1),
        memory_gb=_float(row.get("memory_gb"), 4.0),
        gpus=_int(row.get("gpus"), 0),
        walltime_seconds=_int(row.get("walltime_seconds"), 3600),
        hardware_tags=tuple(
            part.strip() for part in (row.get("hardware_tags") or "").split(",") if part.strip()
        ),
    )


def _read_plan(plan: Path) -> list[dict[str, str]]:
    with plan.open(newline="") as handle:
        rows = [
            {key: value.strip() for key, value in row.items() if key is not None and value is not None}
            for row in csv.DictReader(handle)
        ]
    if not rows:
        raise ValueError(f"Batch plan {plan} has no rows.")
    return rows


def _required(row: dict[str, str], key: str, index: int) -> str:
    value = row.get(key, "").strip()
    if not value:
        raise ValueError(f"Batch row {index} is missing required column {key!r}.")
    return value


def _resolve_path(plan: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    plan_relative = (plan.parent / path).resolve()
    if plan_relative.exists():
        return plan_relative
    return (Path.cwd() / path).resolve()


def _default_run_name(adapter_name: str, task_uuid: str, index: int) -> str:
    return f"{index:04d}_{adapter_name}_{task_uuid[:8]}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return slug.strip("._") or "run"


def _none(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value


def _int(value: str | None, default: int) -> int:
    return default if value in (None, "") else int(value)


def _int_or_none(value: str | None) -> int | None:
    return None if value in (None, "") else int(value)


def _float(value: str | None, default: float) -> float:
    return default if value in (None, "") else float(value)


def _float_or_none(value: str | None) -> float | None:
    return None if value in (None, "") else float(value)


def _bool(value: str | None, default: bool) -> bool:
    parsed = _bool_or_none(value)
    return default if parsed is None else parsed


def _bool_or_none(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Expected boolean value, got {value!r}")


def _int_tuple(value: str | None) -> tuple[int, ...]:
    if value in (None, ""):
        return ()
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())
