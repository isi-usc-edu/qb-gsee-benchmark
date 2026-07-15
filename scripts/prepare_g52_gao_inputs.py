#!/usr/bin/env python3
"""Prepare the private table, seed evidence, and offline cache for G52."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from io import StringIO
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.features.corpus_runner import (
    cache_path,
    load_corpus_fcidumps,
    verify_declared_checksum,
)

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_exact(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f"refusing to replace nonmatching G52 input {path}")
    path.write_bytes(data)


def _table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"missing feature-table header: {path}")
        return list(reader.fieldnames), list(reader)


def _table_bytes(fields: list[str], rows: list[dict[str, str]]) -> bytes:
    handle = StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode("utf-8")


def _gao_metadata(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for instance_path in sorted(path.rglob("*.json")):
        document = json.loads(instance_path.read_text())
        for task in document.get("tasks", []):
            fcidumps = [
                item
                for item in task.get("supporting_files", [])
                if item.get("is_fcidump_file")
            ]
            if len(fcidumps) != 1:
                raise ValueError(f"Gao task {task.get('task_uuid')} lacks one FCIDUMP")
            features = task.get("features", {})
            result[task["task_uuid"]] = {
                "problem_instance_uuid": document["problem_instance_uuid"],
                "problem_instance_short_name": document["short_name"],
                "n_elec": features["num_electrons"],
                "n_orbs": features["num_orbitals"],
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--problem-instances", type=Path, default=ROOT / "problem_instances"
    )
    parser.add_argument("--gao-instances", type=Path, required=True)
    parser.add_argument(
        "--public-feature-table",
        type=Path,
        default=ROOT / "scripts" / "Hamiltonian_features.csv",
    )
    parser.add_argument("--g40-report", type=Path, required=True)
    parser.add_argument("--g40-state-dir", type=Path, required=True)
    parser.add_argument("--feature-contract", type=Path, required=True)
    parser.add_argument("--gao-fcidump-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-public-rows", type=int, default=591)
    parser.add_argument("--expected-gao-rows", type=int, default=127)
    parser.add_argument("--expected-total-rows", type=int, default=718)
    parser.add_argument("--expected-columns", type=int, default=580)
    args = parser.parse_args()

    records = load_corpus_fcidumps(args.problem_instances)
    records_by_uuid = {record.task_uuid: record for record in records}
    gao_records = load_corpus_fcidumps(args.gao_instances)
    gao_by_uuid = {record.task_uuid: record for record in gao_records}
    fields, public_rows = _table(args.public_feature_table)
    public_by_uuid = {row["task_uuid"]: row for row in public_rows}
    if len(public_by_uuid) != len(public_rows):
        raise ValueError("duplicate task UUID in public feature table")
    expected = {
        "public rows": (len(public_rows), args.expected_public_rows),
        "Gao rows": (len(gao_records), args.expected_gao_rows),
        "corpus rows": (len(records), args.expected_total_rows),
        "columns": (len(fields), args.expected_columns),
    }
    mismatches = {
        name: {"observed": observed, "expected": wanted}
        for name, (observed, wanted) in expected.items()
        if observed != wanted
    }
    if mismatches:
        raise ValueError(f"unexpected G52 intake dimensions: {mismatches}")
    if set(public_by_uuid) != set(records_by_uuid) - set(gao_by_uuid):
        raise ValueError("public feature rows plus Gao tasks do not partition corpus")

    report = json.loads(args.g40_report.read_text())
    contract_sha256 = _sha256(args.feature_contract)
    if (
        report.get("status") != "passed"
        or report.get("successful_states") != args.expected_public_rows
        or report.get("rows_after") != args.expected_public_rows
        or report.get("columns_after") != args.expected_columns
        or report.get("feature_contract_sha256") != contract_sha256
        or report.get("output_feature_table_sha256")
        != _sha256(args.public_feature_table)
    ):
        raise ValueError("accepted G40 report does not pin the public feature table")
    state_ledger = report.get("state_ledger", [])
    ledger_by_name = {item["path"]: item["sha256"] for item in state_ledger}
    state_paths = sorted(args.g40_state_dir.glob("*.mfproto.json"))
    if len(ledger_by_name) != args.expected_public_rows or {
        path.name for path in state_paths
    } != set(ledger_by_name):
        raise ValueError("accepted G40 state directory differs from its ledger")
    for path in state_paths:
        if _sha256(path) != ledger_by_name[path.name]:
            raise ValueError(f"accepted G40 state checksum mismatch: {path.name}")

    metadata = _gao_metadata(args.gao_instances)
    rows = list(public_rows)
    required_metadata_fields = {
        "problem_instance_uuid",
        "problem_instance_short_name",
        "task_uuid",
        "instance_data_object_uuid",
        "instance_data_object_file_name",
        "instance_data_object_url",
        "n_elec",
        "n_orbs",
    }
    if not required_metadata_fields.issubset(fields):
        raise ValueError("public feature table lacks required provenance columns")
    for task_uuid in sorted(gao_by_uuid):
        record = gao_by_uuid[task_uuid]
        row = {field: "" for field in fields}
        row.update(metadata[task_uuid])
        row.update(
            {
                "task_uuid": task_uuid,
                "instance_data_object_uuid": record.instance_data_object_uuid,
                "instance_data_object_file_name": record.file_name,
                "instance_data_object_url": record.url,
            }
        )
        rows.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    table_path = args.output_dir / "Hamiltonian_features.g52_candidate.csv"
    _write_exact(table_path, _table_bytes(fields, rows))
    seed_report = {
        "status": "passed",
        "extractor_version": report["extractor_version"],
        "code_revision": report["extractor_code_revision"],
        "configuration": report["configuration"],
        "output_contract": {"sha256": contract_sha256},
        "state_ledger": state_ledger,
        "accepted_g40_report": {
            "path": str(args.g40_report),
            "sha256": _sha256(args.g40_report),
        },
    }
    seed_path = args.output_dir / "g52_seed_report.json"
    _write_exact(
        seed_path,
        (json.dumps(seed_report, indent=2, sort_keys=True) + "\n").encode(),
    )

    cache_dir = args.output_dir / "cache"
    cache_dir.mkdir(exist_ok=True)
    cache_ledger = []
    for record in gao_records:
        source = (args.gao_fcidump_dir / record.file_name).resolve()
        if not source.is_file():
            raise ValueError(f"missing local Gao FCIDUMP: {source}")
        verify_declared_checksum(source, record)
        destination = cache_path(cache_dir, record)
        if destination.exists() or destination.is_symlink():
            verify_declared_checksum(destination, record)
        else:
            temporary = destination.with_suffix(destination.suffix + ".partial")
            temporary.symlink_to(source)
            os.replace(temporary, destination)
        cache_ledger.append(
            {
                "path": destination.name,
                "source": str(source),
                "declared_checksum": record.checksum,
                "declared_checksum_type": record.checksum_type,
            }
        )

    input_report = {
        "report_version": "g52_gao_inputs_v1",
        "status": "passed",
        "public_rows": len(public_rows),
        "gao_rows": len(gao_records),
        "candidate_rows": len(rows),
        "columns": len(fields),
        "public_feature_table_sha256": _sha256(args.public_feature_table),
        "candidate_feature_table_sha256": _sha256(table_path),
        "accepted_g40_report_sha256": _sha256(args.g40_report),
        "feature_contract_sha256": contract_sha256,
        "seed_report_sha256": _sha256(seed_path),
        "cache_entries": len(cache_ledger),
        "cache_ledger": cache_ledger,
    }
    report_path = args.output_dir / "g52_input_report.json"
    _write_exact(
        report_path,
        (json.dumps(input_report, indent=2, sort_keys=True) + "\n").encode(),
    )
    print(
        json.dumps(
            {
                key: input_report[key]
                for key in (
                    "status",
                    "public_rows",
                    "gao_rows",
                    "candidate_rows",
                    "cache_entries",
                )
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
