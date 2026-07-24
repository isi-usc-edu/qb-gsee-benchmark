#!/usr/bin/env python3
"""Verify that the TrimCI rung correction did not alter unchanged model scopes."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Callable

from qb_gsee_benchmark.ml.core_set import sha256_file, stable_json_dump


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def unchanged_variant(row: dict[str, str]) -> bool:
    return (
        row["solver_family_id"] != "trimci"
        or row["solver_short_name"] == "TrimCI_default"
    )


def compare_csv_scope(
    old: Path,
    new: Path,
    name: str,
    predicate: Callable[[dict[str, str]], bool],
) -> dict[str, Any]:
    old_rows = [row for row in csv_rows(old / name) if predicate(row)]
    new_rows = [row for row in csv_rows(new / name) if predicate(row)]
    return {
        "equal": old_rows == new_rows,
        "old_rows": len(old_rows),
        "new_rows": len(new_rows),
    }


def file_inventory(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): sha256_file(item)
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old", type=Path, required=True)
    parser.add_argument("--new", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    checks = {
        "normalized_observations_unchanged_variants": compare_csv_scope(
            arguments.old,
            arguments.new,
            "normalized_observations.csv",
            unchanged_variant,
        ),
        "coverage_unchanged_variants": compare_csv_scope(
            arguments.old, arguments.new, "coverage.csv", unchanged_variant
        ),
        "eligibility_unchanged_variants": compare_csv_scope(
            arguments.old,
            arguments.new,
            "variant_eligibility.csv",
            unchanged_variant,
        ),
        "predictions_previously_eligible_variants": compare_csv_scope(
            arguments.old, arguments.new, "predictions.csv", unchanged_variant
        ),
        "performance_previously_eligible_variants": compare_csv_scope(
            arguments.old,
            arguments.new,
            "family_balanced_performance.csv",
            unchanged_variant,
        ),
        "deltas_previously_eligible_variants": compare_csv_scope(
            arguments.old, arguments.new, "paired_deltas.csv", unchanged_variant
        ),
        "growth_unchanged_variants": compare_csv_scope(
            arguments.old, arguments.new, "ladder_growth.csv", unchanged_variant
        ),
        "nestedness_non_trimci_ladders": compare_csv_scope(
            arguments.old,
            arguments.new,
            "nestedness.csv",
            lambda row: row["solver_family_id"] != "trimci",
        ),
        "preflight_tree": {
            "equal": file_inventory(arguments.old / "preflight")
            == file_inventory(arguments.new / "preflight"),
            "old_files": len(file_inventory(arguments.old / "preflight")),
            "new_files": len(file_inventory(arguments.new / "preflight")),
        },
        "schema_tree": {
            "equal": file_inventory(arguments.old / "schemas")
            == file_inventory(arguments.new / "schemas"),
            "old_files": len(file_inventory(arguments.old / "schemas")),
            "new_files": len(file_inventory(arguments.new / "schemas")),
        },
    }
    failures = sorted(name for name, check in checks.items() if not check["equal"])
    report = {
        "artifact_id": "ml_g50_solver_families_v3_v4_scope_comparison_v1",
        "status": "pass" if not failures else "fail",
        "old_manifest_sha256": sha256_file(arguments.old / "artifact_manifest.json"),
        "new_manifest_sha256": sha256_file(arguments.new / "artifact_manifest.json"),
        "changed_scope": "TrimCI seven-rung labels, models, predictions, and dependent aggregates",
        "checks": checks,
        "failures": failures,
    }
    stable_json_dump(report, arguments.output)
    if failures:
        raise SystemExit(f"changed supposedly unchanged scopes: {failures}")
    print(
        "ML_G50_V3_V4_SCOPE_COMPARISON "
        f"checks={len(checks)} status={report['status']}"
    )


if __name__ == "__main__":
    main()
