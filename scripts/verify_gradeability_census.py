#!/usr/bin/env python
"""Independent verifier for the ML-8A gradeability census.

Re-derives every census field from the raw instance JSONs, the pinned taxonomy,
and the pinned feature table using its OWN implementation of the frozen
decision ladder. It deliberately does not import
``qb_gsee_benchmark.ml.gradeability_census`` -- the builder's decision code must
not be able to certify itself. Fails closed: any mismatch exits non-zero.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

CHECKABLE = frozenset(
    {"analytical", "exact", "multiple_nearly_exact", "one_nearly_exact"}
)
JW_COMPLETE_COVERAGE = 715


class VerificationError(RuntimeError):
    pass


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _reason(task: dict[str, Any]) -> str:
    """Independent restatement of the frozen ML-8A ladder."""
    tier = str(task.get("curation_tier") or "")
    grade = task.get("reference_provenance_grade")
    grade = str(grade) if grade else "missing"
    requirements = task.get("requirements") or {}
    energy = _number(requirements.get("reference_energy"))
    threshold = _number(requirements.get("absolute_accuracy_threshold"))
    if tier == "test":
        return "excluded_test_tier"
    if task.get("source_defect_documented"):
        return "excluded_source_defect_documented"
    if grade == "missing":
        return "excluded_missing_taxonomy_grade"
    if grade not in CHECKABLE:
        return "excluded_reference_grade_" + grade
    if energy is None:
        return "excluded_missing_reference_energy"
    if threshold is None or threshold <= 0.0:
        return "excluded_missing_or_invalid_threshold"
    return "gradeable"


def _read_csv_column(path: Path, column: str) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [str(row[column]) for row in csv.DictReader(handle)]


def _jw_columns(root: Path, census: dict[str, Any]) -> list[str]:
    metadata_path = root / census["inputs"]["feature_metadata"]["path"]
    with metadata_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    eligible = sorted(
        str(row["column"])
        for row in rows
        if str(row["cost_class"]) == "jw_encoding"
        and str(row["model_eligible"]).strip().lower() == "true"
    )
    table_path = root / census["inputs"]["feature_table"]["path"]
    with table_path.open(encoding="utf-8", newline="") as handle:
        feature_rows = list(csv.DictReader(handle))
    coverage = {
        column: sum(1 for row in feature_rows if str(row[column]).strip() != "")
        for column in eligible
    }
    return sorted(
        column for column, count in coverage.items() if count == JW_COMPLETE_COVERAGE
    )


def _jw_null_tasks(root: Path, census: dict[str, Any], columns: list[str]) -> set[str]:
    table_path = root / census["inputs"]["feature_table"]["path"]
    with table_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        str(row["task_uuid"])
        for row in rows
        if all(str(row[column]).strip() == "" for column in columns)
    }


def verify(root: Path, artifact: Path) -> dict[str, Any]:
    census = json.loads((artifact / "census.json").read_text(encoding="utf-8"))
    report = json.loads((artifact / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (artifact / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    checks = 0

    # 1. schema validation
    for payload, schema_name in (
        (census, "census.schema.json"),
        (report, "report.schema.json"),
    ):
        schema = json.loads(
            (artifact / "schemas" / schema_name).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(payload)
        checks += 1

    # 2. held-state flags
    for payload in (census, report, manifest):
        _check(payload["status"] == "held_pending_pi_review", "not held")
        _check(payload["effective"] is False, "effective must be false")
        _check(
            payload["eligibility_substrate_of_record"] is False,
            "substrate-of-record must be false",
        )
        _check(payload["modifies_committed_artifact"] is False, "claims a mutation")
        _check(payload["reads_solver_outcomes"] is False, "claims outcome reads")
        checks += 5

    # 3. pinned inputs still hash as declared
    for name, specification in sorted(census["inputs"].items()):
        path = root / str(specification["path"])
        _check(path.is_file(), f"missing pinned input: {name}")
        _check(
            _sha256(path) == str(specification["sha256"]),
            f"pinned input drift: {name}",
        )
        checks += 1

    # 4. corpus bytes: per-file hashes and the listing digest
    instances = sorted((root / "problem_instances").rglob("*.json"))
    declared = {
        str(record["path"]): str(record["sha256"])
        for record in census["corpus_digest"]["files"]
    }
    _check(
        len(instances) == census["corpus_digest"]["instance_files"] == len(declared),
        "instance file count mismatch",
    )
    for path in instances:
        relative = str(path.relative_to(root))
        _check(relative in declared, f"undeclared instance file: {relative}")
        _check(_sha256(path) == declared[relative], f"instance byte drift: {relative}")
        checks += 1
    listing = "".join(f"{key}:{declared[key]}\n" for key in sorted(declared))
    _check(
        hashlib.sha256(listing.encode("utf-8")).hexdigest()
        == str(census["corpus_digest"]["listing_sha256"]),
        "corpus listing digest mismatch",
    )
    checks += 1

    # 5. independently re-derive every task row
    taxonomy = json.loads(
        (root / census["inputs"]["canonical_families"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    canonical = {
        str(row["task_uuid"]): str(row["canonical_family_recommended"])
        for row in taxonomy["tasks"]
    }
    jw_columns = _jw_columns(root, census)
    _check(
        sorted(jw_columns) == sorted(census["jw_block"]["corpus_complete_columns"]),
        "JW corpus-complete column set mismatch",
    )
    jw_null = _jw_null_tasks(root, census, jw_columns)
    _check(
        sorted(jw_null) == sorted(census["jw_block"]["null_task_uuids"]),
        "JW whole-block-null task set mismatch",
    )
    checks += 2

    expected: dict[str, dict[str, Any]] = {}
    for path in instances:
        payload = json.loads(path.read_text(encoding="utf-8"))
        short_name = str(payload.get("problem_instance_short_name") or path.stem)
        for task in payload.get("tasks", []):
            task_uuid = str(task["task_uuid"])
            _check(task_uuid not in expected, f"duplicate task: {task_uuid}")
            grade = task.get("reference_provenance_grade")
            grade = str(grade) if grade else "missing"
            requirements = task.get("requirements") or {}
            threshold = _number(requirements.get("absolute_accuracy_threshold"))
            reason = _reason(task)
            expected[task_uuid] = {
                "task_uuid": task_uuid,
                "problem_instance_path": str(path.relative_to(root)),
                "problem_instance_short_name": short_name,
                "canonical_family": canonical[task_uuid],
                "reference_grade": grade,
                "reference_grade_checkable": grade in CHECKABLE,
                "curation_tier": str(task.get("curation_tier") or ""),
                "test_tier": str(task.get("curation_tier") or "") == "test",
                "source_defect_documented": bool(task.get("source_defect_documented")),
                "reference_energy_present": _number(requirements.get("reference_energy"))
                is not None,
                "absolute_accuracy_threshold": threshold,
                "threshold_positive": threshold is not None and threshold > 0.0,
                "jw_block_null_infeasible": task_uuid in jw_null,
                "gradeable_for_campaign_scoring": reason == "gradeable",
                "gradeability_reason": reason,
            }

    rows = census["tasks"]
    _check(len(rows) == len(expected) == 718, f"task count: {len(rows)}")
    _check(
        [str(row["task_uuid"]) for row in rows]
        == sorted(str(row["task_uuid"]) for row in rows),
        "census rows are not task-sorted",
    )
    for row in rows:
        reference = expected[str(row["task_uuid"])]
        for key, value in reference.items():
            _check(
                row[key] == value,
                f"field mismatch {row['task_uuid']}.{key}: {row[key]!r} != {value!r}",
            )
        checks += 1

    # 6. CSV mirror agrees with the JSON payload
    with (artifact / "census.csv").open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    _check(len(csv_rows) == len(rows), "census.csv row count mismatch")
    for csv_row, row in zip(csv_rows, rows):
        _check(csv_row["task_uuid"] == row["task_uuid"], "census.csv order mismatch")
        _check(
            csv_row["gradeability_reason"] == row["gradeability_reason"],
            f"census.csv reason mismatch: {csv_row['task_uuid']}",
        )
        _check(
            (csv_row["gradeable_for_campaign_scoring"].lower() == "true")
            == bool(row["gradeable_for_campaign_scoring"]),
            f"census.csv boolean mismatch: {csv_row['task_uuid']}",
        )
        checks += 1

    # 7. recount every published total
    counts = Counter(str(row["gradeability_reason"]) for row in rows)
    for reason, count in report["reason_counts"].items():
        _check(int(counts.get(reason, 0)) == int(count), f"reason count: {reason}")
        checks += 1
    gradeable = sum(1 for row in rows if row["gradeable_for_campaign_scoring"])
    totals = report["totals"]
    _check(int(totals["n_tasks"]) == len(rows), "total task count")
    _check(int(totals["n_gradeable"]) == gradeable, "total gradeable count")
    _check(
        int(totals["n_not_gradeable"]) == len(rows) - gradeable,
        "total non-gradeable count",
    )
    _check(
        int(totals["n_jw_block_null_infeasible"]) == len(jw_null),
        "total JW-null count",
    )
    checks += 4

    families = Counter(str(row["canonical_family"]) for row in rows)
    _check(
        int(totals["n_canonical_families"]) == len(families), "canonical family count"
    )
    _check(len(report["family_counts"]) == len(families), "family row count")
    for record in report["family_counts"]:
        family = str(record["canonical_family"])
        subset = [row for row in rows if str(row["canonical_family"]) == family]
        subset_gradeable = sum(
            1 for row in subset if row["gradeable_for_campaign_scoring"]
        )
        _check(int(record["n_tasks"]) == len(subset), f"family n_tasks: {family}")
        _check(
            int(record["n_gradeable"]) == subset_gradeable,
            f"family n_gradeable: {family}",
        )
        _check(
            int(record["n_not_gradeable"]) == len(subset) - subset_gradeable,
            f"family n_not_gradeable: {family}",
        )
        checks += 3
    for record in report["grade_counts"]:
        grade = str(record["reference_grade"])
        subset = [row for row in rows if str(row["reference_grade"]) == grade]
        subset_gradeable = sum(
            1 for row in subset if row["gradeable_for_campaign_scoring"]
        )
        _check(int(record["n_tasks"]) == len(subset), f"grade n_tasks: {grade}")
        _check(
            int(record["n_gradeable"]) == subset_gradeable,
            f"grade n_gradeable: {grade}",
        )
        _check(
            bool(record["checkable"]) == (grade in CHECKABLE),
            f"grade checkable flag: {grade}",
        )
        checks += 3

    # 7b. amendment A1 structural diagnostics, recounted from the task rows
    structural = report["structural_consequences"]
    zero_families = sorted(
        family
        for family in families
        if not any(
            row["gradeable_for_campaign_scoring"]
            for row in rows
            if str(row["canonical_family"]) == family
        )
    )
    _check(
        sorted(
            str(record["canonical_family"])
            for record in structural["families_with_zero_gradeable_tasks"]
        )
        == zero_families,
        "zero-gradeable family list mismatch",
    )
    for record in structural["families_with_zero_gradeable_tasks"]:
        _check(
            int(record["n_tasks"]) == int(families[str(record["canonical_family"])]),
            f"zero-gradeable family task count: {record['canonical_family']}",
        )
        checks += 1
    _check(
        int(structural["n_families_with_zero_gradeable_tasks"]) == len(zero_families),
        "zero-gradeable family count",
    )
    _check(
        int(structural["n_families_with_any_gradeable_task"])
        == len(families) - len(zero_families),
        "any-gradeable family count",
    )
    _check(
        int(structural["n_families_with_any_non_gradeable_task"])
        == sum(
            1
            for family in families
            if any(
                not row["gradeable_for_campaign_scoring"]
                for row in rows
                if str(row["canonical_family"]) == family
            )
        ),
        "any-non-gradeable family count",
    )
    _check(
        structural["recommendation_offered"] is False,
        "census must offer no recommendation",
    )
    checks += 5

    # 8. re-evaluate the preregistered falsifiable prediction
    check = report["panel_cross_check"]
    if check.get("evaluated"):
        panel_path = root / str(check["panel_source"])
        _check(panel_path.is_file(), "panel source missing")
        _check(_sha256(panel_path) == str(check["panel_source_sha256"]), "panel drift")
        panel_tasks = sorted(set(_read_csv_column(panel_path, "task_uuid")))
        _check(
            len(panel_tasks) == int(check["panel_tasks"]), "panel task count mismatch"
        )
        by_task = {str(row["task_uuid"]): row for row in rows}
        panel_gradeable = [
            task
            for task in panel_tasks
            if by_task[task]["gradeable_for_campaign_scoring"]
        ]
        _check(
            len(panel_gradeable) == int(check["observed"]["gradeable"]),
            "panel gradeable recount mismatch",
        )
        _check(
            len(panel_tasks) - len(panel_gradeable)
            == int(check["observed"]["not_gradeable"]),
            "panel non-gradeable recount mismatch",
        )
        _check(
            sorted(check["not_gradeable_task_uuids"])
            == sorted(set(panel_tasks) - set(panel_gradeable)),
            "panel non-gradeable UUID list mismatch",
        )
        _check(
            bool(check["prediction_confirmed"])
            == (check["observed"] == check["expected"]),
            "prediction_confirmed inconsistent with counts",
        )
        checks += 6

    # 9. manifest hashes and byte counts
    declared_files = {
        str(record["path"]): (int(record["bytes"]), str(record["sha256"]))
        for record in manifest["files"]
    }
    present = sorted(
        str(path.relative_to(artifact))
        for path in artifact.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    _check(present == sorted(declared_files), "manifest file list mismatch")
    for relative, (size, digest) in sorted(declared_files.items()):
        path = artifact / relative
        _check(path.stat().st_size == size, f"manifest byte count: {relative}")
        _check(_sha256(path) == digest, f"manifest hash: {relative}")
        checks += 2

    return {
        "status": "VERIFIED",
        "checks": checks,
        "n_tasks": len(rows),
        "n_gradeable": gradeable,
        "n_not_gradeable": len(rows) - gradeable,
        "panel_prediction_confirmed": check.get("prediction_confirmed"),
        "n_families_with_zero_gradeable_tasks": len(zero_families),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact", type=Path, default=Path("analysis/ml_gradeability_census/held_v1")
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    artifact = arguments.artifact
    if not artifact.is_absolute():
        artifact = root / artifact
    try:
        result = verify(root, artifact)
    except Exception as error:  # noqa: BLE001 - fail closed by design
        print(json.dumps({"status": "FAILED", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
