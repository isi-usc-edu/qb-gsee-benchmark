#!/usr/bin/env python3
"""Merge a completed G40 P1-B or P1-C state set into the feature table."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.build_g40_p1a_production import _corpus_metadata
from scripts.build_g40_p1bc_pilot_report import _pbs_accounting, _sha256

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TABLE = ROOT / "scripts" / "Hamiltonian_features.csv"
DEFAULT_OUTPUT = ROOT / "analysis" / "feature_schema"


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


def _write_table(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _state_ledger(paths: list[Path]) -> str:
    text = "".join(f"{_sha256(path)}  {path.name}\n" for path in paths)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {report['block'].upper()} production report",
            "",
            "## Result",
            "",
            f"- Corpus states merged: **{report['successful_states']}/{report['corpus_tasks']}**.",
            (
                f"- Feature table: **{report['rows_before']} x "
                f"{report['columns_before']}** to **{report['rows_after']} x "
                f"{report['columns_after']}**."
            ),
            f"- New columns: **{len(report['new_columns'])}**.",
            f"- Newly populated cells: **{report['newly_populated_cells']}**.",
            (
                "- Existing populated state-owned cells audited: "
                f"**{report['existing_populated_cells_audited']}**."
            ),
            "- Changed populated cells: **0**.",
            (
                f"- PBS `{report['pbs']['job_id']}` on `{report['pbs']['queue']}`: "
                f"exit {report['pbs']['exit_status']}, wall "
                f"{report['pbs']['walltime_seconds']} s, memory "
                f"`{report['pbs']['memory']}`."
            ),
            (
                "- G21 representation pairs: "
                f"**{report['representation_pair_check']['status']}** "
                f"({report['representation_pair_check']['groups_passed']}/"
                f"{report['representation_pair_check']['equivalence_groups']})."
            ),
            f"- Output table SHA-256: `{report['output_feature_table_sha256']}`.",
            "",
            "The merge is additive and corpus-manifest-driven. It changes no problem",
            "instance, reference, solution record, or solver harness.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--block", choices=("g40_p1b", "g40_p1c"), required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--state-pattern", required=True)
    parser.add_argument("--extractor-version", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--builder-revision", required=True)
    parser.add_argument("--feature-table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument(
        "--problem-instances", type=Path, default=ROOT / "problem_instances"
    )
    parser.add_argument("--pilot-report", type=Path, required=True)
    parser.add_argument("--representation-check", type=Path, required=True)
    parser.add_argument("--accounting", type=Path, required=True)
    parser.add_argument("--stdout-log", type=Path, required=True)
    parser.add_argument("--stderr-log", type=Path, required=True)
    parser.add_argument("--job-script", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()

    state_paths = sorted(args.state_dir.glob(args.state_pattern))
    states = [json.loads(path.read_text()) for path in state_paths]
    corpus = _corpus_metadata(args.problem_instances)
    state_ids = [state["task_uuid"] for state in states]
    if len(state_ids) != len(set(state_ids)):
        raise ValueError("duplicate production task state")
    if set(state_ids) != set(corpus):
        raise ValueError("production states do not exactly match the corpus manifest")
    failed = [state["task_uuid"] for state in states if state["status"] != "success"]
    if failed:
        raise ValueError(f"non-success production states: {failed}")
    versions = {state["extractor_version"] for state in states}
    if versions != {args.extractor_version}:
        raise ValueError(f"unexpected extractor versions: {versions}")
    feature_sets = {tuple(sorted(state["features"])) for state in states}
    if len(feature_sets) != 1:
        raise ValueError("production states have inconsistent feature columns")
    feature_columns = list(next(iter(feature_sets)))

    pilot = json.loads(args.pilot_report.read_text())
    if (
        pilot["status"] != "passed"
        or pilot["extractor_version"] != args.extractor_version
    ):
        raise ValueError("production extractor does not match a passed pilot")
    representation = json.loads(args.representation_check.read_text())
    if representation["status"] != "passed":
        raise ValueError("production representation-pair check failed")

    report_path = args.output_prefix.with_suffix(".json")
    previous = json.loads(report_path.read_text()) if report_path.exists() else {}
    input_sha256 = previous.get(
        "input_feature_table_sha256", _sha256(args.feature_table)
    )
    fields, rows = _read_table(args.feature_table)
    rows_by_uuid = {row["task_uuid"]: row for row in rows}
    if set(rows_by_uuid) != set(corpus) or len(rows_by_uuid) != len(rows):
        raise ValueError("feature table does not exactly match the corpus manifest")
    rows_before = previous.get("rows_before", len(rows))
    columns_before = previous.get("columns_before", len(fields))
    new_columns = sorted(set(feature_columns) - set(fields))
    fields.extend(new_columns)

    audited = 0
    newly_populated = 0
    for state in states:
        row = rows_by_uuid[state["task_uuid"]]
        for column in feature_columns:
            old_value = row.get(column, "")
            new_value = _value_text(state["features"][column])
            if old_value:
                audited += 1
                if old_value != new_value:
                    raise ValueError(
                        f"changed populated cell {state['task_uuid']} {column}: "
                        f"{old_value!r} -> {new_value!r}"
                    )
            elif new_value:
                newly_populated += 1
            row[column] = new_value

    _write_table(args.feature_table, fields, rows)
    report = {
        "report_version": "g40_p1bc_production_v1",
        "block": args.block,
        "code_revision": args.code_revision,
        "builder_revision": args.builder_revision,
        "extractor_version": args.extractor_version,
        "corpus_tasks": len(corpus),
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
        "input_feature_table_sha256": input_sha256,
        "output_feature_table_sha256": _sha256(args.feature_table),
        "state_ledger_sha256": _state_ledger(state_paths),
        "pilot_report_sha256": _sha256(args.pilot_report),
        "representation_pair_check": {
            key: representation[key]
            for key in ("status", "equivalence_groups", "groups_passed")
        },
        "pbs": _pbs_accounting(args.accounting),
        "stdout_log_sha256": _sha256(args.stdout_log),
        "stderr_log_sha256": _sha256(args.stderr_log),
        "job_script_sha256": _sha256(args.job_script),
        "accounting_sha256": _sha256(args.accounting),
    }
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.output_prefix.with_suffix(".md").write_text(_markdown(report))
    print(
        json.dumps(
            {
                "block": args.block,
                "rows": len(rows),
                "columns": len(fields),
                "new_columns": len(new_columns),
                "table_sha256": report["output_feature_table_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
