#!/usr/bin/env python3
"""Run the read-only G45 duplicate-conflict census over the live corpus."""

from __future__ import annotations

import argparse
import json
import os
import resource
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.features.corpus_runner import (
    CorpusFcidump,
    file_checksum,
    load_corpus_fcidumps,
    materialize_fcidump,
)
from qb_gsee_benchmark.features.fcidump_conflicts import (
    DUPLICATE_CENSUS_VERSION,
    scan_duplicate_conflicts,
)


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--problem-instances",
        type=Path,
        default=ROOT / "problem_instances",
    )
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--max-tasks", type=int)
    return parser.parse_args()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def run_record(
    record: CorpusFcidump,
    cache_dir: Path,
    state_dir: Path,
    offline: bool,
) -> dict[str, Any]:
    state_path = state_dir / f"{record.task_uuid}.g45.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    signature = record.signature()
    if state_path.exists():
        previous = json.loads(state_path.read_text())
        if (
            previous.get("status") == "success"
            and previous.get("manifest_signature") == signature
            and previous.get("census_version") == DUPLICATE_CENSUS_VERSION
        ):
            return previous

    started = time.monotonic()
    try:
        source = materialize_fcidump(record, cache_dir, offline=offline)
        census = scan_duplicate_conflicts(source).to_dict()
        source_sha256 = file_checksum(source, "sha256")
        status = "success"
        error_type = None
        error_message = None
    except Exception as exc:
        census = None
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
        "census_version": DUPLICATE_CENSUS_VERSION,
        "walltime_seconds": time.monotonic() - started,
        "process_peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "census": census,
        "error_type": error_type,
        "error_message": error_message,
    }
    _atomic_write_json(state_path, payload)
    return payload


def main() -> int:
    args = parse_args()
    if args.workers < 1:
        raise ValueError("--workers must be positive")
    records = load_corpus_fcidumps(args.problem_instances)
    if args.max_tasks is not None:
        records = records[: args.max_tasks]

    outcomes = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                run_record,
                record,
                args.cache_dir,
                args.state_dir,
                args.offline,
            ): record
            for record in records
        }
        for future in as_completed(futures):
            outcomes.append(future.result())

    summary = {
        "selected_tasks": len(records),
        "success": sum(item["status"] == "success" for item in outcomes),
        "failed": sum(item["status"] == "failed" for item in outcomes),
        "failed_task_uuids": sorted(
            item["task_uuid"]
            for item in outcomes
            if item["status"] == "failed"
        ),
    }
    print(json.dumps(summary, sort_keys=True))
    return int(summary["failed"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
