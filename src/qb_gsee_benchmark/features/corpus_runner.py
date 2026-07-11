# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Manifest-driven execution support for G40 feature extraction."""

from __future__ import annotations

import hashlib
import json
import os
import resource
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from qb_gsee_benchmark.features.universal_t0_features import (
    UNIVERSAL_T0_LINEAR_VERSION,
    compute_universal_t0_linear_features,
)


@dataclass(frozen=True)
class CorpusFcidump:
    problem_instance_short_name: str
    task_uuid: str
    instance_data_object_uuid: str
    url: str
    checksum: str
    checksum_type: str
    file_name: str
    norb_metadata: int | None
    ms2_metadata: int | None

    def signature(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_corpus_fcidumps(
    problem_instances_dir: str | Path,
) -> list[CorpusFcidump]:
    """Build the current task manifest; no corpus count is hardcoded."""
    root = Path(problem_instances_dir)
    records: list[CorpusFcidump] = []
    for path in sorted(root.rglob("*.json")):
        document = json.loads(path.read_text())
        for task in document.get("tasks", []):
            fcidumps = [
                item
                for item in task.get("supporting_files", [])
                if item.get("is_fcidump_file")
            ]
            if len(fcidumps) != 1:
                raise ValueError(
                    f"{task.get('task_uuid')} has {len(fcidumps)} FCIDUMPs"
                )
            item = fcidumps[0]
            features = task.get("features", {})
            norb = features.get(
                "num_orbitals",
                features.get("n_orbitals", features.get("n_levels")),
            )
            ms2 = features.get("ms2", features.get("spin"))
            url_name = Path(urlparse(item["instance_data_object_url"]).path).name
            records.append(
                CorpusFcidump(
                    problem_instance_short_name=document["short_name"],
                    task_uuid=task["task_uuid"],
                    instance_data_object_uuid=item["instance_data_object_uuid"],
                    url=item["instance_data_object_url"],
                    checksum=item.get("instance_data_checksum", ""),
                    checksum_type=item.get("instance_data_checksum_type", ""),
                    file_name=item.get("instance_data_object_file_name", url_name),
                    norb_metadata=None if norb is None else int(norb),
                    ms2_metadata=None if ms2 is None else int(ms2),
                )
            )
    records.sort(key=lambda record: record.task_uuid)
    task_ids = [record.task_uuid for record in records]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("Duplicate task UUID in corpus FCIDUMP manifest")
    return records


def write_corpus_manifest_jsonl(
    records: list[CorpusFcidump], path: str | Path
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(asdict(record), sort_keys=True) + "\n" for record in records
    )
    path.write_text(text)


def _hash_algorithm(checksum_type: str) -> str:
    normalized = checksum_type.lower().replace("-", "").replace("_", "")
    aliases = {
        "sha1": "sha1",
        "sha1sum": "sha1",
        "sha256": "sha256",
        "sha256sum": "sha256",
        "md5": "md5",
        "md5sum": "md5",
    }
    if normalized not in aliases:
        raise ValueError(f"Unsupported checksum type: {checksum_type!r}")
    return aliases[normalized]


def file_checksum(path: str | Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_declared_checksum(path: str | Path, record: CorpusFcidump) -> str:
    if not record.checksum:
        raise ValueError(f"{record.task_uuid} has no declared FCIDUMP checksum")
    algorithm = _hash_algorithm(record.checksum_type)
    actual = file_checksum(path, algorithm)
    if actual.lower() != record.checksum.lower():
        raise ValueError(
            f"Checksum mismatch for {record.task_uuid}: "
            f"declared {record.checksum}, actual {actual}"
        )
    return actual


def cache_path(cache_dir: str | Path, record: CorpusFcidump) -> Path:
    suffixes = "".join(Path(record.file_name).suffixes)
    suffix = suffixes or ".fcidump"
    return Path(cache_dir) / f"{record.instance_data_object_uuid}{suffix}"


def materialize_fcidump(
    record: CorpusFcidump,
    cache_dir: str | Path,
    *,
    offline: bool = False,
    timeout_seconds: int = 300,
) -> Path:
    destination = cache_path(cache_dir, record)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        verify_declared_checksum(destination, record)
        return destination
    if offline:
        raise FileNotFoundError(destination)

    temporary = destination.with_suffix(destination.suffix + ".partial")
    with requests.get(
        record.url,
        stream=True,
        timeout=timeout_seconds,
    ) as response:
        response.raise_for_status()
        with temporary.open("wb") as handle:
            for block in response.iter_content(chunk_size=1024 * 1024):
                if block:
                    handle.write(block)
    try:
        verify_declared_checksum(temporary, record)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def run_linear_task(
    record: CorpusFcidump,
    cache_dir: str | Path,
    state_dir: str | Path,
    *,
    offline: bool = False,
) -> dict[str, Any]:
    """Run or resume one checksum-bound P1-A task."""
    state_path = Path(state_dir) / f"{record.task_uuid}.linear.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    signature = record.signature()
    if state_path.exists():
        previous = json.loads(state_path.read_text())
        if (
            previous.get("status") == "success"
            and previous.get("manifest_signature") == signature
            and previous.get("extractor_version") == UNIVERSAL_T0_LINEAR_VERSION
        ):
            return previous

    started = time.monotonic()
    try:
        source = materialize_fcidump(record, cache_dir, offline=offline)
        features = compute_universal_t0_linear_features(
            source, ms2_override=record.ms2_metadata
        )
        source_sha256 = file_checksum(source, "sha256")
        status = "success"
        error_type = None
        error_message = None
    except Exception as exc:
        features = None
        source_sha256 = None
        status = "failed"
        error_type = type(exc).__name__
        error_message = str(exc)
    payload = {
        "status": status,
        "problem_instance_short_name": record.problem_instance_short_name,
        "task_uuid": record.task_uuid,
        "instance_data_object_uuid": record.instance_data_object_uuid,
        "source_url": record.url,
        "declared_checksum": record.checksum,
        "declared_checksum_type": record.checksum_type,
        "source_sha256": source_sha256,
        "manifest_signature": signature,
        "manifest_ms2_metadata": record.ms2_metadata,
        "extractor_version": UNIVERSAL_T0_LINEAR_VERSION,
        "walltime_seconds": time.monotonic() - started,
        "process_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "features": features,
        "error_type": error_type,
        "error_message": error_message,
    }
    _atomic_write_json(state_path, payload)
    return payload
