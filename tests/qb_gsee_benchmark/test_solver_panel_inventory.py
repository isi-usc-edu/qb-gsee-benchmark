from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "solver_panel"
    / "build_coverage_inventory.py"
)
SPEC = importlib.util.spec_from_file_location("build_coverage_inventory", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
inventory_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory_module)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_inventory_excludes_validation_and_matches_default_solver_uuid(tmp_path: Path):
    task_uuid = "10000000-0000-0000-0000-000000000001"
    problem = {
        "problem_instance_uuid": "20000000-0000-0000-0000-000000000001",
        "short_name": "public_case",
        "tasks": [
            {
                "task_uuid": task_uuid,
                "features": {"num_orbitals": 4, "num_electrons": 2},
            }
        ],
    }
    write_json(tmp_path / "problem_instances" / "public" / "case.json", problem)
    write_json(
        tmp_path / "problem_instances" / "validation_instances" / "case.json",
        {**problem, "problem_instance_uuid": "excluded"},
    )
    write_json(
        tmp_path / "solution_files" / "pyscf" / "solution.json",
        {
            "solver_details": {
                "solver_uuid": inventory_module.DEFAULT_SOLVERS["pyscf_fci"][
                    "solver_uuid"
                ]
            },
            "solution_data": [{"task_uuid": task_uuid}],
        },
    )

    inventory = inventory_module.build_inventory(tmp_path)

    assert inventory["public_task_count"] == 1
    assert inventory["summary"]["pyscf_fci"] == {"present": 1, "missing": 0}
    assert inventory["summary"]["shci_opt"] == {"present": 0, "missing": 1}
    assert inventory["solution_json_parse_errors"] == []
