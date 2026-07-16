#!/usr/bin/env python3
# Copyright 2026.
# Licensed under the Apache License, Version 2.0.
"""Run selected G58 JW encoding tasks."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from qb_gsee_benchmark.features.corpus_runner import load_corpus_fcidumps
from qb_gsee_benchmark.features.jw_encoding_runner import run_jw_encoding_task


def _run(arguments: tuple[object, ...]) -> dict[str, object]:
    record, cache_dir, state_dir, offline = arguments
    return run_jw_encoding_task(
        record,
        cache_dir,
        state_dir,
        offline=bool(offline),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem-instances", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    selected = {
        line.strip() for line in args.selection.read_text().splitlines() if line.strip()
    }
    manifest = load_corpus_fcidumps(args.problem_instances)
    records = [record for record in manifest if record.task_uuid in selected]
    if {record.task_uuid for record in records} != selected:
        missing = sorted(selected - {record.task_uuid for record in records})
        raise ValueError(f"selection contains unknown tasks: {missing}")
    if args.workers < 1 or args.workers > 128:
        raise ValueError("workers must be in [1, 128]")

    work = [
        (record, args.cache_dir, args.state_dir, args.offline) for record in records
    ]
    counts: dict[str, int] = {}
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_run, item): item[0].task_uuid for item in work}
        for future in as_completed(futures):
            result = future.result()
            status = str(result["status"])
            counts[status] = counts.get(status, 0) + 1
            print(
                json.dumps(
                    {
                        "task_uuid": result["task_uuid"],
                        "status": status,
                        "walltime_seconds": result["walltime_seconds"],
                        "process_peak_rss_kb": result["process_peak_rss_kb"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    print(json.dumps({"terminal_counts": counts}, sort_keys=True))
    return int(bool(counts.get("failed") or counts.get("timeout")))


if __name__ == "__main__":
    raise SystemExit(main())
