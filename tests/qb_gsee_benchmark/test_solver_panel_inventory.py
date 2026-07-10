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
            "solution_data": [
                {
                    "task_uuid": task_uuid,
                    "energy": -1.0,
                    "solution_details": {"attempted": True},
                }
            ],
        },
    )
    write_json(
        tmp_path / "solution_files" / "ipie" / "solution.json",
        {
            "solver_details": {
                "solver_uuid": inventory_module.DEFAULT_SOLVERS["ipie_uhf_trial"][
                    "solver_uuid"
                ]
            },
            "solution_data": [
                {
                    "task_uuid": task_uuid,
                    "energy": None,
                    "solution_details": {"attempted": False},
                }
            ],
        },
    )

    inventory = inventory_module.build_inventory(tmp_path)

    assert inventory["public_task_count"] == 1
    assert inventory["summary"]["pyscf_fci"] == {
        "present": 1,
        "attempted": 1,
        "not_attempted": 0,
        "legacy_present": 0,
        "missing": 0,
    }
    assert inventory["summary"]["ipie_uhf_trial"] == {
        "present": 1,
        "attempted": 0,
        "not_attempted": 1,
        "legacy_present": 0,
        "missing": 0,
    }
    assert inventory["summary"]["shci_opt"] == {
        "present": 0,
        "attempted": 0,
        "not_attempted": 0,
        "legacy_present": 0,
        "missing": 1,
    }
    assert inventory["solution_json_parse_errors"] == []
    assert inventory["tranche2_estimate"] == {
        "basis": (
            "conservative scheduling upper bound: every currently missing "
            "solver-task pair consumes its frozen site wall cap"
        ),
        "available_solver_full_cap_node_hours": 23,
        "campaign_budget_node_hours": 300,
        "exceeds_campaign_budget": False,
        "solvers": {
            "pyscf_fci": {
                "remaining_gap_count": 0,
                "tasks_per_node": 32,
                "wall_cap_hours": 4,
                "full_cap_jobs": 0,
                "full_cap_node_hours": 0,
                "availability": "available",
            },
            "shci_opt": {
                "remaining_gap_count": 1,
                "tasks_per_node": 12,
                "wall_cap_hours": 11,
                "full_cap_jobs": 1,
                "full_cap_node_hours": 11,
                "availability": "available",
            },
            "dmrg_fixed_budget": {
                "remaining_gap_count": 1,
                "tasks_per_node": 1,
                "wall_cap_hours": 12,
                "full_cap_jobs": 1,
                "full_cap_node_hours": 12,
                "availability": "available",
            },
            "ipie_uhf_trial": {
                "remaining_gap_count": 0,
                "tasks_per_node": None,
                "wall_cap_hours": None,
                "full_cap_jobs": None,
                "full_cap_node_hours": None,
                "availability": "unavailable_no_gpu_nodes",
            },
        },
    }
    report = tmp_path / "coverage.md"
    inventory_module.write_markdown(report, inventory)
    rendered = report.read_text()
    assert "| `shci_opt` | 1 | 12 | 11 | 1 | 11 | `available` |" in rendered
    assert (
        "| `ipie_uhf_trial` | 0 | n/a | n/a | n/a | n/a | "
        "`unavailable_no_gpu_nodes` |"
    ) in rendered
    assert "Available-solver full-cap total: **23 node-hours**" in rendered
