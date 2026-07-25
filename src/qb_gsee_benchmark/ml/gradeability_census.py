"""ML-8A corpus-wide gradeability census.

Deterministic, outcome-blind census of every corpus task's campaign
gradeability. The frozen decision ladder, vocabulary partition, and output
contract live in ``analysis/ml_gradeability_census/PREREGISTRATION.md`` and its
machine-readable twin; this module implements them and nothing else.

No solver outcome, metrics bundle, or campaign ledger is read here.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.g50_solver_families import canonical_family_map

PREREGISTRATION_ID = "ml8a_gradeability_census_preregistration_v1"
CENSUS_ID = "ml8a_gradeability_census_v1"

#: Reference grades a success-within-threshold test can be scored against.
#: Taken verbatim from ``VALID_REFERENCE_GRADES`` in the metrics
#: implementation of record; ML-8A never widens it.
CHECKABLE_REFERENCE_GRADES = frozenset(
    {"analytical", "exact", "multiple_nearly_exact", "one_nearly_exact"}
)
NOT_CHECKABLE_REFERENCE_GRADES = frozenset(
    {"no_reference", "uncontrolled_estimate", "variational_upper_bound"}
)
MISSING_GRADE = "missing"

JW_COST_CLASS = "jw_encoding"
#: Corpus coverage that marks a JW column as corpus-complete rather than a
#: partial pre-G58 remnant.
JW_CORPUS_COMPLETE_COVERAGE = 715
EXPECTED_JW_CORPUS_COMPLETE_COLUMNS = 15
EXPECTED_TASKS = 718
EXPECTED_INSTANCE_FILES = 218

CENSUS_COLUMNS = [
    "task_uuid",
    "problem_instance_path",
    "problem_instance_short_name",
    "canonical_family",
    "reference_grade",
    "reference_grade_checkable",
    "curation_tier",
    "test_tier",
    "source_defect_documented",
    "reference_energy_present",
    "absolute_accuracy_threshold",
    "threshold_positive",
    "jw_block_null_infeasible",
    "gradeable_for_campaign_scoring",
    "gradeability_reason",
]
FAMILY_COUNT_COLUMNS = [
    "canonical_family",
    "n_tasks",
    "n_gradeable",
    "n_not_gradeable",
    "n_excluded_test_tier",
    "n_excluded_source_defect_documented",
    "n_excluded_reference_grade_no_reference",
    "n_excluded_reference_grade_uncontrolled_estimate",
    "n_excluded_reference_grade_variational_upper_bound",
    "n_excluded_missing_taxonomy_grade",
    "n_excluded_missing_reference_energy",
    "n_excluded_missing_or_invalid_threshold",
    "n_jw_block_null_infeasible",
]
GRADE_COUNT_COLUMNS = [
    "reference_grade",
    "checkable",
    "n_tasks",
    "n_gradeable",
    "n_not_gradeable",
]

_REASON_ORDER = [
    "gradeable",
    "excluded_test_tier",
    "excluded_source_defect_documented",
    "excluded_missing_taxonomy_grade",
    "excluded_reference_grade_no_reference",
    "excluded_reference_grade_uncontrolled_estimate",
    "excluded_reference_grade_variational_upper_bound",
    "excluded_missing_reference_energy",
    "excluded_missing_or_invalid_threshold",
]


def load_preregistration(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(
        payload.get("artifact_id") == PREREGISTRATION_ID,
        "wrong ML-8A preregistration",
    )
    _require(
        payload.get("frozen_before_census_output") is True,
        "ML-8A preregistration is not frozen",
    )
    return payload


def verify_pinned_inputs(
    root: Path, preregistration: Mapping[str, Any]
) -> dict[str, dict[str, str]]:
    """Fail closed on any pinned-input hash drift."""
    resolved: dict[str, dict[str, str]] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path = root / str(specification["path"])
        _require(path.is_file(), f"missing pinned input: {name}")
        digest = sha256_file(path)
        _require(
            digest == str(specification["sha256"]),
            f"pinned input hash drift: {name} -> {digest}",
        )
        resolved[name] = {"path": str(specification["path"]), "sha256": digest}
    return resolved


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def load_corpus_tasks(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Read every corpus task record plus a per-instance-file hash listing."""
    instances = sorted((root / "problem_instances").rglob("*.json"))
    _require(
        len(instances) == EXPECTED_INSTANCE_FILES,
        f"instance file census changed: {len(instances)}",
    )
    digests = [
        {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
        }
        for path in instances
    ]
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in instances:
        payload = json.loads(path.read_text(encoding="utf-8"))
        short_name = str(payload.get("problem_instance_short_name") or path.stem)
        for task in payload.get("tasks", []):
            task_uuid = str(task["task_uuid"])
            _require(task_uuid not in seen, f"duplicate corpus task: {task_uuid}")
            seen.add(task_uuid)
            records.append(
                {
                    "task": task,
                    "problem_instance_path": str(path.relative_to(root)),
                    "problem_instance_short_name": short_name,
                }
            )
    _require(
        len(records) == EXPECTED_TASKS, f"corpus task census changed: {len(records)}"
    )
    records.sort(key=lambda record: str(record["task"]["task_uuid"]))
    return records, digests


