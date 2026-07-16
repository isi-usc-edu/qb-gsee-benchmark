#!/usr/bin/env python3
"""Fail closed on the Matt-reserved G-50 desk-design gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.canonical_families import (
    EXPECTED_ARTIFACT_SHA256,
    canonical_problem_family,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path("analysis/solver_campaigns/g50_campaign_contract_v1.json")
DESIGN_PATH = Path("analysis/solver_campaigns/g50_endgame_clean_slate_design.md")
PILOT_DESIGN_PATH = Path("analysis/solver_campaigns/g50_pilot_design_v1.json")
PILOT_MANIFEST_PATH = Path("analysis/solver_campaigns/g50_pilot_task_manifest_v3.json")
CANONICAL_FAMILY_ARTIFACT_PATH = Path(
    "analysis/feature_schema/canonical_families_v1.json"
)
FEATURES_PATH = Path("scripts/Hamiltonian_features.csv")
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
FORBIDDEN_PILOT_TOKENS = {
    "accuracy_threshold",
    "pilot_energy_error",
    "prior_solver_outcome",
    "reference_energy",
    "supervised_success_label",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(checks: dict[str, bool], name: str, condition: Any) -> None:
    checks[name] = bool(condition)


def verify(
    root: Path = ROOT, pilot_manifest_path: Path = PILOT_MANIFEST_PATH
) -> dict[str, Any]:
    contract = json.loads((root / CONTRACT_PATH).read_text(encoding="utf-8"))
    design = (root / DESIGN_PATH).read_text(encoding="utf-8")
    pilot_design = json.loads((root / PILOT_DESIGN_PATH).read_text(encoding="utf-8"))
    manifest_input_path = (
        pilot_manifest_path
        if pilot_manifest_path.is_absolute()
        else root / pilot_manifest_path
    )
    pilot_manifest = json.loads(manifest_input_path.read_text(encoding="utf-8"))
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
    cost_projection = contract.get("cost_projection", {})
    _record(
        checks,
        "uniform_cap_budget",
        cost_projection.get("working_uniform_cap_hours_per_task") == 12
        and cost_projection.get("final_uniform_cap_hours_per_task")
        == "TBD_AT_GATE_3"
        and cost_projection.get("planning_scenarios")
        == [
            {
                "cpu_node_hours_per_solver_worst_case": 8616,
                "cpu_node_hours_three_solvers_worst_case": 25848,
                "ipie_a100_hours_worst_case": 8616,
                "tasks_per_solver": 718,
                "uniform_cap_hours_per_task": 12,
            }
        ],
    )
    _record(
        checks,
        "uniform_cap_hardware_units",
        cost_projection.get("hardware_unit_per_task")
        == {
            "DMRG": "one 128-core Improv node",
            "SHCI": "one 128-core Improv node",
            "TrimCI": "one 128-core Improv node",
            "ipie_uhf_trial": "one A100 GPU",
        },
    )
    universal_attempt = contract.get("universal_attempt", {})
    _record(
        checks,
        "universal_attempt_scope",
        universal_attempt.get("attempt_all_tasks_per_solver") is True
        and universal_attempt.get("task_count_per_solver") == 718
        and universal_attempt.get("admission_prediction_permitted") is False
        and universal_attempt.get("per_task_scientific_tuning_permitted") is False
        and universal_attempt.get("not_attempted_permitted") is False,
    )
    _record(
        checks,
        "timeout_scored_non_success",
        universal_attempt.get("timeout_status") == "timeout"
        and universal_attempt.get("timeout_scored_as_success") is False
        and universal_attempt.get("oom_or_build_or_ingest_status") == "failed",
    )
    _record(
        checks,
        "admission_model_deleted",
        "target_blind_admission" not in contract
        and "admitted_task_count" not in cost_projection
        and "planning_caps_per_admitted_task_hours" not in cost_projection
        and "production_hard_caps" not in cost_projection,
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
        "uniform_cap_signoff_evidence",
        set(signoff.get("pre_signoff_evidence", []))
        == {
            "clean_source_snapshot",
            "immutable_dependency_lock",
            "compute_node_smoke",
            "failure_injection_tests",
            "outcome_vocabulary_tests",
            "uniform_cap_pilot_calibration",
            "timeout_fraction_projection",
            "campaign_budget_projection",
        },
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
    _record(
        checks,
        "design_uses_o34_universal_attempt",
        "There is no admission predictor or solver-specific admission region."
        in design_words
        and "every solver attempts every task" in design_words
        and "Matt pins one final uniform cap at gate 3" in design_words
        and "No admission ledger is produced." in design_words,
    )

    pilot_contract = contract.get("pilot_design", {})
    manifest_path = root / pilot_contract.get("task_manifest_path", "")
    pilot_design_path = root / pilot_contract.get("design_path", "")
    _record(checks, "pilot_manifest_path", manifest_path == root / PILOT_MANIFEST_PATH)
    _record(checks, "pilot_design_path", pilot_design_path == root / PILOT_DESIGN_PATH)
    _record(
        checks,
        "pilot_files_exist",
        manifest_path.is_file() and pilot_design_path.is_file(),
    )
    manifest_sha = _sha256(manifest_input_path)
    _record(
        checks,
        "pilot_manifest_hash_bound",
        pilot_contract.get("task_manifest_sha256") == manifest_sha
        and pilot_design.get("common_protocol", {}).get("manifest_sha256")
        == manifest_sha,
    )
    _record(
        checks,
        "pilot_status_held",
        contract.get("status")
        == "pilot_design_submitted_execution_held_for_pi_design_review"
        and pilot_contract.get("status") == "submitted_for_pi_review_execution_held"
        and pilot_contract.get("execution_authorized") is False
        and pilot_manifest.get("status") == "design_only_submission_held"
        and pilot_design.get("status")
        == "pilot_design_submitted_for_pi_review_execution_held",
    )
    authorization = pilot_design.get("authorization", {})
    _record(
        checks,
        "all_execution_forbidden",
        authorization.get("pilot_execution_authorized") is False
        and authorization.get("production_execution_authorized") is False
        and authorization.get("qsub_permitted") is False
        and authorization.get("ipie_swing_submission_permitted") is False,
    )

    pilot_tasks = pilot_manifest.get("pilot_tasks", [])
    task_uuids = [item.get("task_uuid") for item in pilot_tasks]
    families = [item.get("family_group") for item in pilot_tasks]
    _record(
        checks,
        "pilot_task_count",
        pilot_manifest.get("pilot_task_count") == 12
        and pilot_contract.get("pilot_task_count") == 12
        and pilot_design.get("common_protocol", {}).get("pilot_task_count") == 12
        and len(pilot_tasks) == 12,
    )
    _record(checks, "pilot_task_uuid_unique", len(set(task_uuids)) == 12)
    _record(checks, "pilot_family_unique", len(set(families)) == 12)
    canonical_families = []
    canonical_bindings_valid = True
    for item in pilot_tasks:
        try:
            canonical_families.append(
                canonical_problem_family(
                    str(item.get("problem_instance_short_name", "")),
                    task_uuid=str(item.get("task_uuid", "")),
                )
            )
        except (KeyError, ValueError):
            canonical_bindings_valid = False
            canonical_families.append(None)
    _record(checks, "pilot_task_binding_canonical", canonical_bindings_valid)
    _record(
        checks,
        "pilot_family_mapping_canonical",
        all(
            item.get("family_group") == family
            and item.get("family_group_source")
            == CANONICAL_FAMILY_ARTIFACT_PATH.as_posix()
            for item, family in zip(pilot_tasks, canonical_families, strict=True)
        ),
    )
    _record(
        checks,
        "pilot_canonical_family_unique",
        canonical_bindings_valid
        and len(canonical_families) == 12
        and len(set(canonical_families)) == 12,
    )
    _record(
        checks,
        "pilot_validation_family_at_most_one",
        sum(
            str(item.get("problem_instance_short_name", "")).startswith("validation.")
            for item in pilot_tasks
        )
        <= 1,
    )
    _record(
        checks,
        "pilot_selection_order",
        [item.get("selection_rank") for item in pilot_tasks] == list(range(1, 13)),
    )
    corpus = pilot_manifest.get("corpus", {})
    _record(
        checks,
        "pilot_corpus_bound",
        corpus.get("task_count") == 718
        and corpus.get("feature_table_path") == FEATURES_PATH.as_posix()
        and corpus.get("feature_table_sha256") == _sha256(root / FEATURES_PATH),
    )
    selection = pilot_manifest.get("selection", {})
    _record(
        checks,
        "pilot_family_artifact_bound",
        selection.get("family_artifact_path")
        == CANONICAL_FAMILY_ARTIFACT_PATH.as_posix()
        and selection.get("family_artifact_sha256") == EXPECTED_ARTIFACT_SHA256
        and _sha256(root / CANONICAL_FAMILY_ARTIFACT_PATH)
        == EXPECTED_ARTIFACT_SHA256,
    )
    _record(
        checks,
        "pilot_selection_target_blind",
        pilot_manifest.get("schema_version") == 3
        and selection.get("algorithm_id") == "rank_scaled_maximin_unique_family_v1"
        and selection.get("family_constraint")
        == "one_task_per_canonical_problem_family"
        and selection.get("family_mapping_function") == "canonical_problem_family"
        and selection.get("family_mapping_module")
        == "qb_gsee_benchmark.canonical_families"
        and selection.get("family_mapping_rule")
        == "task_uuid lookup of canonical_family_recommended in canonical_families_v1.json"
        and selection.get("tie_break") == "lexicographically_smallest_task_uuid",
    )
    serialized_tasks = json.dumps(pilot_tasks, sort_keys=True).lower()
    _record(
        checks,
        "pilot_manifest_forbidden_fields_absent",
        all(token not in serialized_tasks for token in FORBIDDEN_PILOT_TOKENS),
    )

    input_records_valid = True
    for item in pilot_tasks:
        instance_path = root / item.get("problem_instance_path", "")
        if not instance_path.is_file() or item.get(
            "problem_instance_sha256"
        ) != _sha256(instance_path):
            input_records_valid = False
            continue
        instance = json.loads(instance_path.read_text(encoding="utf-8"))
        if instance.get("short_name") != item.get("problem_instance_short_name"):
            input_records_valid = False
        if instance.get("problem_instance_uuid") != item.get("problem_instance_uuid"):
            input_records_valid = False
        matching_tasks = [
            task
            for task in instance.get("tasks", [])
            if task.get("task_uuid") == item.get("task_uuid")
        ]
        if len(matching_tasks) != 1:
            input_records_valid = False
            continue
        fcidumps = [
            record
            for record in matching_tasks[0].get("supporting_files", [])
            if record.get("is_fcidump_file") is True
        ]
        expected_fcidump = item.get("fcidump", {})
        if len(fcidumps) != 1 or any(
            fcidumps[0].get(key) != value for key, value in expected_fcidump.items()
        ):
            input_records_valid = False
    _record(checks, "pilot_input_records_hash_bound", input_records_valid)

    common = pilot_design.get("common_protocol", {})
    calibration = pilot_design.get("calibration_contract", {})
    _record(
        checks,
        "pilot_production_isolation",
        common.get("campaign_identity_relation")
        == "pilot identities are distinct from clean-slate production identities"
        and calibration.get("pilot_artifact_reuse_in_production") is False
        and calibration.get("pilot_checkpoint_reuse_in_production") is False
        and calibration.get("pilot_energy_reuse_in_production") is False
        and calibration.get("energy_fields_visible_to_calibrator") is False,
    )
    _record(
        checks,
        "calibration_forbidden_inputs",
        set(calibration.get("forbidden_inputs", [])) == FORBIDDEN_PILOT_TOKENS,
    )
    pilot_cap = calibration.get("uniform_cap", {})
    _record(
        checks,
        "pilot_universal_attempt_calibration",
        calibration.get("admission_prediction_permitted") is False
        and calibration.get("production_attempt_scope") == "all_718_tasks_per_solver"
        and "admission_inputs" not in calibration
        and "production_admission_policy" not in calibration
        and pilot_cap.get("working_hours_per_task") == 12
        and pilot_cap.get("final_hours_per_task") == "TBD_AT_GATE_3"
        and pilot_cap.get("pinned_by") == "Matt"
        and pilot_cap.get("not_attempted_permitted") is False
        and pilot_cap.get("timeout_status") == "timeout"
        and pilot_cap.get("timeout_scored_as_success") is False,
    )
    _record(
        checks,
        "pilot_cap_projection_outputs",
        set(calibration.get("production_outputs_required_before_gate_3_closure", []))
        == {
            "exact solver configuration locks",
            "measured pilot walltime distributions",
            "measured pilot peak-memory distributions",
            "timeout-fraction projection at the recommended uniform cap",
            "campaign-budget projection at the recommended uniform cap",
            "one uniform per-task cap recommendation for all four solvers",
            "failure and timeout inventory",
            "v1.9 designation skeletons still marked not_designated",
        },
    )
    execution = pilot_design.get("improv_execution_shape", {})
    _record(
        checks,
        "improv_whole_node_compute",
        execution.get("account") == "QC_NA_Sim"
        and execution.get("primary_queue") == "compute"
        and execution.get("debug_queue_permitted") is False
        and execution.get("select") == "select=4:ncpus=128"
        and execution.get("ncpus_per_node") == 128
        and execution.get("nodes_per_campaign") == 4
        and execution.get("explicit_memory_request") is False
        and execution.get("pbs_walltime") == "03:30:00",
    )
    _record(
        checks,
        "pilot_cost_caps",
        common.get("walltime_seconds_per_task") == 3600
        and execution.get("cpu_campaign_hard_cap_node_hours_each") == 14
        and execution.get("total_cpu_pilot_hard_cap_node_hours") == 42,
    )

    solvers = pilot_design.get("solvers", {})
    _record(checks, "pilot_solver_set", set(solvers) == EXPECTED_SOLVERS)
    production_ids = {item.get("campaign_id") for item in campaigns}
    pilot_ids = {item.get("campaign_id") for item in solvers.values()}
    _record(
        checks,
        "pilot_campaign_ids_separate",
        len(pilot_ids) == 4
        and not pilot_ids.intersection(production_ids)
        and {item.get("production_campaign_id") for item in solvers.values()}
        == production_ids,
    )
    ipie = solvers.get("ipie_uhf_trial", {})
    _record(
        checks,
        "ipie_a_pilot_pin",
        ipie.get("selected_option") == "iPIE-A"
        and ipie.get("num_walkers") == 512
        and ipie.get("num_blocks") == 1000
        and ipie.get("num_steps_per_block") == 25
        and ipie.get("timestep") == 0.005
        and ipie.get("trial_wavefunction") == "UHF"
        and ipie.get("swing_pilot_hard_cap_a100_hours") == 12,
    )
    dmrg = solvers.get("DMRG", {})
    _record(
        checks,
        "dmrg_a_pilot_pin",
        dmrg.get("selected_option") == "DMRG-A"
        and dmrg.get("bond_dimension_ladder") == [256, 512, 1024, 2048]
        and dmrg.get("sweeps_per_rung") == [4, 4, 6, 8]
        and dmrg.get("completed_rung_retention")
        == "every completed rung retained as a separate nested observation",
    )
    trimci = solvers.get("TrimCI", {})
    _record(
        checks,
        "trimci_a_pilot_pin",
        trimci.get("selected_option") == "TrimCI-A"
        and trimci.get("fe_extension_required") is True
        and trimci.get("phase0_candidate_count") == 64
        and trimci.get("determinant_ceiling") == 10_000_000
        and trimci.get("checkpoint_determinant_grid")
        == [100_000, 250_000, 500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000]
        and trimci.get("snapshot_semantics")
        == "observation_only; no snapshot may alter search decisions, phase caps, or FE execution",
    )
    shci = solvers.get("SHCI", {})
    _record(
        checks,
        "shci_a_pilot_pin",
        shci.get("selected_option") == "SHCI-A"
        and shci.get("eps_var_ladder") == [2e-4, 1e-4, 5e-5, 2e-5]
        and shci.get("pt_policy")
        == "variational energy at every rung; stochastic PT only at terminal eps_var=2e-5",
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
    parser.add_argument("--pilot-manifest", type=Path, default=PILOT_MANIFEST_PATH)
    args = parser.parse_args()
    report = verify(args.root.resolve(), args.pilot_manifest)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
