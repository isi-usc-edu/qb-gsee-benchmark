#!/usr/bin/env python3
"""Fail closed on the G-53 preregistered protocol extension."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("analysis/solver_campaigns/g53_g49c_protocol_extension_v1.json")
DESIGN = Path("analysis/solver_campaigns/g53_g49c_protocol_extension_design.md")


def _check(checks: dict[str, bool], name: str, value: Any) -> None:
    checks[name] = bool(value)


def verify(root: Path = ROOT) -> dict[str, Any]:
    data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    design = (root / DESIGN).read_text(encoding="utf-8")
    checks: dict[str, bool] = {}

    _check(checks, "goal", data.get("goal") == "G-53")
    _check(
        checks,
        "identity",
        data.get("campaign_id") == "g49_pyscf_stability_resolved_2026-07_v1"
        and data.get("run_generation") == "g49c_protocol_extension_v1",
    )
    _check(
        checks,
        "parents_immutable",
        set(data.get("parent_generations", {}).values()) == {"immutable"},
    )
    _check(
        checks,
        "no_pooling",
        data.get("result_pooling", {}).get("pool_with_parent_generations") is False,
    )

    convergence = data.get("convergence", {})
    _check(
        checks,
        "convergence",
        convergence.get("scf_energy_change_hartree") == 1e-10
        and convergence.get("maximum_ov_gradient") == 1e-7
        and convergence.get("engine_converged_required") is True
        and convergence.get("internal_stability_threshold_hartree") == -1e-5
        and convergence.get("external_stability_threshold_hartree") == -1e-5,
    )

    newton = data.get("newton_bootstrap", {})
    _check(checks, "newton_task_count", len(newton.get("tasks", [])) == 2)
    _check(
        checks,
        "newton_frozen_controls",
        newton.get("second_order_controls")
        == "frozen_mfproto_v3_configure_newton_fallback"
        and newton.get("maximum_follow_steps_after_bootstrap") == 2,
    )

    multifollow = data.get("degenerate_direction_multifollow", {})
    _check(
        checks,
        "multifollow_protocol",
        multifollow.get("root_window_above_lowest_hartree") == 5e-5
        and multifollow.get("branch_budget_unique_converged_stationary_points") == 16
        and multifollow.get("maximum_follow_hops_per_path") == 6
        and multifollow.get("follow_all_roots_in_window") is True,
    )
    _check(
        checks,
        "target_blind",
        multifollow.get("known_target_used_for_search_or_stopping") is False
        and multifollow.get("known_audit_target_energy_hartree_report_only")
        == -45.85907658,
    )

    tasks = data.get("tasks", [])
    _check(checks, "task_count", len(tasks) == 3)
    _check(checks, "task_uuids_unique", len({t.get("task_uuid") for t in tasks}) == 3)
    _check(checks, "input_hashes", all(len(t.get("input_sha256", "")) == 64 for t in tasks))

    pbs = data.get("pbs", {})
    reserved = pbs.get("array_elements", 0) * pbs.get("task_walltime_seconds", 0)
    reserved += pbs.get("verifier_walltime_seconds", 0)
    _check(
        checks,
        "pbs_full_node_compute",
        pbs.get("queue") == "compute"
        and pbs.get("ncpus") == 128
        and pbs.get("memory_request") is None
        and pbs.get("debug_queue_permitted") is False,
    )
    _check(
        checks,
        "node_hour_cap",
        reserved / 3600 == pbs.get("maximum_node_hours") == 1.0,
    )

    _check(checks, "design_target_blind", "report-only comparator" in design)
    _check(checks, "design_raw_junit", "raw JUnit XML" in design)
    _check(checks, "design_no_pooling", "does not modify or pool" in design)

    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "schema_version": 1,
        "check_count": len(checks),
        "passed_count": len(checks) - len(failed),
        "failed_checks": failed,
        "status": "passed" if not failed else "failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    report = verify(args.root.resolve())
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
