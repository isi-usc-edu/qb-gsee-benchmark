# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Resume-safe corpus runner for G40 P2 MFPROTO-v2."""

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
from qb_gsee_benchmark.features.mfproto_extractor import (
    compute_mfproto_features,
    json_safe,
)
from qb_gsee_benchmark.features.mfproto_features import MFPROTO_VERSION
from qb_gsee_benchmark.features.mfproto_stability import (
    EXTERNAL_DIMENSION_CEILING,
)

MFPROTO_CONFIGURATION = {
    "protocol_version": MFPROTO_VERSION,
    "pyscf_version": "2.8.0",
    "scf_threads_are_environment_controlled": True,
    "external_stability_dimension_ceiling": EXTERNAL_DIMENSION_CEILING,
}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def run_mfproto_task(
    record: CorpusFcidump,
    cache_dir: str | Path,
    state_dir: str | Path,
    *,
    code_revision: str,
    offline: bool = False,
) -> dict[str, Any]:
    state_path = Path(state_dir) / f"{record.task_uuid}.mfproto.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    signature = record.signature()
    if state_path.exists():
        previous = json.loads(state_path.read_text())
        if (
            previous.get("status") == "success"
            and previous.get("manifest_signature") == signature
            and previous.get("extractor_version") == MFPROTO_VERSION
            and previous.get("code_revision") == code_revision
            and previous.get("configuration") == MFPROTO_CONFIGURATION
        ):
            return previous

    started = time.monotonic()
    try:
        source = materialize_fcidump(record, cache_dir, offline=offline)
        extraction = compute_mfproto_features(source, ms2_override=record.ms2_metadata)
        source_sha256 = file_checksum(source, "sha256")
        features = json_safe(extraction.features)
        audit = json_safe(extraction.audit)
        status, error_type, error_message = "success", None, None
    except Exception as exc:
        features, audit, source_sha256 = None, None, None
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
        "extractor_version": MFPROTO_VERSION,
        "code_revision": code_revision,
        "configuration": MFPROTO_CONFIGURATION,
        "walltime_seconds": time.monotonic() - started,
        "process_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "features": features,
        "audit": audit,
        "error_type": error_type,
        "error_message": error_message,
    }
    _atomic_write_json(state_path, payload)
    return payload
