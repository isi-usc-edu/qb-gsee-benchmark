#!/usr/bin/env python3
# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Idempotently rebuild the G-21 through G-24 feature columns."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterable

from qb_gsee_benchmark.features.fragment_features import FRAGMENT_FEATURE_COLUMNS
from qb_gsee_benchmark.features.pair_structure_features import (
    PAIR_STRUCTURE_FEATURE_COLUMNS,
)
from qb_gsee_benchmark.features.representation_features import (
    REPRESENTATION_FEATURE_COLUMNS,
)
from qb_gsee_benchmark.features.sign_free_features import (
    SIGN_FREE_FEATURE_COLUMNS,
    detect_hubbard_task,
)

STRUCTURED_FEATURE_COLUMNS = (
    *REPRESENTATION_FEATURE_COLUMNS,
    *FRAGMENT_FEATURE_COLUMNS,
    *SIGN_FREE_FEATURE_COLUMNS,
    *PAIR_STRUCTURE_FEATURE_COLUMNS,
)
assert len(STRUCTURED_FEATURE_COLUMNS) == len(set(STRUCTURED_FEATURE_COLUMNS)) == 62


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument(
        "--problem-instances", type=Path, default=Path("problem_instances")
    )
    parser.add_argument("--representation-csv", type=Path, required=True)
    parser.add_argument("--fragment-csv", type=Path, required=True)
    parser.add_argument("--sign-csv", type=Path, required=True)
    parser.add_argument("--pair-structure-csv", type=Path, required=True)
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)


def metadata_sign_records(problem_instances: Path) -> dict[str, dict[str, str]]:
    records = {}
    for path in sorted(problem_instances.rglob("*.json")):
        instance = json.loads(path.read_text())
        for task in instance.get("tasks", []):
            detected = detect_hubbard_task(instance, task)
            if detected is not None:
                records[str(task["task_uuid"])] = {
                    key: stringify(value) for key, value in detected.items()
                }
    return records


def bundle_records(
    path: Path, feature_columns: Iterable[str]
) -> dict[str, dict[str, str]]:
    fields, rows = read_csv(path)
    expected = set(feature_columns)
    missing = expected - set(fields)
    if missing:
        raise ValueError(f"{path} is missing feature columns: {sorted(missing)}")
    records = {}
    for row in rows:
        task_uuid = row.get("task_uuid", "")
        if not task_uuid or task_uuid in records:
            raise ValueError(f"{path} has missing or duplicate task UUID {task_uuid!r}")
        records[task_uuid] = {column: row[column] for column in feature_columns}
    return records


def main() -> int:
    args = parse_args()
    output = args.output_csv or args.input_csv
    fields, rows = read_csv(args.input_csv)
    missing_columns = [
        column for column in STRUCTURED_FEATURE_COLUMNS if column not in fields
    ]
    fields.extend(missing_columns)
    by_task = {row.get("task_uuid", ""): row for row in rows}

    overlays: list[dict[str, dict[str, str]]] = [
        metadata_sign_records(args.problem_instances),
        bundle_records(args.representation_csv, REPRESENTATION_FEATURE_COLUMNS),
        bundle_records(args.fragment_csv, FRAGMENT_FEATURE_COLUMNS),
        bundle_records(args.sign_csv, SIGN_FREE_FEATURE_COLUMNS),
        bundle_records(args.pair_structure_csv, PAIR_STRUCTURE_FEATURE_COLUMNS),
    ]
    updated = set()
    for records in overlays:
        for task_uuid, values in records.items():
            row = by_task.get(task_uuid)
            if row is None:
                raise KeyError(
                    f"feature record task is absent from input table: {task_uuid}"
                )
            row.update(values)
            updated.add(task_uuid)

    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "columns": len(fields),
                "structured_feature_columns": len(STRUCTURED_FEATURE_COLUMNS),
                "tasks_updated": len(updated),
                "output": str(output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
