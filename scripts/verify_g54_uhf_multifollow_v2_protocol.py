#!/usr/bin/env python3
"""Fail closed on the preregistered G-54 v2 single-delta protocol."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
V1_PROTOCOL = Path("analysis/solver_campaigns/g54_g49c_uhf_multifollow_v1.json")
V2_PROTOCOL = Path("analysis/solver_campaigns/g54_g49c_uhf_multifollow_v2.json")
V2_DESIGN = Path("analysis/solver_campaigns/g54_g49c_uhf_multifollow_v2_design.md")


def _record(checks: dict[str, bool], name: str, condition: Any) -> None:
    checks[name] = bool(condition)


def _scientific_normal_form(protocol: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(protocol)
    normalized["run_generation"] = "<generation>"
    normalized["outcome_contract"] = {
        "<outcome_vocabulary>": "<reporting_schema>",
        "target_energy_used_for_search": False,
    }
    normalized["convergence"][
        "maximum_strict_refinement_attempts_per_stationary_point"
    ] = "<strict_refinement_budget>"
    normalized["start_generation"]["per_start_protocol"] = (
        "<strict_refinement_budget_description>"
    )
    v1_evidence = "per_branch_refinement_cycle_accounting"
    if v1_evidence not in normalized["required_evidence"]:
        normalized["required_evidence"].append(v1_evidence)
    normalized["required_evidence"].sort()
    return normalized


def verify(root: Path = ROOT) -> dict[str, Any]:
    v1 = json.loads((root / V1_PROTOCOL).read_text(encoding="utf-8"))
    v2 = json.loads((root / V2_PROTOCOL).read_text(encoding="utf-8"))
    design = " ".join((root / V2_DESIGN).read_text(encoding="utf-8").split())
    checks: dict[str, bool] = {}

    _record(checks, "goal", v2.get("goal") == "G-54")
    _record(
        checks,
        "identity",
        v2.get("campaign_id") == "g49_pyscf_stability_resolved_2026-07_v1"
        and v2.get("run_generation") == "g49c_uhf_multifollow_v2"
        and v2.get("status") == "preregistered_before_execution",
    )
    _record(
        checks,
        "single_scientific_delta",
        _scientific_normal_form(v1) == _scientific_normal_form(v2),
    )
    _record(
        checks,
        "strict_refinement_budget_delta",
        v1["convergence"][
            "maximum_strict_refinement_attempts_per_stationary_point"
        ]
        == 1
        and v2["convergence"][
            "maximum_strict_refinement_attempts_per_stationary_point"
        ]
        == 8
        and "up_to_eight_strict_newton_refinement_cycles"
        in v2["start_generation"]["per_start_protocol"],
    )
    _record(
        checks,
        "outcome_vocabulary",
        v2.get("outcome_contract")
        == {
            "stable_lower_found": "accepted_annotation",
            "no_lower_stable_within_protocol": "accepted_qualified_annotation",
            "still_unresolved": "unresolved_not_no_lower_claim",
            "target_energy_used_for_search": False,
        },
    )
    _record(
        checks,
        "frozen_four_starts",
        v2["start_generation"]["order"] == ["G1", "G2", "G3", "G4"]
        and v2["start_generation"]["branch_start_budget"] == 4
        and v2["start_generation"]["density_source"]
        == "frozen_mfproto_v3_initial_spin_density_guesses",
    )
    _record(
        checks,
        "frozen_strict_acceptance",
        v2["convergence"]["engine_converged_required"] is True
        and v2["convergence"]["final_delta_energy_strictly_less_than_hartree"]
        == 1e-10
        and v2["convergence"]["maximum_ov_gradient_strictly_less_than"]
        == 1e-7,
    )
    _record(
        checks,
        "frozen_search",
        v2["search"]["root_window_above_lowest_hartree"] == 5e-5
        and v2["search"]["stationary_point_budget_including_global_starts"]
        == 16
        and v2["search"]["maximum_follow_hops_per_path"] == 6
        and v2["search"]["follow_all_internal_roots_in_window"] is True,
    )
    _record(
        checks,
        "target_blind",
        v2["search"]["target_energy"] is None
        and v2["search"][
            "known_terminal_energy_used_for_initialization_ordering_stopping_or_acceptance"
        ]
        is False
        and v2["outcome_contract"]["target_energy_used_for_search"] is False,
    )
    _record(
        checks,
        "frozen_stability",
        v2["stability_certification"] == v1["stability_certification"],
    )
    _record(
        checks,
        "whole_node_cap",
        v2["pbs"]["account"] == "QC_NA_Sim"
        and v2["pbs"]["queue"] == "compute"
        and v2["pbs"]["ncpus"] == 128
        and v2["pbs"]["memory_request"] is None
        and v2["pbs"]["walltime_seconds"] == 1800
        and v2["pbs"]["maximum_node_hours"] == 0.5
        and v2["pbs"]["debug_queue_permitted"] is False
        and v2["pbs"]["backfill_only_after_compute_allocation_exhaustion"] is True,
    )
    _record(
        checks,
        "annotation_only",
        v2["result_pooling"]["annotation_layer_only"] is True
        and v2["result_pooling"]["pool_with_g48_or_g53"] is False
        and v2["result_pooling"]["replace_frozen_records"] is False,
    )
    _record(
        checks,
        "cycle_evidence",
        "per_branch_refinement_cycle_accounting" in v2["required_evidence"],
    )
    _record(
        checks,
        "design_single_delta",
        "only scientific protocol change from G-54 v1" in design
        and "up to eight strict Newton refinement cycles instead of one" in design
        and "one invocation of the same frozen PySCF second-order Newton kernel"
        in design
        and "No threshold or engine-acceptance rule changes in v2." in design,
    )
    _record(
        checks,
        "design_dispositions",
        all(
            token in design
            for token in (
                "`stable_lower_found`",
                "`no_lower_stable_within_protocol`",
                "`still_unresolved`",
            )
        ),
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
