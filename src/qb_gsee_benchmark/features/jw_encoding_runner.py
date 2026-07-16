# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Checksum-bound, restartable G58 JW feature runner."""

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
from qb_gsee_benchmark.features.jw_encoding_features import (
    JW_ENCODING_VERSION,
    JwEncodingInfeasibleError,
    compute_jw_encoding_features,
)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def run_jw_encoding_task(
    record: CorpusFcidump,
    cache_dir: str | Path,
    state_dir: str | Path,
    *,
    offline: bool = False,
) -> dict[str, Any]:
    """Run or resume one atomic G58 task."""
    state_path = Path(state_dir) / f"{record.task_uuid}.jw-encoding.json"
    signature = record.signature()
    if state_path.exists():
        previous = json.loads(state_path.read_text())
        if (
            previous.get("status") in {"exact", "infeasible"}
            and previous.get("manifest_signature") == signature
            and previous.get("extractor_version") == JW_ENCODING_VERSION
        ):
            return previous

    started = time.monotonic()
    source_sha256 = None
    features = None
    audit = None
    reason = None
    error_type = None
    error_message = None
    try:
        source = materialize_fcidump(record, cache_dir, offline=offline)
        source_sha256 = file_checksum(source, "sha256")
    except Exception as exc:
        status = "infeasible"
        reason = "checksum_or_input_unavailable"
        error_type = type(exc).__name__
        error_message = str(exc)
    else:
        try:
            features, audit = compute_jw_encoding_features(
                source, ms2_override=record.ms2_metadata
            )
            status = "exact"
        except JwEncodingInfeasibleError as exc:
            status = "infeasible"
            reason = exc.reason
            error_type = type(exc).__name__
            error_message = str(exc)
        except Exception as exc:
            status = "failed"
            error_type = type(exc).__name__
            error_message = str(exc)
    payload = {
        "status": status,
        "infeasible_reason": reason,
        "problem_instance_short_name": record.problem_instance_short_name,
        "task_uuid": record.task_uuid,
        "instance_data_object_uuid": record.instance_data_object_uuid,
        "source_url": record.url,
        "declared_checksum": record.checksum,
        "declared_checksum_type": record.checksum_type,
        "source_sha256": source_sha256,
        "manifest_signature": signature,
        "extractor_version": JW_ENCODING_VERSION,
        "walltime_seconds": time.monotonic() - started,
        "process_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "features": features,
        "audit": audit,
        "error_type": error_type,
        "error_message": error_message,
    }
    _atomic_json(state_path, payload)
    return payload
