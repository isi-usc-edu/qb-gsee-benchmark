#!/usr/bin/env python3
"""Merge the completed G40 P1-A states into the public feature table."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TABLE = ROOT / "scripts" / "Hamiltonian_features.csv"
DEFAULT_OUTPUT = ROOT / "analysis" / "feature_schema"
ALLOWED_MIGRATIONS = {
    "log_fci_dim": "header_backed_log_fci_dim_rebuild",
    "eri_full_l1_norm": "canonical_eightfold_averaging_and_summation",
    "eri_full_l2_norm": "canonical_eightfold_averaging_and_summation",
    "two_body_unique_record_count": "canonical_eightfold_duplicate_definition",
    "two_body_duplicate_orientation_records_skipped": (
        "canonical_eightfold_duplicate_definition"
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _value_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _load_states(state_dir: Path) -> dict[str, dict[str, Any]]:
    states = {}
    for path in sorted(state_dir.glob("*.linear.json")):
        state = json.loads(path.read_text())
        task_uuid = state["task_uuid"]
        if task_uuid in states:
            raise ValueError(f"duplicate production state {task_uuid}")
        if state["status"] != "success":
            raise ValueError(f"non-success production state {task_uuid}")
        if state["extractor_version"] != "g40_p1_linear_v4":
            raise ValueError(f"unexpected extractor version for {task_uuid}")
        states[task_uuid] = state
    return states


def _corpus_metadata(root: Path) -> dict[str, dict[str, str]]:
    result = {}
    for path in sorted(root.rglob("*.json")):
        document = json.loads(path.read_text())
        for task in document.get("tasks", []):
            files = [
                item
                for item in task.get("supporting_files", [])
                if item.get("is_fcidump_file")
            ]
            if len(files) != 1:
                raise ValueError(f"{task['task_uuid']} has {len(files)} FCIDUMPs")
            item = files[0]
            url = item["instance_data_object_url"]
            result[task["task_uuid"]] = {
                "problem_instance_uuid": document["problem_instance_uuid"],
                "problem_instance_short_name": document["short_name"],
                "task_uuid": task["task_uuid"],
                "instance_data_object_uuid": item["instance_data_object_uuid"],
                "instance_data_object_file_name": item.get(
                    "instance_data_object_file_name",
                    Path(urlparse(url).path).name,
                ),
                "instance_data_object_url": url,
            }
    return result


def _read_table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"missing header in {path}")
        return list(reader.fieldnames), list(reader)


def _read_existing_ledger(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _migration_row(
    task_uuid: str,
    column: str,
    old_value: str,
    new_value: str,
) -> dict[str, str]:
    return {
        "task_uuid": task_uuid,
        "column": column,
        "old_value": old_value,
        "new_value": new_value,
        "reason": ALLOWED_MIGRATIONS[column],
    }


def _report_markdown(report: dict[str, Any]) -> str:
    changes = report["migration_cells_by_column"]
    change_text = ", ".join(f"`{key}`={value}" for key, value in changes.items())
    lines = [
        "# G40 P1-A production report",
        "",
        "## Result",
        "",
        f"- Corpus manifest tasks: **{report['corpus_tasks']}**.",
        f"- Successful v4 states merged: **{report['successful_states']}**.",
        (
            f"- Feature table: **{report['rows_before']} x "
            f"{report['columns_before']}** to **{report['rows_after']} x "
            f"{report['columns_after']}**."
        ),
        (
            "- Existing populated cells audited: "
            f"**{report['existing_populated_cells_audited']}**."
        ),
        f"- Approved migrated cells: **{report['migration_cells']}** ({change_text}).",
        "- Unapproved populated-cell changes: **0**.",
        (
            "- G21 representation-pair check: "
            f"**{report['representation_pair_status']}** "
            f"({report['representation_pair_groups_passed']}/"
            f"{report['representation_pair_groups']} groups)."
        ),
        "",
        "## Production evidence",
        "",
        (
            f"- Initial run: PBS `{report['initial_job_id']}`, code "
            f"`{report['initial_code_revision']}`, stdout "
            f"`{report['initial_stdout_log']}`, stderr "
            f"`{report['initial_stderr_log']}`. Result: 589 success, 2 failed."
        ),
        (
            "- Failure `c6e29566-d374-4bbd-88cb-32190117a7eb`: source is a "
            "one-member ZIP; v3 attempted to decode the ZIP container as ASCII."
        ),
        (
            "- Failure `34e0f543-0f23-405b-b06f-4be3cd556f9b`: source header "
            "omits MS2; v3 rejected it before consulting explicit task `spin=0` "
            "metadata."
        ),
        (
            f"- Corrected run: PBS `{report['corrected_job_id']}`, code "
            f"`{report['corrected_code_revision']}`, stdout "
            f"`{report['corrected_stdout_log']}`, stderr "
            f"`{report['corrected_stderr_log']}`. Result: 591 success, 0 failed; "
            "exit 0; walltime 00:17:06."
        ),
        "",
        "The corrected reader records ZIP member/container provenance and permits a",
        "missing header MS2 only when explicit task `ms2`/`spin` metadata exists. It",
        "does not infer a singlet. All state inputs remain checksum-bound. The merge",
        "preserves every populated legacy cell outside the five migration columns",
        "listed in `g40_p1a_migration_ledger.csv`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--feature-table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument(
        "--problem-instances", type=Path, default=ROOT / "problem_instances"
    )
    parser.add_argument("--representation-check", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--initial-stdout-log", type=Path, required=True)
    parser.add_argument("--initial-stderr-log", type=Path, required=True)
    parser.add_argument("--corrected-stdout-log", type=Path, required=True)
    parser.add_argument("--corrected-stderr-log", type=Path, required=True)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output / "g40_p1a_migration_ledger.csv"
    report_path = args.output / "g40_p1a_production_report.json"
    previous_report = (
        json.loads(report_path.read_text()) if report_path.exists() else {}
    )
    input_sha256 = previous_report.get(
        "input_feature_table_sha256", _sha256(args.feature_table)
    )

    states = _load_states(args.state_dir)
    corpus = _corpus_metadata(args.problem_instances)
    if set(states) != set(corpus):
        raise ValueError("production states do not exactly match the corpus manifest")
    fields, rows = _read_table(args.feature_table)
    rows_before = previous_report.get("rows_before", len(rows))
    columns_before = previous_report.get("columns_before", len(fields))
    original_rows = {row["task_uuid"]: dict(row) for row in rows}
    if len(original_rows) != len(rows):
        raise ValueError("duplicate task UUID in feature table")

    feature_columns = sorted(
        set.intersection(*(set(state["features"]) for state in states.values()))
    )
    for column in feature_columns:
        if column not in fields:
            fields.append(column)
    for task_uuid in sorted(set(states) - set(original_rows)):
        row = {field: "" for field in fields}
        row.update(corpus[task_uuid])
        rows.append(row)
    rows_by_uuid = {row["task_uuid"]: row for row in rows}

    migrations = []
    audited_populated = 0
    for task_uuid, state in sorted(states.items()):
        row = rows_by_uuid[task_uuid]
        original = original_rows.get(task_uuid, {})
        for column in feature_columns:
            old_value = original.get(column, "")
            new_value = _value_text(state["features"][column])
            if old_value:
                audited_populated += 1
            if old_value and old_value != new_value:
                if column not in ALLOWED_MIGRATIONS:
                    raise ValueError(
                        f"unapproved populated-cell change {task_uuid} {column}: "
                        f"{old_value!r} -> {new_value!r}"
                    )
                migrations.append(
                    _migration_row(task_uuid, column, old_value, new_value)
                )
            row[column] = new_value

    existing_ledger = _read_existing_ledger(ledger_path)
    if migrations:
        ledger = migrations
    else:
        ledger = existing_ledger
        for item in ledger:
            if rows_by_uuid[item["task_uuid"]][item["column"]] != item["new_value"]:
                raise ValueError("existing migration ledger does not match the table")
    ledger.sort(key=lambda item: (item["column"], item["task_uuid"]))
    if not ledger:
        raise ValueError("P1-A migration ledger is unexpectedly empty")

    _write_csv(args.feature_table, fields, rows)
    _write_csv(
        ledger_path,
        ["task_uuid", "column", "old_value", "new_value", "reason"],
        ledger,
    )
    representation = json.loads(args.representation_check.read_text())
    if representation["status"] != "passed":
        raise ValueError("G21 representation-pair check failed")

    report = {
        "report_version": "g40_p1a_production_v1",
        "corpus_tasks": len(corpus),
        "successful_states": len(states),
        "extractor_version": "g40_p1_linear_v4",
        "input_feature_table_sha256": input_sha256,
        "output_feature_table_sha256": _sha256(args.feature_table),
        "rows_before": rows_before,
        "columns_before": columns_before,
        "rows_after": len(rows),
        "columns_after": len(fields),
        "existing_populated_cells_audited": previous_report.get(
            "existing_populated_cells_audited", audited_populated
        ),
        "migration_cells": len(ledger),
        "migration_cells_by_column": dict(
            sorted(Counter(item["column"] for item in ledger).items())
        ),
        "representation_pair_status": representation["status"],
        "representation_pair_groups": representation["equivalence_groups"],
        "representation_pair_groups_passed": representation["groups_passed"],
        "initial_job_id": "7651290.imgt1",
        "initial_code_revision": "2b94398",
        "initial_stdout_log": str(args.initial_stdout_log),
        "initial_stdout_sha256": _sha256(args.initial_stdout_log),
        "initial_stderr_log": str(args.initial_stderr_log),
        "initial_stderr_sha256": _sha256(args.initial_stderr_log),
        "corrected_job_id": "7651318.imgt1",
        "corrected_code_revision": "8f8348a0c402c1369141bdc64cafc60923fa5260",
        "corrected_stdout_log": str(args.corrected_stdout_log),
        "corrected_stdout_sha256": _sha256(args.corrected_stdout_log),
        "corrected_stderr_log": str(args.corrected_stderr_log),
        "corrected_stderr_sha256": _sha256(args.corrected_stderr_log),
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (args.output / "g40_p1a_production_report.md").write_text(_report_markdown(report))
    print(
        json.dumps(
            {
                "rows": len(rows),
                "columns": len(fields),
                "migrations": len(ledger),
                "table_sha256": report["output_feature_table_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
