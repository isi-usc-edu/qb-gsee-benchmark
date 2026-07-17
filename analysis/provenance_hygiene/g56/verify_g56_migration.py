#!/usr/bin/env python3
"""Independently verify the detached G-56 provenance-hygiene candidate."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


BASE_COMMIT = "665f436bffbde3f86541314837bd2f69479efc9c"
EXPECTED_COUNTS = {
    "problem_instances": 218,
    "tasks": 718,
    "provenance_moves": 264,
    "encoding_repairs": 8,
    "descriptor_backfills": 234,
    "threshold_annotations": 718,
    "planted_feature_backfills": 11,
    "catalog_changed_cells": 55,
    "catalog_changed_rows": 28,
    "artifact_renames": 4,
    "active_reference_updates": 2,
}
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE / "source_census"
PLAN_PATH = HERE / "g56_migration_plan.json"
LEDGER_PATH = HERE / "g56_migration_ledger.json"


class Verification:
    def __init__(self) -> None:
        self.checks: list[str] = []

    def require(self, condition: bool, label: str, detail: str = "") -> None:
        if not condition:
            suffix = f": {detail}" if detail else ""
            raise AssertionError(f"{label}{suffix}")
        self.checks.append(label)

    def report(self) -> dict[str, Any]:
        return {
            "base_commit": BASE_COMMIT,
            "check_count": len(self.checks),
            "checks": self.checks,
            "goal": "G-56",
            "result": "pass",
            "status": "held_candidate_pending_pi_ack",
        }


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def base_bytes(relative: str) -> bytes:
    return git_output("show", f"{BASE_COMMIT}:{relative}")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def base_json(relative: str) -> Any:
    return json.loads(base_bytes(relative))


def pointer_parts(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise AssertionError(f"invalid JSON pointer: {pointer}")
    return [
        part.replace("~1", "/").replace("~0", "~")
        for part in pointer[1:].split("/")
    ]


def pointer_get(document: Any, pointer: str) -> Any:
    current = document
    for part in pointer_parts(pointer):
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def pointer_set(document: Any, pointer: str, value: Any) -> None:
    parts = pointer_parts(pointer)
    current = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    leaf = parts[-1]
    if isinstance(current, list):
        current[int(leaf)] = value
    else:
        current[leaf] = value


def task_index(document: dict[str, Any]) -> dict[str, int]:
    return {task["task_uuid"]: index for index, task in enumerate(document["tasks"])}


def threshold_value(convention: dict[str, Any]) -> float:
    parameters = convention["formula_parameters"]
    kind = convention["kind"]
    count = convention["scale_count"]
    if kind in {"fixed", "control"}:
        return parameters["fixed_value_hartree"]
    if kind == "per_site":
        return parameters["per_unit_value_hartree"] * count
    if kind == "hybrid_per_site_statistical_floor":
        return max(
            parameters["per_unit_value_hartree"] * count,
            parameters["statistical_floor_multiplier"]
            * parameters["reference_standard_error_hartree"],
        )
    if kind == "per_site_energy_scaled":
        return (
            parameters["per_site_dimensionless_factor"]
            * count
            * parameters["energy_scale_hartree"]
        )
    raise AssertionError(f"unapproved threshold kind: {kind}")


def instance_paths_at_base() -> list[str]:
    output = git_output(
        "ls-tree", "-r", "--name-only", BASE_COMMIT, "--", "problem_instances"
    ).decode()
    return sorted(line for line in output.splitlines() if line.endswith(".json"))


def rows_by_path(plan: dict[str, Any], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in plan[key]:
        relative = f"problem_instances/{row['problem_instance_path']}"
        grouped.setdefault(relative, []).append(row)
    return grouped


def all_task_locations(
    paths: list[str],
) -> tuple[dict[str, tuple[str, int]], dict[str, dict[str, Any]]]:
    locations: dict[str, tuple[str, int]] = {}
    documents: dict[str, dict[str, Any]] = {}
    for relative in paths:
        document = base_json(relative)
        documents[relative] = document
        for index, task in enumerate(document["tasks"]):
            task_uuid = task["task_uuid"]
            if task_uuid in locations:
                raise AssertionError(f"duplicate task UUID at base: {task_uuid}")
            locations[task_uuid] = (relative, index)
    return locations, documents


def add_expected_internal_record(
    document: dict[str, Any], row: dict[str, Any], original: str
) -> None:
    match = re.match(r"^/tasks/(\d+)(?:/|$)", row["json_pointer"])
    owner = document["tasks"][int(match.group(1))] if match else document
    records = owner.setdefault("internal_provenance", {}).setdefault(
        "migration_records", []
    )
    records.append(
        {
            "original_json_pointer": row["json_pointer"],
            "original_value": original,
            "original_value_sha256": row["original_value_sha256"],
            "public_replacement_pointer": row["json_pointer"],
            "public_replacement_value_sha256": row[
                "public_replacement_sha256"
            ],
            "internal_pointer_classes": row["internal_pointer_classes"],
        }
    )


def verify_plan_and_sources(
    verification: Verification, plan: dict[str, Any]
) -> None:
    verification.require(plan["goal"] == "G-56", "plan goal is G-56")
    verification.require(
        plan["source_repository_commit"] == BASE_COMMIT,
        "plan pins the approved base commit",
    )
    verification.require(
        plan["status"] == "held_candidate_pending_pi_ack"
        and plan["public_merge_authorized"] is False,
        "candidate remains held and public merge unauthorized",
    )
    verification.require(
        plan["counts"] == EXPECTED_COUNTS,
        "plan counts match the PI-approved census",
        repr(plan["counts"]),
    )
    for name, expected_hash in plan["source_census_sha256"].items():
        actual_hash = sha256_file(SOURCE / name)
        if actual_hash != expected_hash:
            raise AssertionError(f"source census hash drift: {name}")
    verification.require(True, "all eight source census files are hash-pinned")


def verify_instances(
    verification: Verification,
    plan: dict[str, Any],
    ledger: dict[str, Any],
) -> None:
    paths = instance_paths_at_base()
    current_paths = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "problem_instances").rglob("*.json")
    )
    verification.require(
        paths == current_paths and len(paths) == EXPECTED_COUNTS["problem_instances"],
        "instance file set is unchanged",
    )
    locations, base_documents = all_task_locations(paths)
    verification.require(
        len(locations) == EXPECTED_COUNTS["tasks"],
        "task UUID set is unique and unchanged",
    )

    provenance = rows_by_path(plan, "provenance_moves")
    encoding = rows_by_path(plan, "encoding_repairs")
    descriptors = rows_by_path(plan, "descriptor_backfills")
    planted = rows_by_path(plan, "planted_feature_backfills")
    thresholds: dict[str, list[dict[str, Any]]] = {}
    for row in plan["threshold_annotations"]:
        relative, _ = locations[row["task_uuid"]]
        thresholds.setdefault(relative, []).append(row)

    numeric_reference_count = 0
    support_record_count = 0
    threshold_kinds: Counter[str] = Counter()
    for relative in paths:
        base = base_documents[relative]
        current = load_json(ROOT / relative)
        expected = copy.deepcopy(base)
        indices = task_index(base)

        base_uuids = [task["task_uuid"] for task in base["tasks"]]
        current_uuids = [task["task_uuid"] for task in current["tasks"]]
        if base_uuids != current_uuids:
            raise AssertionError(f"task UUID/order changed: {relative}")

        for base_task, current_task in zip(base["tasks"], current["tasks"]):
            base_requirements = base_task["requirements"]
            current_requirements = current_task["requirements"]
            if base_requirements.get("reference_energy") != current_requirements.get(
                "reference_energy"
            ):
                raise AssertionError(f"reference energy changed: {base_task['task_uuid']}")
            numeric_reference_count += "reference_energy" in base_requirements
            if base_requirements["absolute_accuracy_threshold"] != current_requirements[
                "absolute_accuracy_threshold"
            ]:
                raise AssertionError(
                    f"absolute threshold changed: {base_task['task_uuid']}"
                )
            base_support = base_task.get("supporting_files", [])
            current_support = current_task.get("supporting_files", [])
            if base_support != current_support:
                raise AssertionError(
                    f"supporting-file metadata changed: {base_task['task_uuid']}"
                )
            support_record_count += len(base_support)

        for row in provenance.get(relative, []):
            original = pointer_get(base, row["json_pointer"])
            if not isinstance(original, str):
                raise AssertionError(f"non-string provenance source: {relative}")
            if sha256_bytes(original.encode()) != row["original_value_sha256"]:
                raise AssertionError(f"provenance original hash mismatch: {relative}")
            replacement = row["public_replacement"]
            if sha256_bytes(replacement.encode()) != row["public_replacement_sha256"]:
                raise AssertionError(f"provenance replacement hash mismatch: {relative}")
            pointer_set(expected, row["json_pointer"], replacement)
            add_expected_internal_record(expected, row, original)

        for row in encoding.get(relative, []):
            original = pointer_get(base, row["json_pointer"])
            replacement = bytes.fromhex(row["replacement_utf8_hex"]).decode("utf-8")
            if original.encode().hex() != row["original_utf8_hex"]:
                raise AssertionError(f"encoding before-hex mismatch: {relative}")
            if sha256_bytes(replacement.encode()) != row["replacement_value_sha256"]:
                raise AssertionError(f"encoding replacement hash mismatch: {relative}")
            pointer_set(expected, row["json_pointer"], replacement)

        for row in descriptors.get(relative, []):
            if (
                row["header_num_orbitals"] != row["feature_table_num_orbitals"]
                or row["header_num_electrons"] != row["feature_table_num_electrons"]
            ):
                raise AssertionError(f"header/feature mismatch: {row['task_uuid']}")
            features = expected["tasks"][indices[row["task_uuid"]]].setdefault(
                "features", {}
            )
            features["num_orbitals"] = row["header_num_orbitals"]
            features["num_electrons"] = row["header_num_electrons"]

        for row in thresholds.get(relative, []):
            index = indices[row["task_uuid"]]
            convention = {
                key: copy.deepcopy(row[key])
                for key in (
                    "kind",
                    "display_label",
                    "formula",
                    "scale_count",
                    "formula_parameters",
                    "computed_threshold_hartree",
                    "detail",
                )
            }
            computed = threshold_value(convention)
            stored = expected["tasks"][index]["requirements"][
                "absolute_accuracy_threshold"
            ]
            if computed != convention["computed_threshold_hartree"] or computed != stored:
                raise AssertionError(f"threshold formula mismatch: {row['task_uuid']}")
            threshold_kinds[convention["kind"]] += 1
            expected["tasks"][index]["requirements"][
                "threshold_convention"
            ] = convention

        for row in planted.get(relative, []):
            index = indices[row["task_uuid"]]
            task = expected["tasks"][index]
            if task.get("planted_solution") != row["authoritative_task_value"]:
                raise AssertionError(f"planted authority mismatch: {row['task_uuid']}")
            task.setdefault("features", {})["planted_solution"] = row[
                "feature_layer_value"
            ]

        if expected != current:
            raise AssertionError(
                f"unapproved semantic change in {relative}; candidate differs from "
                "base plus the explicit G-56 plan"
            )

    verification.require(
        numeric_reference_count > 0,
        "all numerical reference energies are unchanged",
        str(numeric_reference_count),
    )
    verification.require(
        support_record_count > 0,
        "all supporting-file URLs and checksums are unchanged",
        str(support_record_count),
    )
    verification.require(
        threshold_kinds
        == {
            "fixed": 421,
            "control": 9,
            "per_site": 239,
            "hybrid_per_site_statistical_floor": 48,
            "per_site_energy_scaled": 1,
        },
        "all threshold formulas recompute exactly by approved kind",
    )
    verification.require(
        sum(len(rows) for rows in provenance.values()) == 264,
        "264 public provenance replacements have exact internal mirrors",
    )
    verification.require(
        sum(len(rows) for rows in encoding.values()) == 8,
        "eight encoding repairs match the byte ledger",
    )
    verification.require(
        sum(len(rows) for rows in descriptors.values()) == 234,
        "234 descriptor backfills agree with FCIDUMP headers and feature table",
    )
    verification.require(
        sum(len(rows) for rows in planted.values()) == 11,
        "11 planted task flags are mirrored at the feature layer",
    )
    verification.require(
        True,
        "all instance semantics equal base plus only approved transformations",
    )

    hash_rows = {row["path"]: row for row in ledger["instance_file_hashes"]}
    if set(hash_rows) != set(paths):
        raise AssertionError("instance hash ledger file set differs from corpus")
    for relative in paths:
        row = hash_rows[relative]
        if row["before_sha256"] != sha256_bytes(base_bytes(relative)):
            raise AssertionError(f"base file hash mismatch: {relative}")
        if row["after_sha256"] != sha256_file(ROOT / relative):
            raise AssertionError(f"candidate file hash mismatch: {relative}")
    verification.require(True, "all 218 before/after instance hashes verify")


def verify_catalog_and_vocabulary(
    verification: Verification,
    plan: dict[str, Any],
    ledger: dict[str, Any],
) -> None:
    relative = "analysis/feature_schema/feature_column_metadata.csv"
    base_text = base_bytes(relative).decode()
    current_text = (ROOT / relative).read_text(encoding="utf-8")
    base_rows = list(csv.DictReader(base_text.splitlines()))
    current_rows = list(csv.DictReader(current_text.splitlines()))
    if len(base_rows) != len(current_rows):
        raise AssertionError("feature catalog row count changed")
    actual_changes: dict[str, tuple[str, str]] = {}
    changed_columns: set[str] = set()
    for before, after in zip(base_rows, current_rows):
        if before["column"] != after["column"]:
            raise AssertionError("feature catalog row order/name changed")
        for field in before:
            if before[field] != after[field]:
                locator = f"{before['column']}:{field}"
                actual_changes[locator] = (before[field], after[field])
                changed_columns.add(before["column"])
    approved = {
        row["locator"]: (row["current_value"], row["proposed_value"])
        for row in plan["feature_catalog_changes"]
    }
    verification.require(
        actual_changes == approved
        and len(actual_changes) == 55
        and len(changed_columns) == 28,
        "feature catalog changes exactly 55 approved cells across 28 rows",
    )
    verification.require(
        sum(
            row["model_eligible"] == "True" and row["cost_class"] == "jw_encoding"
            for row in current_rows
        )
        == 17,
        "post-migration model-eligible JW catalog has 17 columns",
    )
    catalog_hash = ledger["feature_catalog_file_hash"]
    verification.require(
        catalog_hash["before_sha256"] == sha256_bytes(base_text.encode())
        and catalog_hash["after_sha256"] == sha256_bytes(current_text.encode()),
        "feature catalog before/after hashes verify",
    )

    sys.path.insert(0, str(ROOT / "src"))
    from qb_gsee_benchmark.features.feature_schema import metadata_catalog

    with (ROOT / "scripts/Hamiltonian_features.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        columns = next(csv.reader(handle))
    source_rows = [row.to_dict() for row in metadata_catalog(columns)]
    rendered = io.StringIO(newline="")
    writer = csv.DictWriter(
        rendered, fieldnames=list(source_rows[0]), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(source_rows)
    verification.require(
        rendered.getvalue() == current_text,
        "live Python metadata API regenerates the G-56 catalog byte-exact",
    )

    for row in plan["artifact_renames"]:
        old_path = ROOT / row["old_path"]
        new_path = ROOT / row["new_path"]
        if old_path.exists() or not new_path.is_file():
            raise AssertionError(f"artifact rename missing: {row['old_path']}")
        if sha256_bytes(base_bytes(row["old_path"])) != row["before_sha256"]:
            raise AssertionError(f"renamed base hash mismatch: {row['old_path']}")
        if sha256_file(new_path) != row["after_sha256"]:
            raise AssertionError(f"renamed candidate hash mismatch: {row['new_path']}")
    verification.require(True, "four prototype artifact renames verify")

    for row in plan["active_reference_updates"]:
        before = base_bytes(row["path"])
        old, new = row["old_value"].encode(), row["new_value"].encode()
        if before.count(old) != 1:
            raise AssertionError(f"unexpected base reference count: {row['path']}")
        expected = before.replace(old, new)
        if (ROOT / row["path"]).read_bytes() != expected:
            raise AssertionError(f"unapproved active-reference edit: {row['path']}")
    verification.require(True, "two active prototype references changed exactly once")

    for relative in plan["explicit_exclusions"]:
        if (ROOT / relative).read_bytes() != base_bytes(relative):
            raise AssertionError(f"byte-pinned exclusion changed: {relative}")
    verification.require(True, "both historical byte-pinned artifacts are unchanged")


def verify_public_projection_and_schemas(
    verification: Verification, paths: list[str]
) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from qb_gsee_benchmark.public_provenance import public_provenance_view

    with (SOURCE / "g56_public_provenance_census.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        internal_values = {
            row["value"]
            for row in csv.DictReader(handle)
            if row["internal_pointer"] == "True"
        }
    local_path = re.compile(r"(?<![A-Za-z0-9_:/.-])(?:analysis|work|scripts)/")
    for relative in paths:
        rendered = json.dumps(
            public_provenance_view(load_json(ROOT / relative)), ensure_ascii=False
        )
        if "internal_provenance" in rendered or "MATT_DECISION_QUEUE" in rendered:
            raise AssertionError(f"internal field leaked in public projection: {relative}")
        if any(value in rendered for value in internal_values):
            raise AssertionError(f"internal value leaked in public projection: {relative}")
        if local_path.search(rendered):
            raise AssertionError(f"local path leaked in public projection: {relative}")
    verification.require(True, "public projection excludes all internal fields and values")

    schema_paths = [
        ROOT / "schemas/problem_instance.schema.0.0.2.json",
        ROOT / "schemas/uuid.schema.json",
        ROOT / "schemas/timestamp.schema.json",
    ]
    schemas = [load_json(path) for path in schema_paths]
    registry = Registry()
    for schema in schemas:
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    Draft202012Validator.check_schema(schemas[0])
    validator = Draft202012Validator(schemas[0], registry=registry)
    errors = []
    for relative in paths:
        errors.extend(validator.iter_errors(load_json(ROOT / relative)))
    verification.require(
        not errors,
        "all 218 migrated instances validate against the problem schema",
        "; ".join(error.message for error in errors[:5]),
    )

    solution_schema = load_json(ROOT / "schemas/solution.schema.0.0.1.json")
    Draft202012Validator.check_schema(solution_schema)
    resources = solution_schema["properties"]["solution_data"]["items"][
        "properties"
    ]["classical_resources"]
    resource_validator = Draft202012Validator(resources)
    resource_validator.validate({})
    resource_validator.validate(
        {
            "peak_rss_bytes": 697_540_608,
            "peak_rss_measurement_method": "/usr/bin/time -v maximum resident set size",
        }
    )
    required = set(resources.get("required", []))
    verification.require(
        "peak_rss_bytes" not in required
        and "peak_rss_measurement_method" not in required,
        "GO-3 peak RSS bytes and method remain optional",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    verification = Verification()
    plan = load_json(PLAN_PATH)
    ledger = load_json(LEDGER_PATH)
    verify_plan_and_sources(verification, plan)
    verify_instances(verification, plan, ledger)
    verify_catalog_and_vocabulary(verification, plan, ledger)
    paths = instance_paths_at_base()
    verify_public_projection_and_schemas(verification, paths)

    subprocess.run(
        [sys.executable, str(HERE / "build_g56_migration.py"), "--mode", "check"],
        cwd=ROOT,
        check=True,
    )
    verification.require(True, "migration generator check-mode is byte-exact")

    report = verification.report()
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(f"PASS: {report['check_count']} independent G-56 checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
