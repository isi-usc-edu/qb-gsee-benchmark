#!/usr/bin/env python3
"""Apply the G39 vocabulary and campaign metadata migration to G31 records."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.solvers.base import harness_attempted
from qb_gsee_benchmark.solvers.base import validate_solution_payload

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = "g31_tranche1_2026-07"
SOURCE_COMMITS = {
    "90e7e0b": "original_pyscf",
    "56792ca": "original_shci",
    "2629353": "original_ipie",
    "454ab19": "diamond_pyscf",
    "a545345": "diamond_shci",
    "839f67a": "diamond_ipie",
}
EXPECTED_RECORDS = 165
EXPECTED_ORIGINAL_CORRECTIONS = 27
EXPECTED_DIAMOND_CORRECTIONS = 2
SHCI_EPS_VAR = 5.0e-5
SHCI_EPS_VAR_LABEL = "5e-5"
TIMEOUT_ELAPSED_SECONDS = {
    (
        "solution_files/pyscf_solutions/"
        "solution.b4fb73b8-4452-5072-99b6-eb9f61523499.json"
    ): 1800.1470546722412,
    (
        "solution_files/pyscf_solutions/"
        "solution.d42dc028-303e-5b43-a6d0-146bdb908fc8.json"
    ): 1800.1083147525787,
    (
        "solution_files/pyscf_solutions/"
        "solution.322b3212-6364-5bef-bb6b-d0b61ed77bc5.json"
    ): 1800.1612884998322,
    (
        "solution_files/pyscf_solutions/"
        "solution.64e051dd-532e-51b3-94e1-9409438d3764.json"
    ): 1800.1102952957153,
    (
        "solution_files/SHCI/"
        "solution.d42dc028-303e-5b43-a6d0-146bdb908fc8.json"
    ): 7200.1054763793945,
    (
        "solution_files/SHCI/"
        "solution.322b3212-6364-5bef-bb6b-d0b61ed77bc5.json"
    ): 7200.10426735878,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_paths() -> dict[Path, tuple[str, str]]:
    paths: dict[Path, tuple[str, str]] = {}
    for commit, source in SOURCE_COMMITS.items():
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            if line.startswith("solution_files/") and line.endswith(".json"):
                path = Path(line)
                if path in paths:
                    raise RuntimeError(f"duplicate G31 source path: {path}")
                paths[path] = (source, commit)
    if len(paths) != EXPECTED_RECORDS:
        raise RuntimeError(
            f"G31 source commits identify {len(paths)} records; "
            f"expected {EXPECTED_RECORDS}"
        )
    return dict(sorted(paths.items(), key=lambda item: str(item[0])))


def changed_paths(before: Any, after: Any, prefix: str = "") -> set[str]:
    if isinstance(before, dict) and isinstance(after, dict):
        paths: set[str] = set()
        for key in before.keys() | after.keys():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key not in before or key not in after:
                paths.add(child)
            else:
                paths.update(changed_paths(before[key], after[key], child))
        return paths
    if isinstance(before, list) and isinstance(after, list):
        paths: set[str] = set()
        if len(before) != len(after):
            return {prefix}
        for index, (left, right) in enumerate(zip(before, after)):
            paths.update(changed_paths(left, right, f"{prefix}[{index}]"))
        return paths
    return set() if before == after else {prefix}


def migrate_payload(
    payload: dict[str, Any],
    timeout_elapsed_seconds: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    migrated = deepcopy(payload)
    rows = migrated.get("solution_data", [])
    if len(rows) != 1:
        raise RuntimeError("G31 campaign records must contain exactly one solution row")
    details = rows[0].setdefault("solution_details", {})
    status_before = details.get("harness_status")
    attempted_before = details.get("attempted")
    reason = details.get("not_attempted_reason")
    status_after = status_before
    timed_out = (
        status_before == "not_attempted"
        and isinstance(reason, str)
        and reason.startswith("attempt timed out at adapter-default wall cap")
    )
    if timed_out:
        status_after = "timeout"
    attempted_after = harness_attempted(status_after)
    details["harness_status"] = status_after
    details["attempted"] = attempted_after
    details["campaign"] = CAMPAIGN
    if status_after == "timeout" and timeout_elapsed_seconds is not None:
        run_time = rows[0].setdefault("run_time", {})
        for timing_name in ("overall_time", "algorithm_run_time"):
            run_time.setdefault(timing_name, {})["seconds"] = timeout_elapsed_seconds

    algorithm = migrated["solver_details"]["algorithm_details"]
    config = algorithm.setdefault("solver_config", {})
    config["campaign"] = CAMPAIGN
    is_shci = algorithm.get("harness_adapter") == "shci_arrow"
    if is_shci:
        config["eps_var"] = SHCI_EPS_VAR
        config["eps_var_label"] = SHCI_EPS_VAR_LABEL

    allowed = {
        "solution_data[0].solution_details.harness_status",
        "solution_data[0].solution_details.attempted",
        "solution_data[0].solution_details.campaign",
        "solver_details.algorithm_details.solver_config.campaign",
    }
    if status_after == "timeout" and timeout_elapsed_seconds is not None:
        allowed.update(
            {
                "solution_data[0].run_time.overall_time.seconds",
                "solution_data[0].run_time.algorithm_run_time.seconds",
            }
        )
    if is_shci:
        allowed.update(
            {
                "solver_details.algorithm_details.solver_config.eps_var",
                "solver_details.algorithm_details.solver_config.eps_var_label",
            }
        )
    changes = changed_paths(payload, migrated)
    unexpected = changes - allowed
    if unexpected:
        raise RuntimeError(f"migration changed disallowed fields: {sorted(unexpected)}")
    return migrated, {
        "task_uuid": rows[0].get("task_uuid"),
        "status_before": status_before,
        "status_after": status_after,
        "attempted_before": attempted_before,
        "attempted_after": attempted_after,
        "reason": reason,
        "timeout_elapsed_seconds": timeout_elapsed_seconds,
        "changed_paths": sorted(changes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "analysis"
            / "solver_panel"
            / "g39_solution_vocabulary_migration.json"
        ),
    )
    args = parser.parse_args()

    records = []
    original_corrections = []
    diamond_corrections = []
    for relative_path, (source, source_commit) in source_paths().items():
        path = ROOT / relative_path
        baseline = subprocess.run(
            ["git", "show", f"{source_commit}:{relative_path}"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        current = path.read_bytes()
        payload = json.loads(baseline)
        previous, _ = migrate_payload(payload)
        elapsed = TIMEOUT_ELAPSED_SECONDS.get(str(relative_path))
        migrated, change = migrate_payload(payload, elapsed)
        validate_solution_payload(migrated, schema_dir=ROOT / "schemas")
        after_bytes = (json.dumps(migrated, indent=2, sort_keys=True) + "\n").encode()
        previous_bytes = (
            json.dumps(previous, indent=2, sort_keys=True) + "\n"
        ).encode()
        if current not in {baseline, previous_bytes, after_bytes}:
            raise RuntimeError(
                f"{relative_path} is neither the source nor migrated payload"
            )
        corrected = (
            change["status_before"] != change["status_after"]
            or change["attempted_before"] != change["attempted_after"]
        )
        record = {
            "path": str(relative_path),
            "source": source,
            "source_commit": source_commit,
            "task_uuid": change["task_uuid"],
            "status_before": change["status_before"],
            "status_after": change["status_after"],
            "attempted_before": change["attempted_before"],
            "attempted_after": change["attempted_after"],
            "reason": change["reason"],
            "timeout_elapsed_seconds": change["timeout_elapsed_seconds"],
            "changed_paths": change["changed_paths"],
            "sha256_before": sha256_bytes(baseline),
            "sha256_after": sha256_bytes(after_bytes),
        }
        records.append(record)
        if corrected and source.startswith("original_"):
            original_corrections.append(str(relative_path))
        if corrected and source.startswith("diamond_"):
            diamond_corrections.append(str(relative_path))
        if args.apply:
            path.write_bytes(after_bytes)

    if len(original_corrections) != EXPECTED_ORIGINAL_CORRECTIONS:
        raise RuntimeError(
            f"found {len(original_corrections)} original corrections; "
            f"expected {EXPECTED_ORIGINAL_CORRECTIONS}"
        )
    if len(diamond_corrections) != EXPECTED_DIAMOND_CORRECTIONS:
        raise RuntimeError(
            f"found {len(diamond_corrections)} diamond corrections; "
            f"expected {EXPECTED_DIAMOND_CORRECTIONS}"
        )
    report = {
        "status": "applied" if args.apply else "preview",
        "campaign": CAMPAIGN,
        "records": len(records),
        "original_corrections": original_corrections,
        "diamond_corrections": diamond_corrections,
        "shci_eps_var": SHCI_EPS_VAR,
        "shci_eps_var_label": SHCI_EPS_VAR_LABEL,
        "records_detail": records,
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    print(
        json.dumps(
            {
                "status": report["status"],
                "records": report["records"],
                "original_corrections": len(original_corrections),
                "diamond_corrections": len(diamond_corrections),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
