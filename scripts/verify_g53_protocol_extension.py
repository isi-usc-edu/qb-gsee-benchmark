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
REMEDIATION = Path(
    "analysis/solver_campaigns/g53_g49c_strict_tolerance_remediation_v1.json"
)
REMEDIATION_DESIGN = Path(
    "analysis/solver_campaigns/g53_g49c_strict_tolerance_remediation_design.md"
)
ENFORCEMENT_FIX = Path(
    "analysis/solver_campaigns/g53_g49c_strict_enforcement_fix_v2.json"
)
ENFORCEMENT_FIX_DESIGN = Path(
    "analysis/solver_campaigns/g53_g49c_strict_enforcement_fix_v2.md"
)
RECONSTRUCTION_FIX = Path(
    "analysis/solver_campaigns/g53_g49c_strict_reconstruction_fix_v3.json"
)
RECONSTRUCTION_FIX_DESIGN = Path(
    "analysis/solver_campaigns/g53_g49c_strict_reconstruction_fix_v3.md"
)


def _check(checks: dict[str, bool], name: str, value: Any) -> None:
    checks[name] = bool(value)


def verify(root: Path = ROOT) -> dict[str, Any]:
    data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    design = (root / DESIGN).read_text(encoding="utf-8")
    remediation = json.loads((root / REMEDIATION).read_text(encoding="utf-8"))
    remediation_design = (root / REMEDIATION_DESIGN).read_text(encoding="utf-8")
    enforcement = json.loads((root / ENFORCEMENT_FIX).read_text(encoding="utf-8"))
    enforcement_design = (root / ENFORCEMENT_FIX_DESIGN).read_text(encoding="utf-8")
    enforcement_words = " ".join(enforcement_design.lower().split())
    reconstruction = json.loads(
        (root / RECONSTRUCTION_FIX).read_text(encoding="utf-8")
    )
    reconstruction_design = (
        root / RECONSTRUCTION_FIX_DESIGN
    ).read_text(encoding="utf-8")
    reconstruction_words = " ".join(reconstruction_design.lower().split())
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
    first_launch = remediation.get("first_launch", {})
    strict = remediation.get("strict_acceptance", {})
    remediation_pbs = remediation.get("pbs", {})
    _check(
        checks,
        "remediation_distinct_generation",
        remediation.get("parent_run_generation") == "g49c_protocol_extension_v1"
        and remediation.get("run_generation") == "g49c_strict_tolerance_fix_v1"
        and remediation.get("scope")
        == ["fb87d637-aaab-4e8f-8898-4ecca8bd0fe0"],
    )
    _check(
        checks,
        "first_launch_false_pass_bound",
        first_launch.get("records_immutable") is True
        and first_launch.get("verifier_disposition")
        == "invalid_false_pass_missing_energy_change_assertion"
        and first_launch.get("observed_final_delta_energy_hartree")
        > first_launch.get("preregistered_limit_hartree"),
    )
    _check(
        checks,
        "remediation_strict_acceptance",
        strict.get("engine_converged_required") is True
        and strict.get("final_delta_energy_strictly_less_than_hartree") == 1e-10
        and strict.get("maximum_ov_gradient_strictly_less_than") == 1e-7
        and strict.get("maximum_refinement_attempts_per_stationary_point") == 1,
    )
    _check(
        checks,
        "remediation_cost_cap",
        remediation_pbs.get("queue") == "compute"
        and remediation_pbs.get("ncpus") == 128
        and remediation_pbs.get("memory_request") is None
        and remediation_pbs.get("scheduler_verifier_node") is False
        and remediation_pbs.get("cumulative_worst_case_node_hours")
        < remediation_pbs.get("authorized_cumulative_node_hour_cap")
        == 1.0,
    )
    _check(
        checks,
        "remediation_design_disclosure",
        "false pass" in remediation_design
        and "replaces only the fb87d637 row" in remediation_design,
    )
    corrections = enforcement.get("implementation_corrections", {})
    enforcement_pbs = enforcement.get("pbs", {})
    _check(
        checks,
        "enforcement_fix_distinct_generation",
        enforcement.get("parent_run_generation")
        == "g49c_strict_tolerance_fix_v1"
        and enforcement.get("run_generation") == "g49c_strict_tolerance_fix_v2"
        and enforcement.get("protocol_changed") is False,
    )
    _check(
        checks,
        "enforcement_fix_fail_closed",
        corrections.get(
            "bootstrap_candidate_receives_authorized_strict_refinement"
        )
        is True
        and corrections.get("maximum_strict_refinement_attempts_per_stationary_point")
        == 1
        and corrections.get("verifier_requires_search_exhausted") is True
        and corrections.get("verifier_requires_at_least_one_clean_minimum") is True,
    )
    _check(
        checks,
        "enforcement_fix_cost",
        enforcement_pbs.get("queue") == "compute"
        and enforcement_pbs.get("ncpus") == 128
        and enforcement_pbs.get("memory_request") is None
        and enforcement_pbs.get("cumulative_worst_case_node_hours")
        < enforcement_pbs.get("authorized_cumulative_node_hour_cap")
        == 1.0,
    )
    _check(
        checks,
        "enforcement_fix_design",
        "implementation correction, not a protocol change" in enforcement_words
        and "zero clean minima" in enforcement_words,
    )
    reconstruction_rule = reconstruction.get("implementation_correction", {})
    reconstruction_pbs = reconstruction.get("pbs", {})
    _check(
        checks,
        "reconstruction_fix_distinct_generation",
        reconstruction.get("parent_run_generation")
        == "g49c_strict_tolerance_fix_v2"
        and reconstruction.get("run_generation")
        == "g49c_strict_tolerance_fix_v3"
        and reconstruction.get("protocol_changed") is False,
    )
    _check(
        checks,
        "reconstruction_fix_scoped",
        reconstruction_rule.get("temporary_label_used_only_to_reconstruct_orbitals")
        is True
        and reconstruction_rule.get("strict_acceptance_reapplied_after_newton")
        is True
        and reconstruction_rule.get(
            "maximum_strict_refinement_attempts_per_stationary_point"
        )
        == 1,
    )
    _check(
        checks,
        "reconstruction_fix_cost",
        reconstruction_pbs.get("queue") == "compute"
        and reconstruction_pbs.get("ncpus") == 128
        and reconstruction_pbs.get("memory_request") is None
        and reconstruction_pbs.get("cumulative_worst_case_node_hours")
        < reconstruction_pbs.get("authorized_cumulative_node_hour_cap")
        == 1.0,
    )
    _check(
        checks,
        "reconstruction_fix_design",
        "temporary dataclass copy" in reconstruction_words
        and "does not accept the candidate" in reconstruction_words,
    )

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