def corpus_listing_digest(digests: Sequence[Mapping[str, str]]) -> str:
    """Digest the sorted ``path:sha256`` listing that pins the corpus bytes."""
    listing = "".join(
        f"{record['path']}:{record['sha256']}\n"
        for record in sorted(digests, key=lambda record: str(record["path"]))
    )
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()


def jw_block_columns(metadata: pd.DataFrame, features: pd.DataFrame) -> dict[str, Any]:
    """Split model-eligible JW columns into corpus-complete and partial sets."""
    eligible = metadata.loc[
        (metadata["cost_class"].astype(str) == JW_COST_CLASS)
        & metadata["model_eligible"].astype(str).str.lower().eq("true"),
        "column",
    ]
    columns = sorted(map(str, eligible))
    _require(bool(columns), "no model-eligible jw_encoding columns found")
    coverage = {column: int(features[column].notna().sum()) for column in columns}
    complete = sorted(
        column
        for column, count in coverage.items()
        if count == JW_CORPUS_COMPLETE_COVERAGE
    )
    partial = sorted(set(columns) - set(complete))
    _require(
        len(complete) == EXPECTED_JW_CORPUS_COMPLETE_COLUMNS,
        f"corpus-complete JW column count changed: {len(complete)}",
    )
    return {
        "model_eligible_columns": columns,
        "corpus_complete_columns": complete,
        "partial_columns": partial,
        "coverage": dict(sorted(coverage.items())),
    }


def jw_null_tasks(features: pd.DataFrame, columns: Sequence[str]) -> set[str]:
    populated = features[list(columns)].notna().sum(axis=1)
    return {
        str(task_uuid)
        for task_uuid in features.loc[populated == 0, "task_uuid"].astype(str)
    }


def grade_of(task: Mapping[str, Any]) -> str:
    value = task.get("reference_provenance_grade")
    return str(value) if value else MISSING_GRADE


def gradeability(task: Mapping[str, Any]) -> str:
    """Apply the frozen ML-8A decision ladder and return its single reason."""
    if str(task.get("curation_tier") or "") == "test":
        return "excluded_test_tier"
    if task.get("source_defect_documented"):
        return "excluded_source_defect_documented"
    grade = grade_of(task)
    if grade == MISSING_GRADE:
        return "excluded_missing_taxonomy_grade"
    if grade not in CHECKABLE_REFERENCE_GRADES:
        return f"excluded_reference_grade_{grade}"
    requirements = task.get("requirements") or {}
    if _finite(requirements.get("reference_energy")) is None:
        return "excluded_missing_reference_energy"
    threshold = _finite(requirements.get("absolute_accuracy_threshold"))
    if threshold is None or threshold <= 0.0:
        return "excluded_missing_or_invalid_threshold"
    return "gradeable"


