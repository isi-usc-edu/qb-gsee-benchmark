"""Audits for solver-harness outcome metadata."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.solvers.base import HARNESS_STATUSES
from qb_gsee_benchmark.solvers.base import harness_attempted


def has_execution_evidence(solution_details: dict[str, Any]) -> bool:
    """Return whether adapter-private details prove that execution started."""

    for key, value in solution_details.items():
        if not key.endswith("details") or not isinstance(value, dict):
            continue
        command = value.get("command")
        if isinstance(command, list) and command:
            return True
        if value.get("returncode") is not None:
            return True
        if value.get("traceback"):
            return True
    return False


def audit_solution_payload(
    payload: dict[str, Any], source: str
) -> list[dict[str, Any]]:
    """Return vocabulary violations for one solution payload."""

    violations: list[dict[str, Any]] = []
    for index, row in enumerate(payload.get("solution_data", [])):
        details = row.get("solution_details", {})
        if "harness_status" not in details and "attempted" not in details:
            continue
        status = details.get("harness_status")
        attempted = details.get("attempted")
        common = {
            "source": source,
            "solution_data_index": index,
            "task_uuid": row.get("task_uuid"),
            "harness_status": status,
            "attempted": attempted,
        }
        if status not in HARNESS_STATUSES:
            violations.append({**common, "reason": "unsupported_harness_status"})
            continue
        expected = harness_attempted(status)
        if attempted is not expected:
            violations.append({**common, "reason": "attempted_status_mismatch"})
        if status == "not_attempted" and has_execution_evidence(details):
            violations.append(
                {**common, "reason": "not_attempted_has_execution_evidence"}
            )
    return violations


def audit_solution_tree(solution_root: str | Path) -> dict[str, Any]:
    """Audit every JSON solution under a repository solution tree."""

    root = Path(solution_root)
    files = sorted(root.rglob("*.json"))
    statuses: Counter[str] = Counter()
    audited_rows = 0
    violations: list[dict[str, Any]] = []
    for path in files:
        payload = json.loads(path.read_text())
        for row in payload.get("solution_data", []):
            details = row.get("solution_details", {})
            if "harness_status" in details or "attempted" in details:
                audited_rows += 1
                statuses[str(details.get("harness_status"))] += 1
        violations.extend(audit_solution_payload(payload, str(path.relative_to(root))))
    return {
        "status": "pass" if not violations else "fail",
        "solution_files": len(files),
        "audited_harness_rows": audited_rows,
        "harness_status_counts": dict(sorted(statuses.items())),
        "violations": violations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("solution_root", nargs="?", default="solution_files")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_solution_tree(args.solution_root)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
