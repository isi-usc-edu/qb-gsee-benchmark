# Copyright 2026.
# Licensed under the Apache License, Version 2.0.

"""Resume-safe corpus runner for G40 P1-C."""

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
from qb_gsee_benchmark.features.orderability_features import (
    ORDERABILITY_VERSION,
    RANDOM_ORDER_SEED,
    compute_orderability_features,
)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def run_orderability_task(
    record: CorpusFcidump,
    cache_dir: str | Path,
    state_dir: str | Path,
    *,
    offline: bool = False,
    random_seed: int = RANDOM_ORDER_SEED,
) -> dict[str, Any]:
    """Run or resume one checksum- and configuration-bound P1-C task."""
    state_path = Path(state_dir) / f"{record.task_uuid}.orderability.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    signature = record.signature()
    configuration = {"random_seed": random_seed}
    if state_path.exists():
        previous = json.loads(state_path.read_text())
        if (
            previous.get("status") == "success"
            and previous.get("manifest_signature") == signature
            and previous.get("extractor_version") == ORDERABILITY_VERSION
            and previous.get("configuration") == configuration
        ):
            return previous

    started = time.monotonic()
    try:
        source = materialize_fcidump(record, cache_dir, offline=offline)
        features = compute_orderability_features(
            source,
            ms2_override=record.ms2_metadata,
            random_seed=random_seed,
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
        "extractor_version": ORDERABILITY_VERSION,
        "configuration": configuration,
        "walltime_seconds": time.monotonic() - started,
        "process_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "features": features,
        "error_type": error_type,
        "error_message": error_message,
    }
    _atomic_write_json(state_path, payload)
    return payload