def build_census_rows(
    records: Sequence[Mapping[str, Any]],
    canonical: Mapping[str, str],
    jw_null: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        task = record["task"]
        task_uuid = str(task["task_uuid"])
        _require(task_uuid in canonical, f"task absent from taxonomy: {task_uuid}")
        requirements = task.get("requirements") or {}
        grade = grade_of(task)
        threshold = _finite(requirements.get("absolute_accuracy_threshold"))
        reason = gradeability(task)
        rows.append(
            {
                "task_uuid": task_uuid,
                "problem_instance_path": record["problem_instance_path"],
                "problem_instance_short_name": record["problem_instance_short_name"],
                "canonical_family": str(canonical[task_uuid]),
                "reference_grade": grade,
                "reference_grade_checkable": grade in CHECKABLE_REFERENCE_GRADES,
                "curation_tier": str(task.get("curation_tier") or ""),
                "test_tier": str(task.get("curation_tier") or "") == "test",
                "source_defect_documented": bool(task.get("source_defect_documented")),
                "reference_energy_present": _finite(requirements.get("reference_energy"))
                is not None,
                "absolute_accuracy_threshold": threshold,
                "threshold_positive": threshold is not None and threshold > 0.0,
                "jw_block_null_infeasible": task_uuid in jw_null,
                "gradeable_for_campaign_scoring": reason == "gradeable",
                "gradeability_reason": reason,
            }
        )
    rows.sort(key=lambda row: str(row["task_uuid"]))
    return rows


def reason_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(row["gradeability_reason"]) for row in rows)
    unexpected = sorted(set(counts) - set(_REASON_ORDER))
    _require(not unexpected, f"unexpected gradeability reason: {unexpected}")
    return {reason: int(counts.get(reason, 0)) for reason in _REASON_ORDER}


def family_count_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    families = sorted({str(row["canonical_family"]) for row in rows})
    result: list[dict[str, Any]] = []
    for family in families:
        subset = [row for row in rows if str(row["canonical_family"]) == family]
        counts = reason_counts(subset)
        record = {
            "canonical_family": family,
            "n_tasks": len(subset),
            "n_gradeable": counts["gradeable"],
            "n_not_gradeable": len(subset) - counts["gradeable"],
            "n_jw_block_null_infeasible": sum(
                1 for row in subset if row["jw_block_null_infeasible"]
            ),
        }
        for reason in _REASON_ORDER[1:]:
            record[f"n_{reason}"] = counts[reason]
        result.append(record)
    return result


def grade_count_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grades = sorted({str(row["reference_grade"]) for row in rows})
    result: list[dict[str, Any]] = []
    for grade in grades:
        subset = [row for row in rows if str(row["reference_grade"]) == grade]
        gradeable = sum(1 for row in subset if row["gradeable_for_campaign_scoring"])
        result.append(
            {
                "reference_grade": grade,
                "checkable": grade in CHECKABLE_REFERENCE_GRADES,
                "n_tasks": len(subset),
                "n_gradeable": gradeable,
                "n_not_gradeable": len(subset) - gradeable,
            }
        )
    return result


def panel_cross_check(
    root: Path, rows: Sequence[Mapping[str, Any]], preregistration: Mapping[str, Any]
) -> dict[str, Any]:
    """Evaluate the preregistered falsifiable prediction against final_v4."""
    prediction = preregistration["verification"]["falsifiable_prediction"]
    panel_path = root / str(prediction["panel_source"])
    if not panel_path.is_file():
        return {
            "evaluated": False,
            "reason": "panel source absent from this checkout",
            "panel_source": str(prediction["panel_source"]),
        }
    panel = pd.read_csv(panel_path, usecols=["task_uuid"])
    panel_tasks = sorted({str(value) for value in panel["task_uuid"]})
    by_task = {str(row["task_uuid"]): row for row in rows}
    missing = [task for task in panel_tasks if task not in by_task]
    _require(not missing, f"panel tasks absent from census: {missing[:3]}")
    gradeable = [
        task for task in panel_tasks if by_task[task]["gradeable_for_campaign_scoring"]
    ]
    not_gradeable = sorted(set(panel_tasks) - set(gradeable))
    observed = {"gradeable": len(gradeable), "not_gradeable": len(not_gradeable)}
    expected = {
        "gradeable": int(prediction["expected_gradeable"]),
        "not_gradeable": int(prediction["expected_non_gradeable"]),
    }
    return {
        "evaluated": True,
        "panel_source": str(prediction["panel_source"]),
        "panel_source_sha256": sha256_file(panel_path),
        "panel_tasks": len(panel_tasks),
        "expected": expected,
        "observed": observed,
        "prediction_confirmed": observed == expected,
        "not_gradeable_task_uuids": not_gradeable,
        "not_gradeable_reasons": {
            task: str(by_task[task]["gradeability_reason"]) for task in not_gradeable
        },
    }


