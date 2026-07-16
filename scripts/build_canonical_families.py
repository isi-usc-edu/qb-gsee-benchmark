#!/usr/bin/env python3
"""Build or verify the binding O32 canonical-family artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "analysis/feature_schema/canonical_families_v1.json"
CSV_PATH = ROOT / "analysis/feature_schema/canonical_families_v1.csv"
PROPOSAL_MAPPING_SHA256 = (
    "717b35d0ca885e5c7aef054d6b211d945ecb23be3715239620182cc2d0994bb1"
)
PROPOSAL_SUMMARY_SHA256 = (
    "ca6ff68096683540a889022fb52caf8401c390d94e5cb505a842fcf540914df3"
)
PROPOSAL_APPENDIX_SHA256 = (
    "c68d3d8bed5eb4fade2339c2a2a5187f0bd5ec10187d86e1c4a3802affcb3c95"
)
PROPOSAL_MEMO_SHA256 = (
    "eb87706169b6c10de521902223e9e608f730e90d84d9a5476ca75733b16fe06a"
)
EXPECTED_TASKS = 718
EXPECTED_INSTANCES = 218
EXPECTED_ARTIFACT_SHA256 = (
    "4bc9404feba3313cea64df734364a3ecbb45dbfda6f41bd337231181fef67942"
)
EXPECTED_FAMILIES = 40
METADATA_FIELDS = (
    "effective",
    "ruling_id",
    "proposal_mapping_sha256",
    "proposal_memo_sha256",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _csv_bytes(document: dict[str, Any]) -> bytes:
    task_fields = sorted({key for task in document["tasks"] for key in task})
    fields = list(METADATA_FIELDS) + task_fields
    handle = StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    provenance = document["proposal_provenance"]
    for task in document["tasks"]:
        row = {key: _cell(value) for key, value in task.items()}
        row.update(
            {
                "effective": "true",
                "ruling_id": document["ruling"]["id"],
                "proposal_mapping_sha256": provenance["mapping_sha256"],
                "proposal_memo_sha256": provenance["memo_sha256"],
            }
        )
        writer.writerow(row)
    return handle.getvalue().encode()


def _write_exact(path: Path, content: bytes) -> None:
    if path.exists() and path.read_bytes() != content:
        raise ValueError(f"refusing to overwrite non-identical artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _corpus_index(root: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    paths = sorted((root / "problem_instances").rglob("*.json"))
    if len(paths) != EXPECTED_INSTANCES:
        raise ValueError(f"expected {EXPECTED_INSTANCES} instances, found {len(paths)}")
    for path in paths:
        document = json.loads(path.read_text())
        relative = path.relative_to(root / "problem_instances").as_posix()
        for task in document.get("tasks", []):
            task_uuid = task["task_uuid"]
            if task_uuid in result:
                raise ValueError(f"duplicate corpus task UUID: {task_uuid}")
            result[task_uuid] = {
                "problem_instance_path": relative,
                "problem_instance_short_name": document["short_name"],
                "problem_instance_uuid": document["problem_instance_uuid"],
            }
    return result


def build_document(proposal_path: Path) -> dict[str, Any]:
    if _sha256(proposal_path) != PROPOSAL_MAPPING_SHA256:
        raise ValueError("approved proposal mapping hash mismatch")
    proposal = json.loads(proposal_path.read_text())
    tasks = proposal.get("tasks", [])
    if (
        len(tasks) != EXPECTED_TASKS
        or len({task["task_uuid"] for task in tasks}) != EXPECTED_TASKS
    ):
        raise ValueError("approved proposal does not contain 718 unique tasks")
    if (
        len({task["canonical_family_recommended"] for task in tasks})
        != EXPECTED_FAMILIES
    ):
        raise ValueError("approved proposal does not contain 40 recommended families")
    return {
        "archive_class_counts": dict(
            sorted(Counter(task["archive_class"] for task in tasks).items())
        ),
        "artifact_id": "canonical_families_v1",
        "effective": True,
        "family_counts": dict(
            sorted(
                Counter(task["canonical_family_recommended"] for task in tasks).items()
            )
        ),
        "ml4b_reconciliation": proposal["ml4b_reconciliation"],
        "policy": proposal["policy"],
        "proposal_provenance": {
            "appendix_sha256": PROPOSAL_APPENDIX_SHA256,
            "mapping_sha256": PROPOSAL_MAPPING_SHA256,
            "memo_sha256": PROPOSAL_MEMO_SHA256,
            "summary_sha256": PROPOSAL_SUMMARY_SHA256,
        },
        "recommended_family_count": EXPECTED_FAMILIES,
        "recommended_level": proposal["recommended_level"],
        "ruling": {
            "date": "2026-07-16",
            "id": "O32",
            "record": "MATT RULING 2026-07-16 - O32 APPROVED",
            "statement": "I accept family ruling",
        },
        "schema_version": 1,
        "source_instance_count": proposal["source_instance_count"],
        "source_repository_commit": proposal["source_repository_commit"],
        "source_task_count": proposal["source_task_count"],
        "status": "binding_matt_o32_approved",
        "tasks": tasks,
    }


def verify(root: Path = ROOT) -> dict[str, object]:
    json_path = root / JSON_PATH.relative_to(ROOT)
    document = json.loads(json_path.read_text())
    if _sha256(json_path) != EXPECTED_ARTIFACT_SHA256:
        raise ValueError("canonical-family artifact checksum mismatch")
    if (
        document.get("artifact_id") != "canonical_families_v1"
        or document.get("schema_version") != 1
        or document.get("effective") is not True
        or document.get("status") != "binding_matt_o32_approved"
        or document.get("ruling", {}).get("id") != "O32"
    ):
        raise ValueError("canonical-family binding metadata is invalid")
    provenance = document.get("proposal_provenance", {})
    expected_provenance = {
        "appendix_sha256": PROPOSAL_APPENDIX_SHA256,
        "mapping_sha256": PROPOSAL_MAPPING_SHA256,
        "memo_sha256": PROPOSAL_MEMO_SHA256,
        "summary_sha256": PROPOSAL_SUMMARY_SHA256,
    }
    if provenance != expected_provenance:
        raise ValueError("canonical-family proposal provenance mismatch")
    tasks = document.get("tasks", [])
    by_uuid = {task["task_uuid"]: task for task in tasks}
    if len(tasks) != EXPECTED_TASKS or len(by_uuid) != EXPECTED_TASKS:
        raise ValueError("canonical-family task count or uniqueness mismatch")
    if len(document.get("family_counts", {})) != EXPECTED_FAMILIES:
        raise ValueError("canonical-family family count mismatch")
    recount = dict(
        sorted(Counter(task["canonical_family_recommended"] for task in tasks).items())
    )
    if recount != document["family_counts"]:
        raise ValueError("canonical-family counts do not recount")
    corpus = _corpus_index(root)
    if set(corpus) != set(by_uuid):
        raise ValueError("canonical-family and corpus task UUID sets differ")
    for task_uuid, expected in corpus.items():
        observed = by_uuid[task_uuid]
        for key, value in expected.items():
            if observed.get(key) != value:
                raise ValueError(f"canonical-family corpus mismatch: {task_uuid} {key}")
    expected_csv = _csv_bytes(document)
    csv_path = root / CSV_PATH.relative_to(ROOT)
    if csv_path.read_bytes() != expected_csv:
        raise ValueError("canonical-family CSV is not the exact JSON-derived view")
    return {
        "artifact_id": document["artifact_id"],
        "csv_sha256": _sha256(csv_path),
        "effective": True,
        "family_count": len(recount),
        "json_sha256": _sha256(root / JSON_PATH.relative_to(ROOT)),
        "status": "passed",
        "task_count": len(tasks),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-proposal", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.approved_proposal is not None:
        document = build_document(args.approved_proposal)
        _write_exact(JSON_PATH, _json_bytes(document))
        _write_exact(CSV_PATH, _csv_bytes(document))
    elif not args.check:
        parser.error("provide --approved-proposal for first build or --check")
    result = verify()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
