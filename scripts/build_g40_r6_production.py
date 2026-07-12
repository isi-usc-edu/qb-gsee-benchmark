#!/usr/bin/env python3
"""Additively merge G40 R6 degeneracy diagnostics into the feature table."""

from __future__ import annotations

import argparse
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
VERSION = "g40_orderability_degeneracy_v1"
EXPECTED_COLUMNS = [
    "orderability_degeneracy_features_version",
    "orderability_fiedler_min_coordinate_gap",
    "orderability_laplacian_lambda23_relative_split",
    "orderability_laplacian_lambda23_split_applicable",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--accounting", type=Path, required=True)
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
        default=ROOT / "analysis/feature_schema/g40_r6_production_report",
    )
    args = parser.parse_args()

    paths = sorted(args.state_dir.glob("*.orderability-degeneracy.json"))
    states = [json.loads(path.read_text()) for path in paths]
    corpus = _corpus_metadata(args.problem_instances)
    state_ids = [state["task_uuid"] for state in states]
    if len(state_ids) != len(set(state_ids)) or set(state_ids) != set(corpus):
        raise ValueError("R6 states do not exactly match the corpus")
    if any(state["status"] != "success" for state in states):
        raise ValueError("R6 contains failed states")
    if {state["extractor_version"] for state in states} != {VERSION}:
        raise ValueError("unexpected R6 extractor version")
    if sorted(states[0]["features"]) != EXPECTED_COLUMNS:
        raise ValueError("unexpected R6 columns")

    fields, rows = _read_table(args.feature_table)
    input_sha256 = _sha256(args.feature_table)
    rows_by_uuid = {row["task_uuid"]: row for row in rows}
    if set(rows_by_uuid) != set(corpus):
        raise ValueError("feature table does not exactly match the corpus")
    new_columns = sorted(set(EXPECTED_COLUMNS) - set(fields))
    fields.extend(new_columns)
    populated = changed = 0
    for state in states:
        row = rows_by_uuid[state["task_uuid"]]
        for column in EXPECTED_COLUMNS:
            old = row.get(column, "")
            new = _value_text(state["features"][column])
            if old and old != new:
                changed += 1
            elif not old and new:
                populated += 1
            row[column] = new
    if changed:
        raise ValueError(f"R6 changed {changed} populated cells")
    _write_table(args.feature_table, fields, rows)
    pbs = _pbs_accounting(args.accounting)
    if pbs["exit_status"] != 0:
        raise ValueError("nonzero PBS exit in R6 provenance")
    report = {
        "report_version": "g40_r6_production_v1",
        "code_revision": args.code_revision,
        "extractor_version": VERSION,
        "corpus_tasks": len(corpus),
        "successful_states": len(states),
        "rows_before": len(rows),
        "rows_after": len(rows),
        "columns_before": len(fields) - len(new_columns),
        "columns_after": len(fields),
        "new_columns": new_columns,
        "newly_populated_cells": populated,
        "changed_populated_cells": 0,
        "input_feature_table_sha256": input_sha256,
        "output_feature_table_sha256": _sha256(args.feature_table),
        "state_ledger_sha256": _state_ledger(paths),
        "pbs": pbs,
        "accounting_sha256": _sha256(args.accounting),
        "stdout_log_sha256": _sha256(args.stdout_log),
        "stderr_log_sha256": _sha256(args.stderr_log),
        "job_script_sha256": _sha256(args.job_script),
    }
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    args.output_prefix.with_suffix(".json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    args.output_prefix.with_suffix(".md").write_text(
        "\n".join(
            [
                "# G40 R6 production report",
                "",
                f"- States: **{len(states)}/{len(corpus)}** successful.",
                f"- Table: **{len(rows)} x {report['columns_before']}** to **{len(rows)} x {len(fields)}**.",
                f"- New populated cells: **{populated}**; changed populated cells: **0**.",
                f"- PBS `{pbs['job_id']}`: exit {pbs['exit_status']} on `{pbs['queue']}`.",
                f"- Output table SHA-256: `{report['output_feature_table_sha256']}`.",
                "",
            ]
        )
    )
    print(
        json.dumps(
            {
                "rows": len(rows),
                "columns": len(fields),
                "table_sha256": report["output_feature_table_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
