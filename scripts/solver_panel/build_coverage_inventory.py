#!/usr/bin/env python3
"""Build the G-31 default-solver coverage inventory from committed JSON."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_SOLVERS = {
    "pyscf_fci": {
        "adapter": "pyscf_reference",
        "variant": "FCI",
        "solver_uuid": "99f002d5-3e19-5ea4-986e-5282d43a3c91",
    },
    "shci_opt": {
        "adapter": "shci_arrow",
        "variant": "SHCI_opt",
        "solver_uuid": "2dde727e-a881-44fa-aabf-bba6248e4baf",
    },
    "dmrg_fixed_budget": {
        "adapter": "dmrg_block2",
        "variant": "DMRG_fixed_budget",
        "solver_uuid": "16537433-9f4c-4eae-a65d-787dc3b35b59",
    },
    "ipie_uhf_trial": {
        "adapter": "ipie_afqmc",
        "variant": "ipie_uhf_trial",
        "solver_uuid": "54cf1eae-79a4-5ee5-9553-80f4f380882b",
    },
}


def read_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return json.load(handle)


def solution_outcome(result: dict[str, Any]) -> str:
    details = result.get("solution_details", {})
    if "attempted" in details:
        return "attempted" if details["attempted"] else "not_attempted"
    if result.get("energy") is not None:
        return "attempted"
    return "legacy_present"


def public_tasks(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted((repo_root / "problem_instances").glob("**/*.json")):
        if "validation_instances" in path.parts:
            continue
        problem = read_json(path)
        if "problem_instance_uuid" not in problem or not isinstance(
            problem.get("tasks"), list
        ):
            continue
        for task_index, task in enumerate(problem["tasks"]):
            task_uuid = str(task["task_uuid"])
            if task_uuid in seen:
                raise ValueError(f"duplicate public task UUID: {task_uuid}")
            seen.add(task_uuid)
            features = task.get("features", {})
            rows.append(
                {
                    "problem_path": str(path.relative_to(repo_root)),
                    "problem_short_name": problem.get("short_name", path.stem),
                    "problem_instance_uuid": problem["problem_instance_uuid"],
                    "task_index": task_index,
                    "task_uuid": task_uuid,
                    "curation_tier": task.get("curation_tier"),
                    "reference_provenance_grade": task.get(
                        "reference_provenance_grade"
                    ),
                    "num_orbitals": features.get("num_orbitals"),
                    "num_electrons": features.get("num_electrons"),
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["num_orbitals"] is None,
            row["num_orbitals"] or 0,
            row["num_electrons"] is None,
            row["num_electrons"] or 0,
            row["problem_short_name"],
            row["task_index"],
        ),
    )


def solution_index(
    repo_root: Path,
) -> tuple[dict[tuple[str, str], list[dict[str, str]]], list[str]]:
    solver_uuid_to_key = {
        details["solver_uuid"]: key for key, details in DEFAULT_SOLVERS.items()
    }
    matches: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    parse_errors: list[str] = []
    for path in sorted((repo_root / "solution_files").glob("**/*.json")):
        try:
            solution = read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            parse_errors.append(f"{path.relative_to(repo_root)}: {exc}")
            continue
        solver_uuid = solution.get("solver_details", {}).get("solver_uuid")
        solver_key = solver_uuid_to_key.get(solver_uuid)
        if solver_key is None:
            continue
        for result in solution.get("solution_data", []):
            task_uuid = result.get("task_uuid")
            if task_uuid:
                matches[(solver_key, str(task_uuid))].append(
                    {
                        "path": str(path.relative_to(repo_root)),
                        "outcome": solution_outcome(result),
                    }
                )
    return matches, parse_errors


def build_inventory(repo_root: Path) -> dict[str, Any]:
    tasks = public_tasks(repo_root)
    matches, parse_errors = solution_index(repo_root)
    rows = []
    for task in tasks:
        row = dict(task)
        for solver_key in DEFAULT_SOLVERS:
            records = matches.get((solver_key, task["task_uuid"]), [])
            paths = sorted(record["path"] for record in records)
            outcomes = {record["outcome"] for record in records}
            if not records:
                outcome = "missing"
            elif "attempted" in outcomes:
                outcome = "attempted"
            elif "not_attempted" in outcomes:
                outcome = "not_attempted"
            else:
                outcome = "legacy_present"
            row[f"{solver_key}_status"] = "present" if paths else "missing"
            row[f"{solver_key}_outcome"] = outcome
            row[f"{solver_key}_solution_paths"] = paths
        rows.append(row)
    summary = {
        key: {
            "present": sum(row[f"{key}_status"] == "present" for row in rows),
            "attempted": sum(row[f"{key}_outcome"] == "attempted" for row in rows),
            "not_attempted": sum(
                row[f"{key}_outcome"] == "not_attempted" for row in rows
            ),
            "legacy_present": sum(
                row[f"{key}_outcome"] == "legacy_present" for row in rows
            ),
            "missing": sum(row[f"{key}_status"] == "missing" for row in rows),
        }
        for key in DEFAULT_SOLVERS
    }
    return {
        "scope": "all committed public tasks; validation_instances excluded",
        "default_solvers": DEFAULT_SOLVERS,
        "public_task_count": len(rows),
        "summary": summary,
        "solution_json_parse_errors": parse_errors,
        "rows": rows,
    }


def write_csv(path: Path, inventory: dict[str, Any]) -> None:
    base_fields = [
        "problem_path",
        "problem_short_name",
        "problem_instance_uuid",
        "task_index",
        "task_uuid",
        "curation_tier",
        "reference_provenance_grade",
        "num_orbitals",
        "num_electrons",
    ]
    fields = list(base_fields)
    for key in DEFAULT_SOLVERS:
        fields.extend(
            (f"{key}_status", f"{key}_outcome", f"{key}_solution_paths")
        )
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for source in inventory["rows"]:
            row = dict(source)
            for key in DEFAULT_SOLVERS:
                row[f"{key}_solution_paths"] = ";".join(
                    row[f"{key}_solution_paths"]
                )
            writer.writerow(row)


def write_markdown(path: Path, inventory: dict[str, Any]) -> None:
    lines = [
        "# G-31 default solver x public task coverage",
        "",
        "Generated only from committed `problem_instances/` and "
        "`solution_files/` JSON. Validation instances are excluded. A cell is "
        "present only when a solution's stable solver UUID matches the exact "
        "default adapter identity below and its `solution_data` names the task. "
        "Artifact presence is separate from whether the solver was attempted.",
        "",
        "Regenerate with:",
        "",
        "```bash",
        "python scripts/solver_panel/build_coverage_inventory.py",
        "```",
        "",
        "## Default identities",
        "",
        "| key | adapter | default variant | solver UUID |",
        "|---|---|---|---|",
    ]
    for key, details in DEFAULT_SOLVERS.items():
        lines.append(
            f"| `{key}` | `{details['adapter']}` | `{details['variant']}` | "
            f"`{details['solver_uuid']}` |"
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"Public tasks: **{inventory['public_task_count']}**.",
            "",
            "| solver | present | attempted | not attempted | legacy present | "
            "missing | artifact coverage |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for key, counts in inventory["summary"].items():
        fraction = counts["present"] / inventory["public_task_count"]
        lines.append(
            f"| `{key}` | {counts['present']} | {counts['attempted']} | "
            f"{counts['not_attempted']} | {counts['legacy_present']} | "
            f"{counts['missing']} | {fraction:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Coverage matrix",
            "",
            "`A` = attempted, `N` = explicitly not attempted, `L` = legacy "
            "present without attempt metadata, and `M` = missing. Exact paths "
            "are in the adjacent CSV and JSON artifacts.",
            "",
            "| orbitals | electrons | instance | task UUID | PySCF FCI | "
            "SHCI opt | DMRG | ipie UHF |",
            "|---:|---:|---|---|:---:|:---:|:---:|:---:|",
        ]
    )
    for row in inventory["rows"]:
        status = [
            {
                "attempted": "A",
                "not_attempted": "N",
                "legacy_present": "L",
            }.get(row[f"{key}_outcome"], "M")
            for key in DEFAULT_SOLVERS
        ]
        lines.append(
            f"| {row['num_orbitals'] or '?'} | {row['num_electrons'] or '?'} | "
            f"`{row['problem_short_name']}` | `{row['task_uuid']}` | "
            f"{' | '.join(status)} |"
        )
    if inventory["solution_json_parse_errors"]:
        lines.extend(["", "## Parse errors", ""])
        lines.extend(
            f"- `{message}`" for message in inventory["solution_json_parse_errors"]
        )
    else:
        lines.extend(["", "Solution JSON parse errors: **0**."])
    lines.extend(
        [
            "",
            "## Tranche-2 estimate",
            "",
            "Pending tranche-1 terminal outcomes. G-31 requires this estimate "
            "before campaign wrap-up; it is intentionally not guessed from "
            "unattempted rows.",
            "",
        ]
    )
    path.write_text("\n".join(lines))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = repo_root / "analysis" / "solver_panel"
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory(repo_root)
    json_path = output_dir / "g31_default_solver_coverage.json"
    csv_path = output_dir / "g31_default_solver_coverage.csv"
    markdown_path = output_dir / "g31_default_solver_coverage.md"
    json_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    write_csv(csv_path, inventory)
    write_markdown(markdown_path, inventory)
    print(
        json.dumps(
            {
                "public_tasks": inventory["public_task_count"],
                "summary": inventory["summary"],
                "parse_errors": len(inventory["solution_json_parse_errors"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