def _census_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://qb-gsee-benchmark/analysis/ml_gradeability_census/census.schema.json",
        "title": "ML-8A corpus-wide gradeability census",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "artifact_id",
            "status",
            "effective",
            "eligibility_substrate_of_record",
            "modifies_committed_artifact",
            "reads_solver_outcomes",
            "preregistration",
            "inputs",
            "corpus_digest",
            "reference_grade_vocabulary",
            "gradeability_reason_order",
            "jw_block",
            "tasks",
        ],
        "properties": {
            "artifact_id": {"const": CENSUS_ID},
            "status": {"const": "held_pending_pi_review"},
            "effective": {"const": False},
            "eligibility_substrate_of_record": {"const": False},
            "modifies_committed_artifact": {"const": False},
            "reads_solver_outcomes": {"const": False},
            "preregistration": {"type": "object"},
            "inputs": {"type": "object"},
            "corpus_digest": {"type": "object"},
            "reference_grade_vocabulary": {"type": "object"},
            "gradeability_reason_order": {
                "type": "array",
                "items": {"type": "string"},
            },
            "jw_block": {"type": "object"},
            "tasks": {
                "type": "array",
                "minItems": EXPECTED_TASKS,
                "maxItems": EXPECTED_TASKS,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(CENSUS_COLUMNS),
                    "properties": {
                        "task_uuid": {"type": "string"},
                        "problem_instance_path": {"type": "string"},
                        "problem_instance_short_name": {"type": "string"},
                        "canonical_family": {"type": "string"},
                        "reference_grade": {"type": "string"},
                        "reference_grade_checkable": {"type": "boolean"},
                        "curation_tier": {"type": "string"},
                        "test_tier": {"type": "boolean"},
                        "source_defect_documented": {"type": "boolean"},
                        "reference_energy_present": {"type": "boolean"},
                        "absolute_accuracy_threshold": {"type": ["number", "null"]},
                        "threshold_positive": {"type": "boolean"},
                        "jw_block_null_infeasible": {"type": "boolean"},
                        "gradeable_for_campaign_scoring": {"type": "boolean"},
                        "gradeability_reason": {"type": "string"},
                    },
                },
            },
        },
    }


def _report_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://qb-gsee-benchmark/analysis/ml_gradeability_census/report.schema.json",
        "title": "ML-8A gradeability census report",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "artifact_id",
            "status",
            "effective",
            "eligibility_substrate_of_record",
            "modifies_committed_artifact",
            "reads_solver_outcomes",
            "totals",
            "reason_counts",
            "grade_counts",
            "family_counts",
            "jw_block",
            "panel_cross_check",
            "conservative_choices",
            "inputs",
        ],
        "properties": {
            "artifact_id": {"const": "ml8a_gradeability_census_report_v1"},
            "status": {"const": "held_pending_pi_review"},
            "effective": {"const": False},
            "eligibility_substrate_of_record": {"const": False},
            "modifies_committed_artifact": {"const": False},
            "reads_solver_outcomes": {"const": False},
            "totals": {"type": "object"},
            "reason_counts": {"type": "object"},
            "grade_counts": {"type": "array"},
            "family_counts": {"type": "array"},
            "jw_block": {"type": "object"},
            "panel_cross_check": {"type": "object"},
            "conservative_choices": {"type": "array"},
            "inputs": {"type": "object"},
        },
    }


