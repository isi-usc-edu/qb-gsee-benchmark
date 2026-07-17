#!/usr/bin/env python3
"""Build or verify the detached G-56 provenance-hygiene migration candidate."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO


BASE_COMMIT = "665f436bffbde3f86541314837bd2f69479efc9c"
EXPECTED = {
    "instances": 218,
    "tasks": 718,
    "provenance_moves": 264,
    "provenance_unique_values": 47,
    "encoding_repairs": 8,
    "descriptor_backfills": 234,
    "threshold_annotations": 718,
    "planted_feature_backfills": 11,
    "catalog_changed_cells": 55,
    "catalog_changed_rows": 28,
}
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROJECT = ROOT.parents[2]
SOURCE = HERE / "source_census"
REPLACEMENTS = HERE / "public_replacements.json"
FEATURE_TABLE = ROOT / "scripts/Hamiltonian_features.csv"
OLD_CACHE = PROJECT / "work/feature_runs/g40_p1a_pilot/cache"
DOWNLOAD_CACHE = ROOT.parent / "fcidump_cache"
COMMITTED_PLAN = HERE / "g56_migration_plan.json"
COMMITTED_LEDGER = HERE / "g56_migration_ledger.json"

ARTIFACT_RENAMES = {
    "analysis/solver_panel/g31_legacy_lattice_task_mapping.csv":
        "analysis/solver_panel/g31_prototype_lattice_task_mapping.csv",
    "analysis/solver_panel/g31_legacy_lattice_task_mapping.json":
        "analysis/solver_panel/g31_prototype_lattice_task_mapping.json",
    "analysis/solver_panel/g31_legacy_lattice_task_mapping.md":
        "analysis/solver_panel/g31_prototype_lattice_task_mapping.md",
    "scripts/solver_panel/build_legacy_lattice_task_mapping.py":
        "scripts/solver_panel/build_prototype_lattice_task_mapping.py",
}
REFERENCE_UPDATES = {
    "scripts/export_metrics_bundle.py": (
        "g31_legacy_lattice_task_mapping.csv",
        "g31_prototype_lattice_task_mapping.csv",
    ),
    "scripts/generate_lattice_thresholds.py": (
        "g31_legacy_lattice_task_mapping.csv",
        "g31_prototype_lattice_task_mapping.csv",
    ),
}
BYTE_PINNED = (
    "scripts/dashboard_data/metrics_v1_9.json",
    "analysis/feature_schema/g40_p1d_legacy_comparison.md",
)


def digest_bytes(payload: bytes, algorithm: str = "sha256") -> str:
    result = hashlib.new(algorithm)
    result.update(payload)
    return result.hexdigest()


def digest_file(path: Path, algorithm: str = "sha256") -> str:
    result = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def base_bytes(relative: str) -> bytes:
    return subprocess.check_output(
        ["git", "show", f"{BASE_COMMIT}:{relative}"], cwd=ROOT
    )


def base_json(relative: str) -> dict[str, Any]:
    return json.loads(base_bytes(relative))


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def stable_json(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def instance_json(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode()


def pointer_parts(pointer: str) -> list[str]:
    if not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {pointer}")
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


def task_for_pointer(document: dict[str, Any], pointer: str) -> dict[str, Any] | None:
    match = re.match(r"^/tasks/(\d+)(?:/|$)", pointer)
    return document["tasks"][int(match.group(1))] if match else None


def add_internal_record(
    document: dict[str, Any],
    pointer: str,
    original: str,
    replacement: str,
    classes: list[str],
) -> None:
    owner = task_for_pointer(document, pointer) or document
    internal = owner.setdefault("internal_provenance", {})
    records = internal.setdefault("migration_records", [])
    records.append(
        {
            "original_json_pointer": pointer,
            "original_value": original,
            "original_value_sha256": digest_bytes(original.encode()),
            "public_replacement_pointer": pointer,
            "public_replacement_value_sha256": digest_bytes(replacement.encode()),
            "internal_pointer_classes": classes,
        }
    )


def feature_sizes() -> dict[str, tuple[int, int]]:
    rows = csv_rows(FEATURE_TABLE)
    result = {
        row["task_uuid"]: (int(float(row["n_orbs"])), int(float(row["n_elec"])))
        for row in rows
    }
    if len(result) != EXPECTED["tasks"]:
        raise RuntimeError(f"feature-table row drift: {len(result)}")
    return result


def fcidump_support(task: dict[str, Any]) -> dict[str, Any]:
    records = [
        item for item in task["supporting_files"] if item.get("is_fcidump_file") is True
    ]
    if len(records) != 1:
        raise ValueError(f"{task['task_uuid']}: expected one FCIDUMP, got {len(records)}")
    return records[0]


def local_object(task: dict[str, Any]) -> Path:
    support = fcidump_support(task)
    object_uuid = support["instance_data_object_uuid"]
    candidates = [
        OLD_CACHE / f"{object_uuid}.fcidump.gz",
        OLD_CACHE / f"{object_uuid}.fcidump",
        DOWNLOAD_CACHE / f"{task['task_uuid']}.object",
    ]
    matches = [path for path in candidates if path.is_file()]
    if len(matches) != 1:
        raise FileNotFoundError(f"{task['task_uuid']}: local object candidates={matches}")
    return matches[0]


def offline_descriptor_rows(mode: str) -> dict[str, dict[str, Any]]:
    """Load reviewed descriptor evidence for a cache-free check-mode replay."""
    if mode != "check":
        return {}
    plan = json.loads(COMMITTED_PLAN.read_text(encoding="utf-8"))
    rows = {
        row["task_uuid"]: row for row in plan.get("descriptor_backfills", [])
    }
    if len(rows) != EXPECTED["descriptor_backfills"]:
        raise RuntimeError("committed descriptor evidence is incomplete")
    return rows


def stream_header(handle: BinaryIO) -> tuple[int, int]:
    chunks: list[str] = []
    for _ in range(80):
        raw = handle.readline()
        if not raw:
            break
        line = raw.decode("utf-8", errors="replace")
        chunks.append(line)
        if "/" in line or "&END" in line.upper():
            break
    header = " ".join(chunks)
    norb = re.search(r"\bNORB\s*=\s*(\d+)", header, re.IGNORECASE)
    nelec = re.search(r"\bNELEC\s*=\s*(\d+)", header, re.IGNORECASE)
    if not norb or not nelec:
        raise ValueError(f"FCIDUMP header lacks NORB/NELEC: {header[:500]}")
    return int(norb.group(1)), int(nelec.group(1))


def read_fcidump_header(path: Path) -> tuple[int, int, str | None]:
    signature = path.read_bytes()[:4]
    if signature[:2] == b"\x1f\x8b":
        with gzip.open(path, "rb") as handle:
            norb, nelec = stream_header(handle)
        return norb, nelec, None
    if signature == b"PK\x03\x04":
        with zipfile.ZipFile(path) as archive:
            members = [
                name for name in archive.namelist()
                if not name.endswith("/") and "fcidump" in name.lower()
            ]
            if len(members) != 1:
                raise ValueError(f"{path}: expected one FCIDUMP zip member, got {members}")
            with archive.open(members[0]) as handle:
                norb, nelec = stream_header(handle)
        return norb, nelec, members[0]
    with path.open("rb") as handle:
        norb, nelec = stream_header(handle)
    return norb, nelec, None


def threshold_object(
    document: dict[str, Any],
    task: dict[str, Any],
    proposal: dict[str, str],
) -> dict[str, Any]:
    kind = proposal["proposed_threshold_convention"]
    threshold = task["requirements"]["absolute_accuracy_threshold"]
    scale_count = int(proposal["scale_count"]) if proposal["scale_count"] else None

    if kind in {"fixed", "control"}:
        formula = "fixed_value_hartree"
        parameters = {"fixed_value_hartree": threshold}
        computed = parameters["fixed_value_hartree"]
    elif kind == "per_site":
        unit = 0.0001 if document["short_name"] == "simons_hydrogen_chains" else 0.001
        formula = "per_unit_value_hartree * scale_count"
        parameters = {"per_unit_value_hartree": unit}
        computed = unit * scale_count
    elif kind == "hybrid_per_site_statistical_floor":
        standard_error = task["requirements"]["reference_energy_standard_error"]
        formula = (
            "max(per_unit_value_hartree * scale_count, "
            "statistical_floor_multiplier * reference_standard_error_hartree)"
        )
        parameters = {
            "per_unit_value_hartree": 0.001,
            "statistical_floor_multiplier": 2.0,
            "reference_standard_error_hartree": standard_error,
        }
        computed = max(0.001 * scale_count, 2.0 * standard_error)
    elif kind == "per_site_energy_scaled":
        energy_scale = abs(task["features"]["hopping_t_hartree"])
        formula = "per_site_dimensionless_factor * scale_count * energy_scale_hartree"
        parameters = {
            "per_site_dimensionless_factor": 0.001,
            "energy_scale_hartree": energy_scale,
        }
        computed = 0.001 * scale_count * energy_scale
    else:
        raise ValueError(f"unknown threshold kind: {kind}")

    if computed != threshold:
        raise ValueError(
            f"{task['task_uuid']}: computed threshold {computed!r} != stored {threshold!r}"
        )
    return {
        "kind": kind,
        "display_label": proposal["proposed_display_label"],
        "formula": formula,
        "scale_count": scale_count,
        "formula_parameters": parameters,
        "computed_threshold_hartree": computed,
        "detail": proposal["convention_detail"],
    }


def build_instances(mode: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    provenance = [
        row for row in csv_rows(SOURCE / "g56_public_provenance_census.csv")
        if row["internal_pointer"] == "True"
    ]
    encoding = csv_rows(SOURCE / "g56_encoding_defect_census.csv")
    descriptors = csv_rows(SOURCE / "g56_missing_size_descriptor_census.csv")
    thresholds = csv_rows(SOURCE / "g56_threshold_convention_proposal.csv")
    replacement_doc = json.loads(REPLACEMENTS.read_text(encoding="utf-8"))
    replacements = replacement_doc["replacements"]

    if len(provenance) != EXPECTED["provenance_moves"]:
        raise RuntimeError("provenance census drift")
    if len(set(row["value"] for row in provenance)) != EXPECTED["provenance_unique_values"]:
        raise RuntimeError("provenance unique-value drift")
    if set(replacements) != {row["value"] for row in provenance}:
        raise RuntimeError("explicit replacement table does not cover the census exactly")
    if len(encoding) != EXPECTED["encoding_repairs"]:
        raise RuntimeError("encoding census drift")
    if len(descriptors) != EXPECTED["descriptor_backfills"]:
        raise RuntimeError("descriptor census drift")
    if len(thresholds) != EXPECTED["threshold_annotations"]:
        raise RuntimeError("threshold census drift")

    instance_paths = sorted(
        f"problem_instances/{path}"
        for path in {
            row["problem_instance_path"] for row in
            csv_rows(SOURCE / "g56_public_provenance_census.csv")
        }
    )
    if len(instance_paths) != EXPECTED["instances"]:
        raise RuntimeError(f"instance census drift: {len(instance_paths)}")

    documents = {path: base_json(path) for path in instance_paths}
    before = {path: base_bytes(path) for path in instance_paths}
    task_index: dict[str, tuple[str, dict[str, Any]]] = {}
    task_count = 0
    for path, document in documents.items():
        for task in document["tasks"]:
            task_count += 1
            task_uuid = task["task_uuid"]
            if task_uuid in task_index:
                raise ValueError(f"duplicate task UUID: {task_uuid}")
            task_index[task_uuid] = (path, task)
    if task_count != EXPECTED["tasks"]:
        raise RuntimeError(f"task census drift: {task_count}")

    provenance_plan: list[dict[str, Any]] = []
    for row in provenance:
        path = f"problem_instances/{row['problem_instance_path']}"
        document = documents[path]
        pointer = row["json_pointer"]
        original = pointer_get(document, pointer)
        if original != row["value"]:
            raise ValueError(f"{path}{pointer}: provenance source drift")
        replacement = replacements[original]
        pointer_set(document, pointer, replacement)
        classes = [item for item in row["internal_pointer_classes"].split(";") if item]
        add_internal_record(document, pointer, original, replacement, classes)
        provenance_plan.append(
            {
                "problem_instance_path": row["problem_instance_path"],
                "task_uuid": row["task_uuid"] or None,
                "json_pointer": pointer,
                "field_key": row["field_key"],
                "original_value_sha256": digest_bytes(original.encode()),
                "public_replacement": replacement,
                "public_replacement_sha256": digest_bytes(replacement.encode()),
                "internal_pointer_classes": classes,
            }
        )

    encoding_ledger: list[dict[str, Any]] = []
    for row in encoding:
        path = f"problem_instances/{row['problem_instance_path']}"
        document = documents[path]
        pointer = row["json_pointer"]
        original = pointer_get(document, pointer)
        if original != row["original_value"]:
            raise ValueError(f"{path}{pointer}: encoding source drift")
        repaired = original.encode("cp1252").decode("utf-8")
        if repaired != row["proposed_value"]:
            raise ValueError(f"{path}{pointer}: nondeterministic encoding repair")
        pointer_set(document, pointer, repaired)
        encoding_ledger.append(
            {
                "problem_instance_path": row["problem_instance_path"],
                "task_uuid": row["task_uuid"] or None,
                "json_pointer": pointer,
                "repair_method": row["repair_method"],
                "original_utf8_hex": original.encode().hex(),
                "replacement_utf8_hex": repaired.encode().hex(),
                "original_value_sha256": digest_bytes(original.encode()),
                "replacement_value_sha256": digest_bytes(repaired.encode()),
            }
        )

    sizes = feature_sizes()
    offline_descriptors = offline_descriptor_rows(mode)
    descriptor_ledger: list[dict[str, Any]] = []
    for row in descriptors:
        path, task = task_index[row["task_uuid"]]
        expected_path = f"problem_instances/{row['problem_instance_path']}"
        if path != expected_path:
            raise ValueError(f"{row['task_uuid']}: descriptor path drift")
        support = fcidump_support(task)
        for key, source_key in (
            ("instance_data_object_url", "fcidump_url"),
            ("instance_data_checksum_type", "fcidump_checksum_type"),
            ("instance_data_checksum", "fcidump_checksum"),
        ):
            if support[key] != row[source_key]:
                raise ValueError(f"{row['task_uuid']}: supporting-file census drift")
        if support["instance_data_checksum_type"] != "sha1sum":
            raise ValueError(f"{row['task_uuid']}: unsupported checksum")
        proposed = (int(row["proposed_num_orbitals"]), int(row["proposed_num_electrons"]))
        try:
            local = local_object(task)
        except FileNotFoundError:
            if mode != "check":
                raise
            evidence = offline_descriptors[row["task_uuid"]]
            expected_evidence = {
                "task_uuid": row["task_uuid"],
                "problem_instance_path": row["problem_instance_path"],
                "fcidump_url": support["instance_data_object_url"],
                "fcidump_sha1": support["instance_data_checksum"],
                "header_num_orbitals": proposed[0],
                "header_num_electrons": proposed[1],
                "feature_table_num_orbitals": sizes[row["task_uuid"]][0],
                "feature_table_num_electrons": sizes[row["task_uuid"]][1],
            }
            for key, value in expected_evidence.items():
                if evidence.get(key) != value:
                    raise ValueError(
                        f"{row['task_uuid']}: offline descriptor evidence drift in {key}"
                    )
            norb = evidence["header_num_orbitals"]
            nelec = evidence["header_num_electrons"]
            descriptor_entry = {
                "task_uuid": evidence["task_uuid"],
                "problem_instance_path": evidence["problem_instance_path"],
                "fcidump_url": evidence["fcidump_url"],
                "fcidump_sha1": evidence["fcidump_sha1"],
                "local_object_path": evidence["local_object_path"],
                "zip_member": evidence["zip_member"],
                "header_num_orbitals": norb,
                "header_num_electrons": nelec,
                "feature_table_num_orbitals": evidence[
                    "feature_table_num_orbitals"
                ],
                "feature_table_num_electrons": evidence[
                    "feature_table_num_electrons"
                ],
            }
        else:
            actual_checksum = digest_file(local, "sha1")
            if actual_checksum != support["instance_data_checksum"]:
                raise ValueError(f"{row['task_uuid']}: FCIDUMP checksum mismatch")
            norb, nelec, zip_member = read_fcidump_header(local)
            descriptor_entry = {
                "task_uuid": row["task_uuid"],
                "problem_instance_path": row["problem_instance_path"],
                "fcidump_url": support["instance_data_object_url"],
                "fcidump_sha1": actual_checksum,
                "local_object_path": str(local.relative_to(PROJECT)),
                "zip_member": zip_member,
                "header_num_orbitals": norb,
                "header_num_electrons": nelec,
                "feature_table_num_orbitals": sizes[row["task_uuid"]][0],
                "feature_table_num_electrons": sizes[row["task_uuid"]][1],
            }
        if (norb, nelec) != proposed or sizes[row["task_uuid"]] != proposed:
            raise ValueError(f"{row['task_uuid']}: header/census/feature-table mismatch")
        features = task.setdefault("features", {})
        if "num_orbitals" in features or "num_electrons" in features:
            raise ValueError(f"{row['task_uuid']}: descriptor no longer missing")
        features["num_orbitals"] = norb
        features["num_electrons"] = nelec
        descriptor_ledger.append(descriptor_entry)

    threshold_by_task = {row["task_uuid"]: row for row in thresholds}
    threshold_plan: list[dict[str, Any]] = []
    for task_uuid, (path, task) in sorted(task_index.items()):
        proposal = threshold_by_task[task_uuid]
        document = documents[path]
        convention = threshold_object(document, task, proposal)
        if "threshold_convention" in task["requirements"]:
            raise ValueError(f"{task_uuid}: threshold convention already exists")
        task["requirements"]["threshold_convention"] = convention
        threshold_plan.append({"task_uuid": task_uuid, **convention})

    planted_plan: list[dict[str, Any]] = []
    for path, document in documents.items():
        if not path.startswith("problem_instances/planted_solutions/"):
            continue
        for task in document["tasks"]:
            if task.get("planted_solution") is not True:
                raise ValueError(f"{task['task_uuid']}: task planted flag is not authoritative")
            features = task.setdefault("features", {})
            if "planted_solution" in features and features["planted_solution"] is not True:
                raise ValueError(f"{task['task_uuid']}: conflicting planted flags")
            features["planted_solution"] = True
            planted_plan.append(
                {
                    "task_uuid": task["task_uuid"],
                    "problem_instance_path": path.removeprefix("problem_instances/"),
                    "authoritative_task_value": True,
                    "feature_layer_value": True,
                }
            )
    if len(planted_plan) != EXPECTED["planted_feature_backfills"]:
        raise RuntimeError(f"planted feature count drift: {len(planted_plan)}")

    file_ledger: list[dict[str, Any]] = []
    after: dict[str, bytes] = {}
    for path, document in sorted(documents.items()):
        for owner in [document, *document["tasks"]]:
            records = owner.get("internal_provenance", {}).get("migration_records")
            if records:
                records.sort(key=lambda item: item["original_json_pointer"])
        payload = instance_json(document)
        after[path] = payload
        file_ledger.append(
            {
                "path": path,
                "before_sha256": digest_bytes(before[path]),
                "after_sha256": digest_bytes(payload),
            }
        )
        target = ROOT / path
        if mode == "apply":
            target.write_bytes(payload)
        elif target.read_bytes() != payload:
            raise RuntimeError(f"candidate bytes differ from generator: {path}")

    file_hashes = {row["path"]: row for row in file_ledger}
    for entry in encoding_ledger:
        path = f"problem_instances/{entry['problem_instance_path']}"
        entry["file_before_sha256"] = file_hashes[path]["before_sha256"]
        entry["file_after_sha256"] = file_hashes[path]["after_sha256"]

    return file_ledger, {
        "provenance_moves": provenance_plan,
        "encoding_repairs": encoding_ledger,
        "descriptor_backfills": descriptor_ledger,
        "threshold_annotations": threshold_plan,
        "planted_feature_backfills": planted_plan,
    }


def build_feature_catalog(mode: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    relative = "analysis/feature_schema/feature_column_metadata.csv"
    original = base_bytes(relative).decode()
    reader = csv.DictReader(io.StringIO(original))
    rows = list(reader)
    fieldnames = list(reader.fieldnames or [])
    by_column = {row["column"]: row for row in rows}
    changes = [
        row for row in csv_rows(SOURCE / "g56_forward_vocabulary_census.csv")
        if row["kind"] == "feature_catalog_cell"
    ]
    changed_rows: set[str] = set()
    for change in changes:
        column, field = change["locator"].split(":", 1)
        row = by_column[column]
        if row[field] != change["current_value"]:
            raise ValueError(f"feature catalog source drift: {change['locator']}")
        row[field] = change["proposed_value"]
        changed_rows.add(column)
    if len(changes) != EXPECTED["catalog_changed_cells"]:
        raise RuntimeError("feature catalog cell-count drift")
    if len(changed_rows) != EXPECTED["catalog_changed_rows"]:
        raise RuntimeError("feature catalog row-count drift")

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    payload = output.getvalue().encode()
    target = ROOT / relative
    if mode == "apply":
        target.write_bytes(payload)
    elif target.read_bytes() != payload:
        raise RuntimeError("feature catalog differs from generator")
    return changes, {
        "path": relative,
        "before_sha256": digest_bytes(original.encode()),
        "after_sha256": digest_bytes(payload),
    }


def transform_renamed(relative: str, payload: bytes) -> bytes:
    text = payload.decode()
    if relative.endswith("g31_legacy_lattice_task_mapping.md"):
        text = text.replace(
            "# G-31 legacy lattice task mapping",
            "# G-31 prototype lattice task mapping",
            1,
        )
    if relative.endswith("build_legacy_lattice_task_mapping.py"):
        text = text.replace("Certify legacy-to-current", "Certify prototype-to-current")
        text = text.replace(
            "g31_legacy_lattice_task_mapping",
            "g31_prototype_lattice_task_mapping",
        )
        text = text.replace(
            "# G-31 legacy lattice task mapping",
            "# G-31 prototype lattice task mapping",
        )
    return text.encode()


def build_forward_vocabulary(mode: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rename_ledger: list[dict[str, Any]] = []
    for old, new in ARTIFACT_RENAMES.items():
        payload = transform_renamed(old, base_bytes(old))
        old_target, new_target = ROOT / old, ROOT / new
        if mode == "apply":
            new_target.write_bytes(payload)
            old_target.unlink(missing_ok=True)
        else:
            if old_target.exists() or new_target.read_bytes() != payload:
                raise RuntimeError(f"prototype rename differs: {old} -> {new}")
        rename_ledger.append(
            {
                "old_path": old,
                "new_path": new,
                "before_sha256": digest_bytes(base_bytes(old)),
                "after_sha256": digest_bytes(payload),
            }
        )

    reference_ledger: list[dict[str, Any]] = []
    for relative, (old, new) in REFERENCE_UPDATES.items():
        original = base_bytes(relative)
        if original.count(old.encode()) != 1:
            raise ValueError(f"{relative}: expected one active mapping reference")
        payload = original.replace(old.encode(), new.encode())
        target = ROOT / relative
        if mode == "apply":
            target.write_bytes(payload)
        elif target.read_bytes() != payload:
            raise RuntimeError(f"mapping reference differs: {relative}")
        reference_ledger.append(
            {
                "path": relative,
                "old_value": old,
                "new_value": new,
                "before_sha256": digest_bytes(original),
                "after_sha256": digest_bytes(payload),
            }
        )

    for relative in BYTE_PINNED:
        if (ROOT / relative).read_bytes() != base_bytes(relative):
            raise RuntimeError(f"excluded byte-pinned artifact changed: {relative}")
    return rename_ledger, reference_ledger


def write_or_check(path: Path, payload: bytes, mode: str) -> None:
    if mode == "apply":
        path.write_bytes(payload)
    elif path.read_bytes() != payload:
        raise RuntimeError(f"generated evidence differs: {path.relative_to(ROOT)}")


def write_descriptor_csv(rows: list[dict[str, Any]], mode: str) -> None:
    output = io.StringIO(newline="")
    fields = list(rows[0])
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write_or_check(HERE / "g56_descriptor_ledger.csv", output.getvalue().encode(), mode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("apply", "check"), required=True)
    args = parser.parse_args()

    instance_files, sections = build_instances(args.mode)
    catalog_changes, catalog_file = build_feature_catalog(args.mode)
    renames, references = build_forward_vocabulary(args.mode)

    source_hashes = {
        path.name: digest_file(path)
        for path in sorted(SOURCE.iterdir())
        if path.is_file()
    }
    plan = {
        "schema_version": 1,
        "goal": "G-56",
        "status": "held_candidate_pending_pi_ack",
        "public_merge_authorized": False,
        "source_repository_commit": BASE_COMMIT,
        "source_census_sha256": source_hashes,
        "counts": {
            "problem_instances": len(instance_files),
            "tasks": EXPECTED["tasks"],
            "provenance_moves": len(sections["provenance_moves"]),
            "encoding_repairs": len(sections["encoding_repairs"]),
            "descriptor_backfills": len(sections["descriptor_backfills"]),
            "threshold_annotations": len(sections["threshold_annotations"]),
            "planted_feature_backfills": len(sections["planted_feature_backfills"]),
            "catalog_changed_cells": len(catalog_changes),
            "catalog_changed_rows": len({row["locator"].split(":", 1)[0] for row in catalog_changes}),
            "artifact_renames": len(renames),
            "active_reference_updates": len(references),
        },
        **sections,
        "feature_catalog_changes": catalog_changes,
        "artifact_renames": renames,
        "active_reference_updates": references,
        "explicit_exclusions": list(BYTE_PINNED),
    }
    ledger = {
        "schema_version": 1,
        "goal": "G-56",
        "status": "held_candidate_pending_pi_ack",
        "source_repository_commit": BASE_COMMIT,
        "instance_file_hashes": instance_files,
        "feature_catalog_file_hash": catalog_file,
        "encoding_byte_ledger": sections["encoding_repairs"],
        "artifact_rename_ledger": renames,
        "active_reference_update_ledger": references,
        "descriptor_object_count": len(sections["descriptor_backfills"]),
        "descriptor_object_compressed_bytes": (
            json.loads(COMMITTED_LEDGER.read_text(encoding="utf-8"))[
                "descriptor_object_compressed_bytes"
            ]
            if args.mode == "check"
            else sum(
                (PROJECT / row["local_object_path"]).stat().st_size
                for row in sections["descriptor_backfills"]
            )
        ),
        "byte_pinned_exclusions": [
            {
                "path": relative,
                "sha256": digest_bytes(base_bytes(relative)),
            }
            for relative in BYTE_PINNED
        ],
    }

    write_or_check(HERE / "g56_migration_plan.json", stable_json(plan), args.mode)
    write_or_check(HERE / "g56_migration_ledger.json", stable_json(ledger), args.mode)
    write_descriptor_csv(sections["descriptor_backfills"], args.mode)
    print(
        "PASS:"
        f" {len(instance_files)} instances,"
        f" {len(sections['provenance_moves'])} provenance moves,"
        f" {len(sections['descriptor_backfills'])} header backfills,"
        f" {len(sections['threshold_annotations'])} threshold annotations"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
