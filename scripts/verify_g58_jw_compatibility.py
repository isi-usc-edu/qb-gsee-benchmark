#!/usr/bin/env python3
# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Verify G58 JW features against the immutable historical block."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import resource
import time
from pathlib import Path

from qb_gsee_benchmark.features.corpus_runner import (
    load_corpus_fcidumps,
    materialize_fcidump,
)
from qb_gsee_benchmark.features.jw_encoding_features import (
    JW_ENCODING_VERSION,
    OUTPUT_COLUMNS,
    compute_jw_encoding_features,
)

INTEGER_COLUMNS = {
    "max_vertex_degree",
    "min_vertex_degree",
    "number_of_terms",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _load_selection(path: Path) -> list[str]:
    selected = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(selected) != len(set(selected)):
        raise ValueError("compatibility selection contains duplicate task UUIDs")
    return selected


def _load_feature_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = {row["task_uuid"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError("feature table contains duplicate task UUIDs")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--problem-instances", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text())
    relative_tolerance = float(protocol["compatibility"]["relative_tolerance"])
    absolute_tolerance = float(protocol["compatibility"]["absolute_tolerance"])
    minimum_rows = int(protocol["compatibility"]["minimum_covered_rows"])
    selected = _load_selection(args.selection)
    if len(selected) < minimum_rows:
        raise ValueError(
            f"selection has {len(selected)} rows; need at least {minimum_rows}"
        )

    feature_rows = _load_feature_rows(args.features)
    manifest = {
        record.task_uuid: record
        for record in load_corpus_fcidumps(args.problem_instances)
    }
    missing = sorted(set(selected) - feature_rows.keys())
    missing.extend(sorted(set(selected) - manifest.keys()))
    if missing:
        raise ValueError(
            f"selection contains unavailable task UUIDs: {sorted(set(missing))}"
        )

    covered_rows = [
        row
        for row in feature_rows.values()
        if all(row.get(column, "").strip() for column in OUTPUT_COLUMNS)
    ]
    uncovered = [
        task_uuid
        for task_uuid in selected
        if not all(
            feature_rows[task_uuid].get(column, "").strip() for column in OUTPUT_COLUMNS
        )
    ]
    if uncovered:
        raise ValueError(
            f"compatibility selection contains uncovered rows: {uncovered}"
        )

    comparison_rows: list[dict[str, object]] = []
    passed = True
    for task_uuid in selected:
        record = manifest[task_uuid]
        expected_row = feature_rows[task_uuid]
        source = materialize_fcidump(record, args.cache_dir, offline=args.offline)
        started = time.monotonic()
        observed, audit = compute_jw_encoding_features(
            source, ms2_override=record.ms2_metadata
        )
        elapsed = time.monotonic() - started
        mismatches: list[dict[str, object]] = []
        for column in OUTPUT_COLUMNS:
            expected = float(expected_row[column])
            actual = float(observed[column])
            if column in INTEGER_COLUMNS:
                agrees = actual.is_integer() and int(actual) == int(expected)
            else:
                agrees = math.isclose(
                    actual,
                    expected,
                    rel_tol=relative_tolerance,
                    abs_tol=absolute_tolerance,
                )
            if not agrees:
                mismatches.append(
                    {"column": column, "expected": expected, "observed": actual}
                )
        passed = passed and not mismatches
        comparison_rows.append(
            {
                "instance": expected_row["problem_instance_short_name"],
                "mismatches": mismatches,
                "multiset_groups": audit["integral_multiset_group_count"],
                "norb": int(float(expected_row["n_orbs"])),
                "task_uuid": task_uuid,
                "unique_eri_records": audit["two_body_unique_record_count"],
                "walltime_seconds": elapsed,
            }
        )

    report: dict[str, object] = {
        "artifact_id": "g58_compatibility_v1_1",
        "covered_source_census": {
            "covered_rows": len(covered_rows),
            "lattice_rows": sum(
                bool(row.get("lattice_model_family", "").strip())
                for row in covered_rows
            ),
        },
        "extractor_version": JW_ENCODING_VERSION,
        "feature_table_sha256": _sha256(args.features),
        "passed": passed,
        "process_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "protocol_sha256": _sha256(args.protocol),
        "rows": comparison_rows,
        "selection_sha256": _sha256(args.selection),
        "tolerances": {
            "absolute": absolute_tolerance,
            "integer_columns_exact": sorted(INTEGER_COLUMNS),
            "relative": relative_tolerance,
        },
    }
    _atomic_json(args.output, report)
    print(json.dumps({"output": str(args.output), "passed": passed}, sort_keys=True))
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
