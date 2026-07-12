#!/usr/bin/env python3
"""Run the manifest-driven G40 R6 orderability-degeneracy backfill."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from qb_gsee_benchmark.features.corpus_runner import (
    load_corpus_fcidumps,
    write_corpus_manifest_jsonl,
)
from qb_gsee_benchmark.features.orderability_degeneracy_runner import (
    run_orderability_degeneracy_task,
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
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("--workers must be positive")
    records = load_corpus_fcidumps(args.problem_instances)
    if args.manifest_output is not None:
        write_corpus_manifest_jsonl(records, args.manifest_output)
    outcomes = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                run_orderability_degeneracy_task,
                record,
                args.cache_dir,
                args.state_dir,
                offline=args.offline,
            ): record
            for record in records
        }
        for future in as_completed(futures):
            outcomes.append(future.result())
    summary = {
        "corpus_tasks": len(records),
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
