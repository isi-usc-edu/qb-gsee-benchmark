#!/usr/bin/env python3
"""Run the manifest-driven exact G40 P1-D interaction spectrum."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from qb_gsee_benchmark.features.corpus_runner import (
    load_corpus_fcidumps,
    write_corpus_manifest_jsonl,
)
from qb_gsee_benchmark.features.interaction_spectrum_runner import (
    run_interaction_spectrum_task,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--problem-instances", type=Path, default=ROOT / "problem_instances"
    )
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--task-uuid", action="append", default=[])
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("--workers must be positive")
    records = load_corpus_fcidumps(args.problem_instances)
    if args.manifest_output is not None:
        write_corpus_manifest_jsonl(records, args.manifest_output)
    selected = records
    if args.task_uuid:
        requested = set(args.task_uuid)
        selected = [record for record in records if record.task_uuid in requested]
        missing = requested - {record.task_uuid for record in selected}
        if missing:
            raise ValueError(f"unknown task UUIDs: {sorted(missing)}")
    outcomes = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                run_interaction_spectrum_task,
                record,
                args.cache_dir,
                args.state_dir,
                offline=args.offline,
            ): record
            for record in selected
        }
        for future in as_completed(futures):
            outcomes.append(future.result())
    summary = {
        "corpus_tasks": len(records),
        "selected_tasks": len(selected),
        "success": sum(item["status"] == "success" for item in outcomes),
        "failed": sum(item["status"] == "failed" for item in outcomes),
        "failed_task_uuids": sorted(
            item["task_uuid"] for item in outcomes if item["status"] == "failed"
        ),
    }
    print(json.dumps(summary, sort_keys=True))
    return int(summary["failed"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
