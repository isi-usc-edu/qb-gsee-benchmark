#!/usr/bin/env python3
"""Validate and additively merge completed G40 P2 MFPROTO states."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.features.corpus_runner import load_corpus_fcidumps
from scripts.build_g40_p2_pilot_report import (
    _memory_kb,
    _pbs_accounting,
    _sha256,
    _tie_audit_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TABLE = ROOT / "scripts" / "Hamiltonian_features.csv"

# MFPROTO-v3 returned early at this exact shape when all eight SCF branches
# failed to converge. The production states remain immutable; the harvester
# expands only this known shape to the frozen contract with null child-panel
# values. Any other partial shape remains a hard failure.
NO_CONVERGED_SCF_FEATURE_COLUMNS = frozenset(
    {
        "mf_branch_count",
        "mf_converged_branch_count",
        "mf_core_gap_alpha_applicable",
        "mf_core_gap_alpha_hartree",
        "mf_core_gap_alpha_reason",
        "mf_core_gap_beta_applicable",
        "mf_core_gap_beta_hartree",
        "mf_core_gap_beta_reason",
        "mf_core_gap_min_applicable",
        "mf_core_gap_min_hartree",
        "mf_core_gap_min_reason",
        "mf_distinct_solution_count",
        "mf_hf_variance_applicable",
        "mf_hf_variance_reason",
        "mf_lowest_rhf_energy_hartree",
        "mf_lowest_uhf_energy_hartree",
        "mf_selected_applicable",
        "mf_selected_energy_hartree",
        "mf_selected_guess",
        "mf_selected_method",
        "mf_selected_reason",
        "mf_selected_s2",
        "mf_solution_energy_spread_hartree",
        "mf_solution_energy_spread_per_electron_hartree",
        "mf_stability_applicable",
        "mf_stability_reason",
        "mf_symmetry_breaking_applicable",
        "mf_symmetry_breaking_energy_hartree",
        "mf_symmetry_breaking_energy_per_electron",
        "mf_symmetry_breaking_reason",
        "mf_tie_core_degenerate_subspace_count",
        "mf_tie_core_hysteresis_band_split_count",
        "mf_tie_core_minimum_adjacent_split",
        "mf_tie_core_projected_index_tied_subspace_count",
        "mf_tie_g1_alpha_boundary_tie",
        "mf_tie_g1_beta_boundary_tie",
        "mf_tie_g2_alpha_boundary_tie",
        "mf_tie_g2_beta_boundary_tie",
        "mf_tie_g3_alpha_boundary_tie",
        "mf_tie_g3_beta_boundary_tie",
        "mf_tie_selected_fock_alpha_boundary_tie",
        "mf_tie_selected_fock_alpha_degenerate_subspace_count",
        "mf_tie_selected_fock_alpha_hysteresis_band_split_count",
        "mf_tie_selected_fock_alpha_minimum_adjacent_split",
        "mf_tie_selected_fock_alpha_projected_index_tied_subspace_count",
        "mf_tie_selected_fock_beta_boundary_tie",
        "mf_tie_selected_fock_beta_degenerate_subspace_count",
        "mf_tie_selected_fock_beta_hysteresis_band_split_count",
        "mf_tie_selected_fock_beta_minimum_adjacent_split",
        "mf_tie_selected_fock_beta_projected_index_tied_subspace_count",
        "mf_tie_selection_energy_tie_tolerance_hartree",
        "mf_tie_selection_method_order",
        "mfproto_dense_eri_seconds",
        "mfproto_features_version",
        "mfproto_scf_seconds",
        "mfproto_total_seconds",
        "mp2_applicable",
        "mp2_reason",
    }
)


def _contract_features(
    state: dict[str, Any], feature_columns: list[str]
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    task_uuid = state.get("task_uuid")
    features = state.get("features")
    if not isinstance(features, dict):
        raise ValueError(f"production state has invalid features: {task_uuid}")
    contract_columns = set(feature_columns)
    observed_columns = set(features)
    if observed_columns == contract_columns:
        return features, None
    if observed_columns != NO_CONVERGED_SCF_FEATURE_COLUMNS:
        raise ValueError(f"production state violates P2 contract: {task_uuid}")

    audit = state.get("audit")
    branch_outcomes = audit.get("branch_outcomes") if isinstance(audit, dict) else None
    expected_values = {
        "mf_branch_count": 8,
        "mf_converged_branch_count": 0,
        "mf_distinct_solution_count": 0,
        "mf_selected_applicable": False,
        "mf_selected_reason": "no_converged_scf_branch",
        "mf_stability_applicable": False,
        "mf_stability_reason": "no_converged_scf_branch",
        "mf_hf_variance_applicable": False,
        "mf_hf_variance_reason": "no_converged_scf_branch",
        "mp2_applicable": False,
        "mp2_reason": "no_converged_scf_branch",
    }
    valid_audit = (
        isinstance(audit, dict)
        and audit.get("selected_branch_index") is None
        and isinstance(branch_outcomes, list)
        and len(branch_outcomes) == 8
        and all(
            isinstance(branch, dict) and branch.get("converged") is False
            for branch in branch_outcomes
        )
    )
    if not valid_audit or any(
        features.get(column) != value for column, value in expected_values.items()
    ):
        raise ValueError(
            f"partial P2 state lacks no-converged-SCF evidence: {task_uuid}"
        )

    missing_columns = sorted(contract_columns - observed_columns)
    normalized = {column: features.get(column) for column in feature_columns}
    return normalized, {
        "task_uuid": task_uuid,
        "reason": "no_converged_scf_branch",
        "observed_feature_columns": len(observed_columns),
        "null_filled_contract_columns": len(missing_columns),
        "raw_state_unchanged": True,
    }


def _value_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"missing header in {path}")
        return list(reader.fieldnames), list(reader)


def _table_bytes(fields: list[str], rows: list[dict[str, str]]) -> bytes:
    from io import StringIO

    handle = StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode("utf-8")


def _state_ledger(paths: list[Path]) -> tuple[list[dict[str, str]], str]:
    entries = [{"path": path.name, "sha256": _sha256(path)} for path in paths]
    encoded = "".join(f"{item['sha256']}  {item['path']}\n" for item in entries).encode(
        "ascii"
    )
    return entries, hashlib.sha256(encoded).hexdigest()


def _mask_reason_counts(states: list[dict[str, Any]]) -> dict[str, int]:
    reasons = Counter(
        str(value)
        for state in states
        for key, value in state["features"].items()
        if key.endswith("_reason") and value
    )
    return dict(sorted(reasons.items()))


def _markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {report['report_title']}",
            "",
            "## Result",
            "",
            f"- Status: **{report['status']}**.",
            (
                f"- Corpus states merged: **{report['successful_states']}/"
                f"{report['corpus_tasks']}**."
            ),
            (
                f"- Feature table: **{report['rows_before']} x "
                f"{report['columns_before']}** to **{report['rows_after']} x "
                f"{report['columns_after']}**."
            ),
            f"- New columns: **{len(report['new_columns'])}**.",
            (
                "- Contract-shape compatibility rows: "
                f"**{len(report['contract_shape_compatibility'])}** "
                "(no-converged-SCF child panels null-filled; raw states unchanged)."
            ),
            f"- Newly populated cells: **{report['newly_populated_cells']}**.",
            (
                "- Existing populated P2 cells audited: "
                f"**{report['existing_populated_cells_audited']}**."
            ),
            "- Changed populated cells: **0**.",
            (
                f"- PBS jobs: **{report['pbs_gate']['successful_jobs']}/"
                f"{report['pbs_gate']['jobs']}** successful; actual allocation "
                f"**{report['pbs_gate']['node_hours']:.3f} node-hours**."
            ),
            (
                "- Representation gate: "
                f"**{report['representation_pair_check']['status']}** "
                f"({report['representation_pair_check']['groups_passed']}/"
                f"{report['representation_pair_check']['equivalence_groups']})."
            ),
            f"- Output table SHA-256: `{report['output_feature_table_sha256']}`.",
            "",
            "The merge is additive and corpus-manifest-driven. It changes no problem",
            "instance, reference, solution record, solver harness, or S3 object.",
            "",
        ]
    )


def _validate_bundle_evidence(
    plan: dict[str, Any], plan_path: Path
) -> list[dict[str, str]]:
    ledger = plan.get("artifacts", {}).get("bundle_evidence")
    expected = {
        "evidence/cold_tests.junit.xml",
        "evidence/mock_submission.log",
        "evidence/improv_preflight.log",
    }
    if (
        not isinstance(ledger, list)
        or any(not isinstance(item, dict) for item in ledger)
        or {item.get("path") for item in ledger} != expected
    ):
        raise ValueError("production plan lacks the required bundle evidence ledger")
    for item in ledger:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("bundle evidence path escapes the production bundle")
        path = plan_path.parent / relative
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise ValueError(f"bundle evidence checksum mismatch: {relative}")
    return ledger


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--state-pattern", default="*.mfproto.json")
    parser.add_argument("--extractor-version", required=True)
    parser.add_argument("--extractor-code-revision", required=True)
    parser.add_argument("--builder-revision", required=True)
    parser.add_argument("--verifier-code-revision", required=True)
    parser.add_argument("--feature-table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument(
        "--problem-instances", type=Path, default=ROOT / "problem_instances"
    )
    parser.add_argument("--feature-contract", type=Path, required=True)
    parser.add_argument("--pilot-report", type=Path, required=True)
    parser.add_argument("--production-plan", type=Path, required=True)
    parser.add_argument("--representation-check", type=Path, required=True)
    parser.add_argument("--accounting", type=Path, action="append", required=True)
    parser.add_argument("--stdout-log", type=Path, action="append", required=True)
    parser.add_argument("--stderr-log", type=Path, action="append", required=True)
    parser.add_argument("--job-script", type=Path, action="append", required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    parser.add_argument("--plan-version", default="g40_p2_production_plan_v2")
    parser.add_argument("--report-version", default="g40_p2_production_v1")
    parser.add_argument("--report-title", default="G40 P2 MFPROTO-v3 production report")
    parser.add_argument("--maximum-node-hours", type=float)
    args = parser.parse_args()
    report_path = args.output_prefix.with_suffix(".json")
    previous = json.loads(report_path.read_text()) if report_path.exists() else {}

    contract = json.loads(args.feature_contract.read_text())
    if contract.get("contract_version") != "g40_p2_feature_contract_v3":
        raise ValueError("unexpected P2 feature contract")
    feature_columns = list(contract["output_columns"])
    if len(feature_columns) != len(set(feature_columns)):
        raise ValueError("duplicate P2 contract column")

    pilot = json.loads(args.pilot_report.read_text())
    if pilot.get("status") != "passed":
        raise ValueError("production requires a passed P2 pilot")
    if (
        pilot["extractor_version"] != args.extractor_version
        or pilot["code_revision"] != args.extractor_code_revision
        or pilot["output_contract"]["sha256"] != _sha256(args.feature_contract)
    ):
        raise ValueError("production extractor or contract differs from passed pilot")

    records = load_corpus_fcidumps(args.problem_instances)
    records_by_uuid = {record.task_uuid: record for record in records}
    plan = json.loads(args.production_plan.read_text())
    if plan.get("plan_version") != args.plan_version:
        raise ValueError("unexpected production plan version")
    bundle_evidence = _validate_bundle_evidence(plan, args.production_plan)
    if (
        plan["extractor_version"] != args.extractor_version
        or plan["extractor_code_revision"] != args.extractor_code_revision
        or plan["configuration"] != pilot["configuration"]
        or plan["artifacts"]["pilot_report_sha256"] != _sha256(args.pilot_report)
        or plan["artifacts"]["feature_contract_sha256"]
        != _sha256(args.feature_contract)
    ):
        raise ValueError("production plan pins do not match inputs")
    planned_table_sha256 = plan["artifacts"]["input_feature_table_sha256"]
    current_or_original_table_sha256 = previous.get(
        "input_feature_table_sha256", _sha256(args.feature_table)
    )
    if planned_table_sha256 != current_or_original_table_sha256:
        raise ValueError("production plan was built against another feature table")
    plan_tasks = {item["task_uuid"]: item for item in plan["tasks"]}
    if set(plan_tasks) != set(records_by_uuid) or plan["corpus_tasks"] != len(records):
        raise ValueError("production plan does not exactly match the live corpus")
    for task_uuid, record in records_by_uuid.items():
        if plan_tasks[task_uuid]["manifest_signature"] != record.signature():
            raise ValueError(f"production plan manifest drift for {task_uuid}")

    state_paths = sorted(args.state_dir.glob(args.state_pattern))
    states = [json.loads(path.read_text()) for path in state_paths]
    state_ids = [state.get("task_uuid") for state in states]
    mismatched_filenames = [
        path.name
        for path, state in zip(state_paths, states)
        if path.name != f"{state.get('task_uuid')}.mfproto.json"
    ]
    if mismatched_filenames:
        raise ValueError(
            "production state filenames do not match task UUIDs: "
            f"{mismatched_filenames}"
        )
    if len(state_ids) != len(set(state_ids)):
        raise ValueError("duplicate production task state")
    if set(state_ids) != set(records_by_uuid):
        raise ValueError("production states do not exactly match the live corpus")
    configuration = pilot["configuration"]
    features_by_uuid: dict[str, dict[str, Any]] = {}
    contract_shape_compatibility: list[dict[str, Any]] = []
    for state in states:
        task_uuid = state["task_uuid"]
        record = records_by_uuid[task_uuid]
        expected = {
            "status": "success",
            "task_uuid": task_uuid,
            "instance_data_object_uuid": record.instance_data_object_uuid,
            "source_url": record.url,
            "declared_checksum": record.checksum,
            "declared_checksum_type": record.checksum_type,
            "manifest_signature": record.signature(),
            "manifest_ms2_metadata": record.ms2_metadata,
            "extractor_version": args.extractor_version,
            "code_revision": args.extractor_code_revision,
            "configuration": configuration,
        }
        mismatches = {
            key: {"expected": value, "observed": state.get(key)}
            for key, value in expected.items()
            if state.get(key) != value
        }
        if mismatches:
            raise ValueError(f"invalid production state {task_uuid}: {mismatches}")
        source_sha256 = state.get("source_sha256")
        if (
            not isinstance(source_sha256, str)
            or len(source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in source_sha256.lower()
            )
        ):
            raise ValueError(
                f"production state has invalid source SHA-256: {task_uuid}"
            )
        normalized_features, compatibility = _contract_features(state, feature_columns)
        features_by_uuid[task_uuid] = normalized_features
        if compatibility is not None:
            contract_shape_compatibility.append(compatibility)

    representation = json.loads(args.representation_check.read_text())
    if (
        representation.get("status") != "passed"
        or representation.get("code_revision") != args.verifier_code_revision
        or representation.get("permutation_blocks") != ["mfproto"]
    ):
        raise ValueError("production representation-pair check failed or is unpinned")

    accounting = [_pbs_accounting(path) for path in args.accounting]
    if len({item["job_id"] for item in accounting}) != len(accounting):
        raise ValueError("duplicate PBS accounting job")
    failed_jobs = sorted(
        item["job_id"]
        for item in accounting
        if item["job_state"] != "F"
        or item["exit_status"] != 0
        or item["queue"] not in {"compute", "backfill"}
        or item["ncpus"] != 128
    )
    if failed_jobs:
        raise ValueError(f"failed or unauthorized PBS production jobs: {failed_jobs}")
    if len(args.stdout_log) != len(accounting) or len(args.stderr_log) != len(
        accounting
    ):
        raise ValueError("every PBS job must have one stdout and stderr artifact")

    fields, rows = _read_table(args.feature_table)
    rows_by_uuid = {row["task_uuid"]: row for row in rows}
    if len(rows_by_uuid) != len(rows) or set(rows_by_uuid) != set(records_by_uuid):
        raise ValueError("feature table does not exactly match the live corpus")
    input_sha256 = previous.get(
        "input_feature_table_sha256", _sha256(args.feature_table)
    )
    rows_before = previous.get("rows_before", len(rows))
    columns_before = previous.get("columns_before", len(fields))
    current_new_columns = [column for column in feature_columns if column not in fields]
    new_columns = previous.get("new_columns", current_new_columns)
    fields.extend(current_new_columns)

    audited = 0
    newly_populated = 0
    for task_uuid in sorted(features_by_uuid):
        row = rows_by_uuid[task_uuid]
        features = features_by_uuid[task_uuid]
        for column in feature_columns:
            old_value = row.get(column, "")
            new_value = _value_text(features[column])
            if old_value:
                audited += 1
                if old_value != new_value:
                    raise ValueError(
                        f"changed populated cell {task_uuid} {column}: "
                        f"{old_value!r} -> {new_value!r}"
                    )
            elif new_value:
                newly_populated += 1
            row[column] = new_value

    table_bytes = _table_bytes(fields, rows)
    output_sha256 = hashlib.sha256(table_bytes).hexdigest()
    state_ledger, state_ledger_sha256 = _state_ledger(state_paths)
    pbs_node_hours = sum(item["walltime_seconds"] for item in accounting) / 3600.0
    if args.maximum_node_hours is not None and pbs_node_hours > args.maximum_node_hours:
        raise ValueError(
            "actual PBS allocation exceeds cap: "
            f"{pbs_node_hours:.6f} > {args.maximum_node_hours:.6f} node-hours"
        )
    task_walltimes = [float(state["walltime_seconds"]) for state in states]
    maximum_rss_gb = (
        max(float(state["process_peak_rss_kb"]) for state in states) / 1024**2
    )
    maximum_pbs_memory_gb = (
        max(_memory_kb(item["memory"]) for item in accounting) / 1024**2
    )
    report = {
        "report_version": args.report_version,
        "report_title": args.report_title,
        "status": "passed",
        "extractor_version": args.extractor_version,
        "extractor_code_revision": args.extractor_code_revision,
        "builder_revision": args.builder_revision,
        "verifier_code_revision": args.verifier_code_revision,
        "configuration": configuration,
        "corpus_tasks": len(records),
        "successful_states": len(states),
        "rows_before": rows_before,
        "columns_before": columns_before,
        "rows_after": len(rows),
        "columns_after": len(fields),
        "new_columns": new_columns,
        "newly_populated_cells": previous.get("newly_populated_cells", newly_populated),
        "existing_populated_cells_audited": previous.get(
            "existing_populated_cells_audited", audited
        ),
        "changed_populated_cells": 0,
        "contract_shape_compatibility": contract_shape_compatibility,
        "input_feature_table_sha256": input_sha256,
        "output_feature_table_sha256": output_sha256,
        "feature_contract_sha256": _sha256(args.feature_contract),
        "pilot_report_sha256": _sha256(args.pilot_report),
        "production_plan_sha256": _sha256(args.production_plan),
        "bundle_evidence": bundle_evidence,
        "state_ledger_sha256": state_ledger_sha256,
        "state_ledger": state_ledger,
        "task_timing_seconds": {
            "sum": sum(task_walltimes),
            "median": statistics.median(task_walltimes),
            "maximum": max(task_walltimes),
        },
        "maximum_process_peak_rss_gb": maximum_rss_gb,
        "mask_reason_counts": _mask_reason_counts(states),
        "tie_audit_ledger": _tie_audit_ledger(states),
        "representation_pair_check": {
            **{
                key: representation[key]
                for key in ("status", "equivalence_groups", "groups_passed")
            },
            "sha256": _sha256(args.representation_check),
        },
        "pbs_gate": {
            "status": "passed",
            "jobs": len(accounting),
            "successful_jobs": len(accounting),
            "node_hours": pbs_node_hours,
            "maximum_memory_gb": maximum_pbs_memory_gb,
        },
        "pbs_jobs": accounting,
        "stdout_logs": [
            {"path": path.name, "sha256": _sha256(path)} for path in args.stdout_log
        ],
        "stderr_logs": [
            {"path": path.name, "sha256": _sha256(path)} for path in args.stderr_log
        ],
        "job_scripts": [
            {"path": path.name, "sha256": _sha256(path)} for path in args.job_script
        ],
    }

    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    temporary_table = args.feature_table.with_suffix(
        args.feature_table.suffix + ".partial"
    )
    temporary_table.write_bytes(table_bytes)
    os.replace(temporary_table, args.feature_table)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output_prefix.with_suffix(".md").write_text(_markdown(report))
    print(
        json.dumps(
            {
                "rows": len(rows),
                "columns": len(fields),
                "new_columns": len(new_columns),
                "table_sha256": output_sha256,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