def _markdown_report(report: Mapping[str, Any]) -> str:
    totals = report["totals"]
    lines = [
        "# ML-8A gradeability census — HELD (pending PI review)",
        "",
        "Corpus-wide, outcome-blind census of campaign gradeability over every",
        "task. This is a new analysis layer: it modifies no committed artifact,",
        "promotes nothing, and selects nothing. Not the eligibility substrate of",
        "record until the PI accepts it.",
        "",
        "## Totals",
        "",
        f"- corpus tasks: **{totals['n_tasks']}**",
        f"- gradeable for campaign scoring: **{totals['n_gradeable']}**",
        f"- not gradeable: **{totals['n_not_gradeable']}**",
        f"- canonical families: {totals['n_canonical_families']}",
        f"- JW whole-block-null (censused, NOT a gradeability criterion): "
        f"{totals['n_jw_block_null_infeasible']}",
        "",
        "## Count by reason",
        "",
        "| reason | tasks |",
        "|---|---|",
    ]
    for reason, count in report["reason_counts"].items():
        lines.append(f"| `{reason}` | {count} |")
    lines += [
        "",
        "## Count by reference grade",
        "",
        "| reference grade | checkable | tasks | gradeable | not gradeable |",
        "|---|---|---|---|---|",
    ]
    for row in report["grade_counts"]:
        lines.append(
            f"| `{row['reference_grade']}` | {str(row['checkable']).lower()} | "
            f"{row['n_tasks']} | {row['n_gradeable']} | {row['n_not_gradeable']} |"
        )
    lines += [
        "",
        "## Canonical family breakdown",
        "",
        "| canonical family | tasks | gradeable | not gradeable |",
        "|---|---|---|---|",
    ]
    for row in report["family_counts"]:
        lines.append(
            f"| `{row['canonical_family']}` | {row['n_tasks']} | "
            f"{row['n_gradeable']} | {row['n_not_gradeable']} |"
        )
    check = report["panel_cross_check"]
    lines += ["", "## Preregistered falsifiable prediction", ""]
    if check.get("evaluated"):
        lines += [
            f"Restricting the census to the accepted `final_v4` "
            f"{check['panel_tasks']}-task panel gives "
            f"**{check['observed']['gradeable']} gradeable / "
            f"{check['observed']['not_gradeable']} not gradeable** against the "
            f"preregistered expectation of {check['expected']['gradeable']} / "
            f"{check['expected']['not_gradeable']}: "
            f"**{'CONFIRMED' if check['prediction_confirmed'] else 'MISMATCH — FLAG'}**.",
            "",
            "Non-gradeable panel tasks and their reasons:",
            "",
            "| task_uuid | reason |",
            "|---|---|",
        ]
        for task, reason in sorted(check["not_gradeable_reasons"].items()):
            lines.append(f"| `{task}` | `{reason}` |")
    else:
        lines.append(f"Not evaluated: {check.get('reason')}.")
    lines += [
        "",
        "## JW block",
        "",
        f"- corpus-complete model-eligible `jw_encoding` columns: "
        f"{len(report['jw_block']['corpus_complete_columns'])} "
        f"(coverage {JW_CORPUS_COMPLETE_COVERAGE}/{EXPECTED_TASKS})",
        f"- partial columns excluded from the null test: "
        f"{report['jw_block']['partial_columns']}",
        f"- whole-block-null tasks: {report['jw_block']['null_task_uuids']}",
        "",
        "## Conservative choices of record",
        "",
    ]
    for choice in report["conservative_choices"]:
        lines.append(f"- {choice}")
    lines += [
        "",
        "## Fences honoured",
        "",
        "- no solver outcome, metrics bundle, or campaign ledger was read",
        "- no committed artifact was modified; no public or dashboard placement",
        "- no selection, reweighting, or panel revision (that is ML-8B, held)",
        "- canonical family is carried for reporting only, never as a decision input",
        "",
    ]
    return "\n".join(lines)


