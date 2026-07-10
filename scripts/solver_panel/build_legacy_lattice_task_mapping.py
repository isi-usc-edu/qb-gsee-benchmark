#!/usr/bin/env python3
"""Certify legacy-to-current Hubbard task UUID lineage for G-31."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any


FAMILIES = {
    "hubbard_chain": {
        "legacy_problem_uuid": "c2009f9f-4738-4919-9295-5f9231ca5199",
        "expected_tasks": 16,
    },
    "hubbard_square": {
        "legacy_problem_uuid": "614c4444-a31a-4348-b24d-01040208651c",
        "expected_tasks": 30,
    },
}
FIELDS = [
    "family",
    "legacy_problem_instance_uuid",
    "current_problem_instance_uuid",
    "legacy_task_uuid",
    "current_task_uuid",
    "legacy_data_object_uuid",
    "current_data_object_uuid",
    "recovered_raw_path",
    "recovered_raw_sha1",
    "reproducible_gzip_sha1",
    "legacy_declared_sha1",
    "legacy_declared_checksum_matches_recovered",
    "solution_record_count",
    "solution_file_count",
    "mapping_status",
    "evidence",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def sha1_bytes(payload: bytes) -> str:
    return hashlib.sha1(payload).hexdigest()


def reproducible_gzip(payload: bytes) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as stream:
        stream.write(payload)
    return output.getvalue()


def deterministic_uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"qb-gsee-benchmark:{name}"))


def one_fcidump(task: dict[str, Any]) -> dict[str, Any]:
    matches = [
        item for item in task["supporting_files"] if item.get("is_fcidump_file")
    ]
    if len(matches) != 1:
        raise ValueError(
            f"task {task['task_uuid']} has {len(matches)} FCIDUMP support objects"
        )
    return matches[0]


def current_problem(repo_root: Path, family: str) -> tuple[Path, dict[str, Any]]:
    matches = []
    for path in (repo_root / "problem_instances").glob("**/*.json"):
        payload = read_json(path)
        if payload.get("short_name") == family:
            matches.append((path, payload))
    if len(matches) != 1:
        raise ValueError(f"expected one current {family} instance, got {len(matches)}")
    return matches[0]


def legacy_solution_index(
    repo_root: Path, legacy_problem_uuids: set[str]
) -> tuple[Counter[str], dict[str, set[str]]]:
    records: Counter[str] = Counter()
    paths: dict[str, set[str]] = {}
    for path in sorted((repo_root / "solution_files").glob("**/*.json")):
        try:
            solution = read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if str(solution.get("problem_instance_uuid")) not in legacy_problem_uuids:
            continue
        relative = str(path.relative_to(repo_root))
        for result in solution.get("solution_data", []):
            task_uuid = str(result.get("task_uuid"))
            records[task_uuid] += 1
            paths.setdefault(task_uuid, set()).add(relative)
    return records, paths


def build_mapping(repo_root: Path) -> dict[str, Any]:
    legacy_uuids = {
        str(config["legacy_problem_uuid"]) for config in FAMILIES.values()
    }
    solution_records, solution_paths = legacy_solution_index(repo_root, legacy_uuids)
    rows = []
    legacy_tasks_seen: set[str] = set()
    current_tasks_seen: set[str] = set()

    for family, config in FAMILIES.items():
        legacy_path = (
            repo_root
            / "scripts"
            / "hubbard_testing"
            / f"problem_instance.{family}.{config['legacy_problem_uuid']}.json"
        )
        legacy = read_json(legacy_path)
        current_path, current = current_problem(repo_root, family)
        current_by_legacy = {
            str(task.get("features", {}).get("legacy_task_uuid")): task
            for task in current["tasks"]
        }
        if len(current_by_legacy) != len(current["tasks"]):
            raise ValueError(f"{family} current legacy-task keys are not unique")
        if legacy["problem_instance_uuid"] != config["legacy_problem_uuid"]:
            raise ValueError(f"{family} legacy problem UUID mismatch")
        if current.get("legacy_problem_instance_uuid") != config["legacy_problem_uuid"]:
            raise ValueError(f"{family} current problem lineage mismatch")
        if len(legacy["tasks"]) != config["expected_tasks"]:
            raise ValueError(f"{family} legacy task count mismatch")

        for legacy_task in legacy["tasks"]:
            legacy_task_uuid = str(legacy_task["task_uuid"])
            current_task = current_by_legacy.get(legacy_task_uuid)
            if current_task is None:
                raise ValueError(f"missing current task for {legacy_task_uuid}")
            legacy_support = one_fcidump(legacy_task)
            current_support = one_fcidump(current_task)
            legacy_object_uuid = str(legacy_support["instance_data_object_uuid"])
            raw_matches = sorted(
                (
                    repo_root
                    / "scripts"
                    / "hubbard_testing"
                    / "FCIDUMP_hubbard_hartree_fock_orbitals"
                ).glob(f"*{legacy_object_uuid}*")
            )
            if len(raw_matches) != 1:
                raise ValueError(
                    f"{legacy_task_uuid} has {len(raw_matches)} recovered FCIDUMPs"
                )
            raw_path = raw_matches[0]
            raw = raw_path.read_bytes()
            raw_sha1 = sha1_bytes(raw)
            gzip_sha1 = sha1_bytes(reproducible_gzip(raw))
            expected_task_uuid = deterministic_uuid(
                f"hubbard-reinstatement/task/{legacy_task_uuid}"
            )
            expected_data_uuid = deterministic_uuid(
                f"hubbard-reinstatement/fcidump/{legacy_object_uuid}/{gzip_sha1}"
            )
            identity_checks = {
                "deterministic_task_uuid": current_task["task_uuid"]
                == expected_task_uuid,
                "legacy_data_uuid_retained": current_support.get(
                    "legacy_instance_data_object_uuid"
                )
                == legacy_object_uuid,
                "deterministic_data_uuid": current_support[
                    "instance_data_object_uuid"
                ]
                == expected_data_uuid,
                "reproducible_gzip_checksum": current_support[
                    "instance_data_checksum"
                ]
                == gzip_sha1,
                "legacy_declared_checksum_retained": current_support.get(
                    "legacy_instance_data_checksum"
                )
                == legacy_support["instance_data_checksum"],
                "solution_records_present": solution_records[legacy_task_uuid] > 0,
            }
            if not all(identity_checks.values()):
                failed = [
                    name for name, passed in identity_checks.items() if not passed
                ]
                raise ValueError(f"{legacy_task_uuid} failed: {failed}")
            legacy_sha1 = str(legacy_support["instance_data_checksum"])
            rows.append(
                {
                    "family": family,
                    "legacy_problem_instance_uuid": legacy[
                        "problem_instance_uuid"
                    ],
                    "current_problem_instance_uuid": current[
                        "problem_instance_uuid"
                    ],
                    "legacy_task_uuid": legacy_task_uuid,
                    "current_task_uuid": current_task["task_uuid"],
                    "legacy_data_object_uuid": legacy_object_uuid,
                    "current_data_object_uuid": current_support[
                        "instance_data_object_uuid"
                    ],
                    "recovered_raw_path": str(raw_path.relative_to(repo_root)),
                    "recovered_raw_sha1": raw_sha1,
                    "reproducible_gzip_sha1": gzip_sha1,
                    "legacy_declared_sha1": legacy_sha1,
                    "legacy_declared_checksum_matches_recovered": legacy_sha1
                    in {raw_sha1, gzip_sha1},
                    "solution_record_count": solution_records[legacy_task_uuid],
                    "solution_file_count": len(solution_paths[legacy_task_uuid]),
                    "mapping_status": (
                        "certified_identity_lineage_and_recovered_payload"
                    ),
                    "evidence": (
                        "retained legacy problem/task/data UUID; unique recovered "
                        "FCIDUMP selected by data UUID; deterministic UUIDv5 task and "
                        "data-object derivation; current checksum equals reproducible "
                        "gzip of recovered raw payload"
                    ),
                }
            )
            legacy_tasks_seen.add(legacy_task_uuid)
            current_tasks_seen.add(str(current_task["task_uuid"]))

    unknown_solution_tasks = sorted(set(solution_records) - legacy_tasks_seen)
    rows.sort(key=lambda row: (row["family"], row["legacy_task_uuid"]))
    return {
        "status": "pass" if not unknown_solution_tasks else "fail",
        "mapping_policy": (
            "Identity/lineage plus recovered-payload checksum certification. "
            "The retained legacy declared checksums do not match recovered raw or "
            "reproducible gzip bytes and are not used as payload certificates."
        ),
        "rows": rows,
        "summary": {
            "mapped_legacy_tasks": len(legacy_tasks_seen),
            "unique_current_tasks": len(current_tasks_seen),
            "legacy_solution_records": sum(solution_records.values()),
            "legacy_solution_files": len(
                set().union(*solution_paths.values()) if solution_paths else set()
            ),
            "legacy_checksum_matches": sum(
                bool(row["legacy_declared_checksum_matches_recovered"])
                for row in rows
            ),
            "unknown_legacy_solution_tasks": unknown_solution_tasks,
            "family_task_counts": dict(
                sorted(Counter(row["family"] for row in rows).items())
            ),
        },
    }


def write_outputs(repo_root: Path, mapping: dict[str, Any]) -> None:
    output = repo_root / "analysis" / "solver_panel"
    output.mkdir(parents=True, exist_ok=True)
    with (output / "g31_legacy_lattice_task_mapping.csv").open(
        "w", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(mapping["rows"])
    (output / "g31_legacy_lattice_task_mapping.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n"
    )
    summary = mapping["summary"]
    lines = [
        "# G-31 legacy lattice task mapping",
        "",
        f"Status: **{mapping['status']}**.",
        "",
        "The mapping certifies identity lineage and the recovered local payload. "
        "It does not claim that the recovered payload matches the stale checksum "
        "declared by the old problem JSON.",
        "",
        f"- Mapped legacy tasks: {summary['mapped_legacy_tasks']}",
        f"- Unique current tasks: {summary['unique_current_tasks']}",
        f"- Joinable legacy solution records: {summary['legacy_solution_records']}",
        f"- Legacy solution files: {summary['legacy_solution_files']}",
        f"- Legacy declared checksum matches: {summary['legacy_checksum_matches']}",
        "- Unknown legacy solution tasks: "
        f"{len(summary['unknown_legacy_solution_tasks'])}",
        "",
        "Certification chain per row: retained legacy problem/task/data-object "
        "UUIDs; a unique recovered FCIDUMP filename containing the legacy data "
        "UUID; deterministic UUIDv5 derivation of the current task and data "
        "object; and the current SHA-1 matching a deterministic gzip of the "
        "recovered raw FCIDUMP.",
        "",
        "The adjacent CSV is the metrics-exporter join table. Legacy solution "
        "files remain unchanged.",
        "",
    ]
    (output / "g31_legacy_lattice_task_mapping.md").write_text("\n".join(lines))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    mapping = build_mapping(repo_root)
    write_outputs(repo_root, mapping)
    print(json.dumps(mapping["summary"], indent=2, sort_keys=True))
    return 0 if mapping["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
