#!/usr/bin/env python3
"""Additively merge the G40 R1/R4 audit flags into the feature table."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.build_g40_p1a_production import _corpus_metadata
from scripts.build_g40_p1bc_pilot_report import _pbs_accounting, _sha256
from scripts.build_g40_p1bc_production import (
    _read_table,
    _state_ledger,
    _value_text,
    _write_table,
)

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "scripts" / "Hamiltonian_features.csv"
VERSION = "g40_retag_audit_v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--accounting", type=Path, action="append", required=True)
    parser.add_argument("--stdout-log", type=Path, required=True)
    parser.add_argument("--stderr-log", type=Path, required=True)
    parser.add_argument("--job-script", type=Path, required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--feature-table", type=Path, default=TABLE)
    parser.add_argument(
        "--problem-instances", type=Path, default=ROOT / "problem_instances"
    )
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=ROOT / "analysis/feature_schema/g40_retag_audit_production_report",
    )
    args = parser.parse_args()

    paths = sorted(args.state_dir.glob("*.retag-audit.json"))
    states = [json.loads(path.read_text()) for path in paths]
    corpus = _corpus_metadata(args.problem_instances)
    state_ids = [state["task_uuid"] for state in states]
    if len(state_ids) != len(set(state_ids)) or set(state_ids) != set(corpus):
        raise ValueError("retag audit states do not exactly match the corpus")
    if any(state["status"] != "success" for state in states):
        raise ValueError("retag audit contains failed states")
    if {state["extractor_version"] for state in states} != {VERSION}:
        raise ValueError("unexpected retag audit extractor version")
    columns = sorted(states[0]["features"])
    if columns != [
        "det_coupling_reference_boundary_tie",
        "mpo_pair_rank_applicable",
        "retag_audit_features_version",
    ]:
        raise ValueError(f"unexpected retag audit columns: {columns}")

    report_path = args.output_prefix.with_suffix(".json")
    previous = json.loads(report_path.read_text()) if report_path.exists() else {}
    input_sha256 = previous.get("input_feature_table_sha256", _sha256(args.feature_table))
    fields, rows = _read_table(args.feature_table)
    rows_by_uuid = {row["task_uuid"]: row for row in rows}
    if set(rows_by_uuid) != set(corpus):
        raise ValueError("feature table does not exactly match the corpus")
    rows_before = previous.get("rows_before", len(rows))
    columns_before = previous.get("columns_before", len(fields))
    new_columns = previous.get("new_columns", sorted(set(columns) - set(fields)))
    fields.extend(sorted(set(columns) - set(fields)))
    populated = audited = 0
    for state in states:
        row = rows_by_uuid[state["task_uuid"]]
        for column in columns:
            old = row.get(column, "")
            new = _value_text(state["features"][column])
            if old:
                audited += 1
                if old != new:
                    raise ValueError(
                        f"changed populated cell {state['task_uuid']} {column}"
                    )
            elif new:
                populated += 1
            row[column] = new
    _write_table(args.feature_table, fields, rows)
    accounting = [_pbs_accounting(path) for path in args.accounting]
    if any(item["exit_status"] != 0 for item in accounting):
        raise ValueError("nonzero PBS exit in retag audit provenance")
    report = {
        "report_version": "g40_retag_audit_production_v1",
        "code_revision": args.code_revision,
        "extractor_version": VERSION,
        "corpus_tasks": len(corpus),
        "successful_states": len(states),
        "rows_before": rows_before,
        "rows_after": len(rows),
        "columns_before": columns_before,
        "columns_after": len(fields),
        "new_columns": new_columns,
        "newly_populated_cells": previous.get("newly_populated_cells", populated),
        "existing_populated_cells_audited": previous.get(
            "existing_populated_cells_audited", audited
        ),
        "changed_populated_cells": 0,
        "input_feature_table_sha256": input_sha256,
        "output_feature_table_sha256": _sha256(args.feature_table),
        "state_ledger_sha256": _state_ledger(paths),
        "pbs_jobs": accounting,
        "duplicate_submission_note": (
            "PBS jobs 7651548.imgt1 and 7651553.imgt1 were submitted 52 seconds "
            "apart against the same resume-safe state directory and shared log paths; "
            "both exited zero and the final checksum-bound states are ledgered here."
        ),
        "accounting_sha256": [_sha256(path) for path in args.accounting],
        "stdout_log_sha256": _sha256(args.stdout_log),
        "stderr_log_sha256": _sha256(args.stderr_log),
        "job_script_sha256": _sha256(args.job_script),
    }
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output_prefix.with_suffix(".md").write_text(
        "\n".join(
            [
                "# G40 retag-audit production report",
                "",
                f"- States: **{len(states)}/{len(corpus)}** successful.",
                f"- Table: **{rows_before} x {columns_before}** to **{len(rows)} x {len(fields)}**.",
                f"- New populated cells: **{report['newly_populated_cells']}**; changed populated cells: **0**.",
                "- PBS jobs: `7651548.imgt1`, `7651553.imgt1`; both exit 0 on `compute`.",
                f"- Output table SHA-256: `{report['output_feature_table_sha256']}`.",
                "",
                report["duplicate_submission_note"],
                "",
            ]
        )
    )
    print(json.dumps({"rows": len(rows), "columns": len(fields), "table_sha256": report["output_feature_table_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
