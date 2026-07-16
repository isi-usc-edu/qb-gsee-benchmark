#!/usr/bin/env python3
"""Fail closed on the Matt-reserved G-50 desk-design gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("analysis/solver_campaigns/g50_campaign_contract_v1.json")
DESIGN_PATH = Path("analysis/solver_campaigns/g50_endgame_clean_slate_design.md")
CORPUS_DEFINITION = (
    "G-48 closed out, FeMoco-54 quarantine filed, Gao feature backfill "
    "decided, no pending task admissions/removals"
)
EXPECTED_GATES = [
    "corpus_and_core_manifest_freeze",
    "matt_per_solver_configuration_signoff",
    "pi_design_review",
]
EXPECTED_SOLVERS = {"ipie_uhf_trial", "DMRG", "TrimCI", "SHCI"}
EXPECTED_CAMPAIGNS = {
    "g50_ipie_swing_clean_slate_2026-07_v1",
    "g50_dmrg_clean_slate_2026-07_v1",
    "g50_trimci_clean_slate_2026-07_v1",
    "g50_shci_clean_slate_2026-07_v1",
}
HISTORICAL_IPIE = {"ipie_swing_2026-07", "ipie_swing_envfix_2026-07"}
MATT_SELECTIONS = {
    "DMRG": "DMRG-A",
    "SHCI": "SHCI-A",
    "TrimCI": "TrimCI-A",
    "ipie_uhf_trial": "iPIE-A",
}


def _record(checks: dict[str, bool], name: str, condition: Any) -> None:
    checks[name] = bool(condition)


def verify(root: Path = ROOT) -> dict[str, Any]:
    contract = json.loads((root / CONTRACT_PATH).read_text(encoding="utf-8"))
    design = (root / DESIGN_PATH).read_text(encoding="utf-8")
    design_words = " ".join(design.split())
    checks: dict[str, bool] = {}

    campaigns = contract.get("campaigns", [])
    _record(
        checks,
        "campaign_ids",
        {item.get("campaign_id") for item in campaigns} == EXPECTED_CAMPAIGNS,
    )
    _record(checks, "campaign_count", len(campaigns) == 4)
    _record(
        checks,
        "campaigns_not_designated",
        all(
            item.get("headline_designation_status") == "not_designated"
            for item in campaigns
        ),
    )
    _record(checks, "gate_order", contract.get("gates") == EXPECTED_GATES)

    corpus = contract.get("corpus_settle", {})
    _record(
        checks,
        "corpus_definition",
        corpus.get("definition") == CORPUS_DEFINITION,
    )
    conditions = {
        item.get("id"): item.get("satisfied") for item in corpus.get("conditions", [])
    }
    _record(checks, "g48_closed", conditions.get("g48_closed_out") is True)
    _record(
        checks,
        "femoco_quarantine",
        conditions.get("femoco54_quarantine_filed") is True,
    )
    _record(
        checks,
        "gao_decided",
        conditions.get("gao_feature_backfill_decided") is True,
    )
    _record(
        checks,
        "no_pending_admissions_or_removals",
        "no_pending_task_admissions_or_removals" in conditions
        and conditions["no_pending_task_admissions_or_removals"] is True,
    )
    _record(
        checks,
        "corpus_settled",
        corpus.get("settled") is True
        and contract.get("cost_projection", {}).get("core_task_count") == 718,
    )

    signoff = contract.get("matt_configuration_signoff", {})
    directives = signoff.get("directives", {})
    _record(checks, "matt_authority", signoff.get("authority") == "Matt")
    _record(
        checks,
        "signoff_approved",
        signoff.get("status") == "approved"
        and directives.get("DMRG", {}).get("retention")
        == "every_bond_dimension_rung_as_separate_nested_result"
        and directives.get("TrimCI", {}).get("determinant_ceiling") == 10_000_000
        and directives.get("TrimCI", {}).get("snapshot_semantics")
        == "observation_only_no_search_protocol_changes",
    )
    _record(
        checks,
        "freeze_allowed_after_signoff",
        signoff.get("configuration_freeze_allowed") is True
        and signoff.get("numeric_pins_pending_pilot_calibration") is True,
    )
    _record(
        checks,
        "pi_implementer_cannot_select",
        signoff.get("selected_by_pi_or_implementer") is False,
    )
    _record(
        checks,
        "ipie_submitter_selected",
        signoff.get("ipie_submitter_selected") == "Matt",
    )
    options = signoff.get("options", {})
    _record(checks, "all_solver_option_sets", set(options) == EXPECTED_SOLVERS)
    for solver in sorted(EXPECTED_SOLVERS):
        item = options.get(solver, {})
        values = item.get("values", [])
        option_ids = {value.get("option_id") for value in values}
        _record(checks, f"{solver}:multiple_options", len(option_ids) >= 2)
        _record(
            checks,
            f"{solver}:recommendation_is_option",
            item.get("recommended_option_id") in option_ids,
        )
        _record(
            checks,
            f"{solver}:selection_matches_matt",
            item.get("selected_option_id") == MATT_SELECTIONS[solver],
        )

    designation = contract.get("headline_designation", {})
    _record(
        checks,
        "metrics_spec_v1_9",
        designation.get("metrics_spec_version") == "1.9",
    )
    _record(
        checks,
        "designation_required",
        designation.get("designation_required_before_headline") is True,
    )
    template = root / designation.get("g48_structural_template", "")
    _record(checks, "designation_template_exists", template.is_file())
    if template.is_file():
        template_data = json.loads(template.read_text(encoding="utf-8"))
        _record(
            checks,
            "designation_template_is_v1_9",
            template_data.get("metrics_spec", {}).get(
                "effective_version_after_approval"
            )
            == "1.9",
        )
    exclusions = designation.get("historical_ipie_exclusions", [])
    _record(
        checks,
        "historical_ipie_ids",
        {item.get("campaign_id") for item in exclusions} == HISTORICAL_IPIE,
    )
    _record(
        checks,
        "historical_ipie_excluded",
        all(item.get("headline_eligible") is False for item in exclusions),
    )

    _record(
        checks,
        "design_has_exact_corpus_definition",
        CORPUS_DEFINITION in design_words,
    )
    _record(
        checks,
        "design_reserves_matt_authority",
        "Matt's per-solver configuration sign-off" in design_words
        and "The PI does not choose or substitute solver configurations."
        in design_words
        and all(
            f"Selected: {option_id}" in design for option_id in MATT_SELECTIONS.values()
        )
        and "Every bond-dimension rung is retained as a separate" in design
        and "10,000,000 determinants" in design
        and "Snapshotting is observation-only" in design,
    )
    for label in ("iPIE", "DMRG", "TrimCI", "SHCI"):
        _record(
            checks,
            f"design:{label}:options",
            f"### {label} options for Matt" in design,
        )
    _record(
        checks,
        "design_excludes_historical_ipie",
        all(campaign in design for campaign in HISTORICAL_IPIE)
        and "excluded from headline metrics" in design,
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
