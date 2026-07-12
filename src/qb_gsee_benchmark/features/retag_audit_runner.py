# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Resume-safe corpus runner for the G40 retag audit flags."""

from __future__ import annotations

import json
import os
import resource
import time
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.features.corpus_runner import (
    CorpusFcidump,
    file_checksum,
    materialize_fcidump,
)
from qb_gsee_benchmark.features.retag_audit_features import (
    RETAG_AUDIT_VERSION,
    compute_retag_audit_features,
)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def run_retag_audit_task(
    record: CorpusFcidump,
    cache_dir: str | Path,
    state_dir: str | Path,
    *,
    offline: bool = False,
) -> dict[str, Any]:
    state_path = Path(state_dir) / f"{record.task_uuid}.retag-audit.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    signature = record.signature()
    if state_path.exists():
        previous = json.loads(state_path.read_text())
        if (
            previous.get("status") == "success"
            and previous.get("manifest_signature") == signature
            and previous.get("extractor_version") == RETAG_AUDIT_VERSION
        ):
            return previous

    started = time.monotonic()
    try:
        source = materialize_fcidump(record, cache_dir, offline=offline)
        features = compute_retag_audit_features(
            source, ms2_override=record.ms2_metadata
        )
        source_sha256 = file_checksum(source, "sha256")
        status, error_type, error_message = "success", None, None
    except Exception as exc:
        features, source_sha256 = None, None
        status, error_type, error_message = "failed", type(exc).__name__, str(exc)
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
        "extractor_version": RETAG_AUDIT_VERSION,
        "walltime_seconds": time.monotonic() - started,
        "process_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "features": features,
        "error_type": error_type,
        "error_message": error_message,
    }
    _atomic_write_json(state_path, payload)
    return payload
