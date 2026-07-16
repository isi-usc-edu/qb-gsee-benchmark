# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Fail-closed access to the binding O32 canonical-family artifact."""

from __future__ import annotations
import hashlib

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CANONICAL_FAMILIES_PATH = (
    Path(__file__).resolve().parents[2]
    / "analysis"
    / "feature_schema"
    / "canonical_families_v1.json"
)
EXPECTED_TASK_COUNT = 718
EXPECTED_FAMILY_COUNT = 40
EXPECTED_PROPOSAL_MAPPING_SHA256 = (
    "717b35d0ca885e5c7aef054d6b211d945ecb23be3715239620182cc2d0994bb1"
)
EXPECTED_PROPOSAL_MEMO_SHA256 = (
    "eb87706169b6c10de521902223e9e608f730e90d84d9a5476ca75733b16fe06a"
)

EXPECTED_ARTIFACT_SHA256 = (
    "4bc9404feba3313cea64df734364a3ecbb45dbfda6f41bd337231181fef67942"
)


def _validate_document(document: dict[str, Any]) -> None:
    if (
        document.get("artifact_id") != "canonical_families_v1"
        or document.get("schema_version") != 1
        or document.get("effective") is not True
        or document.get("status") != "binding_matt_o32_approved"
        or document.get("ruling", {}).get("id") != "O32"
    ):
        raise ValueError("canonical-family artifact is not an effective O32 binding")
    provenance = document.get("proposal_provenance", {})
    if (
        provenance.get("mapping_sha256") != EXPECTED_PROPOSAL_MAPPING_SHA256
        or provenance.get("memo_sha256") != EXPECTED_PROPOSAL_MEMO_SHA256
    ):
        raise ValueError(
            "canonical-family artifact has unrecognized proposal provenance"
        )
    tasks = document.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != EXPECTED_TASK_COUNT:
        raise ValueError("canonical-family artifact must contain exactly 718 tasks")
    task_uuids = [task.get("task_uuid") for task in tasks]
    if len(set(task_uuids)) != EXPECTED_TASK_COUNT or None in task_uuids:
        raise ValueError("canonical-family task UUIDs are missing or duplicated")
    families = {task.get("canonical_family_recommended") for task in tasks}
    if None in families or len(families) != EXPECTED_FAMILY_COUNT:
        raise ValueError("canonical-family artifact must contain exactly 40 families")
    recounted: dict[str, int] = {}
    for task in tasks:
        family = str(task["canonical_family_recommended"])
        recounted[family] = recounted.get(family, 0) + 1
    if dict(sorted(recounted.items())) != document.get("family_counts"):
        raise ValueError("canonical-family embedded counts do not recount")


def load_canonical_families(
    path: str | Path = CANONICAL_FAMILIES_PATH,
) -> dict[str, Any]:
    """Load and validate a canonical-family document."""
    artifact_path = Path(path)
    content = artifact_path.read_bytes()
    document = json.loads(content)
    _validate_document(document)
    if hashlib.sha256(content).hexdigest() != EXPECTED_ARTIFACT_SHA256:
        raise ValueError("canonical-family artifact checksum mismatch")
    return document


@lru_cache(maxsize=1)
def _indices() -> tuple[dict[str, dict[str, Any]], dict[str, tuple[str, ...]]]:
    document = load_canonical_families()
    by_uuid = {str(task["task_uuid"]): task for task in document["tasks"]}
    by_short_name: dict[str, set[str]] = {}
    for task in document["tasks"]:
        short_name = str(task["problem_instance_short_name"])
        by_short_name.setdefault(short_name, set()).add(
            str(task["canonical_family_recommended"])
        )
    frozen_short_names = {
        key: tuple(sorted(value)) for key, value in by_short_name.items()
    }
    return by_uuid, frozen_short_names


def canonical_family_record(task_uuid: str) -> dict[str, Any]:
    """Return a copy of the binding task-level canonical-family record."""
    by_uuid, _ = _indices()
    try:
        return dict(by_uuid[str(task_uuid)])
    except KeyError as exc:
        raise KeyError(
            f"task UUID is absent from canonical_families_v1: {task_uuid}"
        ) from exc


def canonical_problem_family(
    problem_instance_short_name: str, *, task_uuid: str | None = None
) -> str:
    """Return the O32 generation-protocol family for a corpus task."""
    short_name = str(problem_instance_short_name)
    by_uuid, by_short_name = _indices()
    if task_uuid is not None:
        try:
            record = by_uuid[str(task_uuid)]
        except KeyError as exc:
            raise KeyError(
                f"task UUID is absent from canonical_families_v1: {task_uuid}"
            ) from exc
        if record["problem_instance_short_name"] != short_name:
            raise ValueError(
                "canonical-family task/short-name mismatch: "
                f"{task_uuid} is {record['problem_instance_short_name']!r}, not {short_name!r}"
            )
        return str(record["canonical_family_recommended"])
    try:
        families = by_short_name[short_name]
    except KeyError as exc:
        raise KeyError(
            f"short name is absent from canonical_families_v1: {short_name}"
        ) from exc
    if len(families) != 1:
        raise ValueError(
            f"short name {short_name!r} spans task-level families {families}; task_uuid is required"
        )
    return families[0]