def build_census(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Execute one complete deterministic ML-8A census build."""
    _require(
        not output_directory.exists(), f"output exists: {output_directory}"
    )
    preregistration = load_preregistration(preregistration_path)
    inputs = verify_pinned_inputs(root, preregistration)

    records, digests = load_corpus_tasks(root)
    taxonomy = json.loads(
        (root / inputs["canonical_families"]["path"]).read_text(encoding="utf-8")
    )
    canonical = canonical_family_map(taxonomy)
    metadata = pd.read_csv(root / inputs["feature_metadata"]["path"])
    features = pd.read_csv(
        root / inputs["feature_table"]["path"], low_memory=False
    )
    _require(
        len(features) == EXPECTED_TASKS, f"feature table row count: {len(features)}"
    )
    jw_block = jw_block_columns(metadata, features)
    jw_null = jw_null_tasks(features, jw_block["corpus_complete_columns"])

    rows = build_census_rows(records, canonical, jw_null)
    counts = reason_counts(rows)
    families = family_count_rows(rows)
    grades = grade_count_rows(rows)
    check = panel_cross_check(root, rows, preregistration)

    corpus_digest = {
        "instance_files": len(digests),
        "files": digests,
        "listing_sha256": corpus_listing_digest(digests),
    }
    held = {
        "artifact_id": CENSUS_ID,
        "status": "held_pending_pi_review",
        "effective": False,
        "eligibility_substrate_of_record": False,
        "modifies_committed_artifact": False,
        "reads_solver_outcomes": False,
    }
    census_payload = {
        **held,
        "preregistration": {
            "artifact_id": preregistration["artifact_id"],
            "path": str(preregistration_path.relative_to(root)),
            "sha256": sha256_file(preregistration_path),
        },
        "inputs": inputs,
        "corpus_digest": corpus_digest,
        "reference_grade_vocabulary": {
            "checkable": sorted(CHECKABLE_REFERENCE_GRADES),
            "not_checkable": sorted(NOT_CHECKABLE_REFERENCE_GRADES),
            "absent_sentinel": MISSING_GRADE,
        },
        "gradeability_reason_order": list(_REASON_ORDER),
        "jw_block": {
            **{key: jw_block[key] for key in ("corpus_complete_columns", "partial_columns", "coverage")},
            "enters_gradeability_boolean": False,
            "null_task_uuids": sorted(jw_null),
        },
        "tasks": rows,
    }
    report_payload = {
        **held,
        "artifact_id": "ml8a_gradeability_census_report_v1",
        "totals": {
            "n_tasks": len(rows),
            "n_gradeable": counts["gradeable"],
            "n_not_gradeable": len(rows) - counts["gradeable"],
            "n_canonical_families": len(families),
            "n_jw_block_null_infeasible": len(jw_null),
        },
        "reason_counts": counts,
        "grade_counts": grades,
        "family_counts": families,
        "jw_block": census_payload["jw_block"],
        "panel_cross_check": check,
        "conservative_choices": list(preregistration["conservative_choices"]),
        "inputs": inputs,
    }

    output_directory.mkdir(parents=True, exist_ok=False)
    stable_csv_dump(rows, CENSUS_COLUMNS, output_directory / "census.csv")
    stable_json_dump(census_payload, output_directory / "census.json")
    stable_csv_dump(
        families, FAMILY_COUNT_COLUMNS, output_directory / "family_counts.csv"
    )
    stable_csv_dump(grades, GRADE_COUNT_COLUMNS, output_directory / "grade_counts.csv")
    stable_json_dump(report_payload, output_directory / "report.json")
    stable_json_dump(
        _census_schema(), output_directory / "schemas/census.schema.json"
    )
    stable_json_dump(
        _report_schema(), output_directory / "schemas/report.schema.json"
    )
    (output_directory / "REPORT.md").write_text(
        _markdown_report(report_payload), encoding="utf-8"
    )

    manifest_files = sorted(
        path
        for path in output_directory.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    manifest = {
        "artifact_id": "ml8a_gradeability_census_manifest_v1",
        **{key: held[key] for key in held if key != "artifact_id"},
        "files": [
            {
                "path": str(path.relative_to(output_directory)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in manifest_files
        ],
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return {"census": census_payload, "report": report_payload, "manifest": manifest}
