#!/usr/bin/env python3
"""Fail closed on the preregistered G-54 real-UHF search protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = Path("analysis/solver_campaigns/g54_g49c_uhf_multifollow_v1.json")
DESIGN = Path("analysis/solver_campaigns/g54_g49c_uhf_multifollow_design.md")


def _record(checks: dict[str, bool], name: str, condition: Any) -> None:
    checks[name] = bool(condition)


def verify(root: Path = ROOT) -> dict[str, Any]:
    protocol = json.loads((root / PROTOCOL).read_text(encoding="utf-8"))
    design = (root / DESIGN).read_text(encoding="utf-8")
    design_words = " ".join(design.split())
    checks: dict[str, bool] = {}

    _record(checks, "goal", protocol.get("goal") == "G-54")
    _record(
        checks,
        "identity",
        protocol.get("campaign_id")
        == "g49_pyscf_stability_resolved_2026-07_v1"
        and protocol.get("run_generation") == "g49c_uhf_multifollow_v1"
        and protocol.get("status") == "preregistered_before_execution",
    )
    scope = protocol.get("method_scope", {})
    _record(
        checks,
        "real_uhf_only",
        scope.get("method") == "real_UHF_only"
        and scope.get("ghf_permitted") is False
        and scope.get("complex_orbitals_permitted") is False
        and scope.get("external_stability_recomputed") is False
        and scope.get("result_label") == "within_uhf_stable"
        and scope.get("stability_clean_label_permitted") is False,
    )
    starts = protocol.get("start_generation", {})
    _record(
        checks,
        "four_frozen_starts",
        starts.get("branch_start_budget") == 4
        and starts.get("order") == ["G1", "G2", "G3", "G4"]
        and starts.get("density_source")
        == "frozen_mfproto_v3_initial_spin_density_guesses"
        and starts.get("start_selection_by_energy_permitted") is False,
    )
    search = protocol.get("search", {})
    _record(
        checks,
        "multifollow_budget",
        search.get("root_window_above_lowest_hartree") == 5e-5
        and search.get("stationary_point_budget_including_global_starts") == 16
        and search.get("maximum_follow_hops_per_path") == 6
        and search.get("follow_all_internal_roots_in_window") is True,
    )
    _record(
        checks,
        "target_blind",
        search.get("target_energy") is None
        and search.get(
            "known_terminal_energy_used_for_initialization_ordering_stopping_or_acceptance"
        )
        is False
        and protocol.get("outcome_contract", {}).get(
            "target_energy_used_for_search"
        )
        is False,
    )
    convergence = protocol.get("convergence", {})
    _record(
        checks,
        "strict_convergence",
        convergence.get("engine_converged_required") is True
        and convergence.get("final_delta_energy_strictly_less_than_hartree")
        == 1e-10
        and convergence.get("maximum_ov_gradient_strictly_less_than") == 1e-7
        and convergence.get(
            "maximum_strict_refinement_attempts_per_stationary_point"
        )
        == 1,
    )
    stability = protocol.get("stability_certification", {})
    panels = stability.get("independent_start_panels", [])
    _record(
        checks,
        "multi_start_stability",
        stability.get("multi_start_required_at_every_claimed_minimum") is True
        and stability.get("scope") == "internal_real_UHF_tangent_space_only"
        and stability.get("davidson_residual_norm") == 1e-7
        and stability.get("davidson_eigenvalue_agreement_hartree") == 1e-6
        and stability.get("internal_stability_threshold_hartree") == -1e-5
        and [panel.get("id") for panel in panels]
        == ["lowest_diagonal_coordinates", "sha256_rademacher"]
        and all(panel.get("count") == 8 for panel in panels),
    )
    pbs = protocol.get("pbs", {})
    _record(
        checks,
        "pbs_cap",
        pbs.get("account") == "QC_NA_Sim"
        and pbs.get("queue") == "compute"
        and pbs.get("ncpus") == 128
        and pbs.get("memory_request") is None
        and pbs.get("scheduler_jobs") == 1
        and pbs.get("walltime_seconds") == 1800
        and pbs.get("maximum_node_hours") == 0.5
        and pbs.get("task_and_verifier_share_allocation") is True
        and pbs.get("debug_queue_permitted") is False,
    )
    pooling = protocol.get("result_pooling", {})
    _record(
        checks,
        "annotation_only",
        pooling.get("annotation_layer_only") is True
        and pooling.get("pool_with_g48_or_g53") is False
        and pooling.get("replace_frozen_records") is False,
    )
    evidence = set(protocol.get("required_evidence", []))
    _record(
        checks,
        "closeout_evidence",
        {
            "canonical_environment_capture",
            "raw_scheduler_log_and_accounting_inside_bundle",
            "multi_start_stability_evidence",
            "raw_junit",
            "pinned_environment_record",
        }.issubset(evidence),
    )
    _record(
        checks,
        "design_scope",
        "performs no GHF, complex-orbital, or external-stability operation"
        in design_words
        and "There is no target energy." in design_words
        and "all four frozen MFPROTO-v3 UHF densities" in design_words
        and "two independent deterministic Davidson start panels" in design_words,
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
