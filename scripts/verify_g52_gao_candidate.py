#!/usr/bin/env python3
"""Fail-closed verification for the private G52 Gao P2 candidate table."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

from qb_gsee_benchmark.features.corpus_runner import load_corpus_fcidumps

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _table(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"missing feature-table header: {path}")
        return list(reader.fieldnames), list(reader)


def _verify(args: argparse.Namespace) -> dict[str, object]:
    public_fields, public_rows = _table(args.public_feature_table)
    candidate_fields, candidate_rows = _table(args.candidate_feature_table)
    public = {row["task_uuid"]: row for row in public_rows}
    candidate = {row["task_uuid"]: row for row in candidate_rows}
    corpus = {r.task_uuid for r in load_corpus_fcidumps(args.problem_instances)}
    gao = {r.task_uuid for r in load_corpus_fcidumps(args.gao_instances)}
    if len(public) != args.expected_public_rows or len(public) != len(public_rows):
        raise ValueError("unexpected or duplicate public feature rows")
    if len(gao) != args.expected_gao_rows:
        raise ValueError("unexpected Gao task count")
    if len(candidate) != args.expected_total_rows or len(candidate) != len(
        candidate_rows
    ):
        raise ValueError("unexpected or duplicate candidate feature rows")
    if public_fields != candidate_fields:
        raise ValueError("G52 candidate changed the feature-table schema")
    if set(public) != corpus - gao or set(candidate) != corpus:
        raise ValueError("G52 candidate UUID partition is not 591 plus 127")
    changed_common = [
        task_uuid for task_uuid in public if public[task_uuid] != candidate[task_uuid]
    ]
    if changed_common:
        raise ValueError(f"G52 candidate changed accepted rows: {changed_common[:3]}")

    plan = json.loads(args.production_plan.read_text())
    pending = {
        item["task_uuid"] for item in plan["tasks"] if not item["preseeded_from_pilot"]
    }
    if (
        plan.get("plan_version") != "g52_gao_p2_backfill_plan_v1"
        or plan.get("corpus_tasks") != args.expected_total_rows
        or plan.get("preseeded_states") != args.expected_public_rows
        or plan.get("pending_tasks") != args.expected_gao_rows
        or not plan.get("pending_only_shards")
        or pending != gao
    ):
        raise ValueError("G52 plan does not pin exactly the 127 Gao tasks")

    report = json.loads(args.production_report.read_text())
    if (
        report.get("status") != "passed"
        or report.get("report_version") != "g52_gao_p2_backfill_v1"
        or report.get("successful_states") != args.expected_total_rows
        or report.get("rows_after") != args.expected_total_rows
        or report.get("columns_after") != len(candidate_fields)
        or report.get("changed_populated_cells") != 0
        or report.get("output_feature_table_sha256")
        != _sha256(args.candidate_feature_table)
        or report.get("pbs_gate", {}).get("node_hours", args.maximum_node_hours + 1)
        > args.maximum_node_hours
    ):
        raise ValueError("G52 production report failed the release-candidate gate")
    return {
        "report_version": "g52_gao_candidate_verification_v1",
        "status": "passed",
        "public_rows": len(public),
        "gao_rows": len(gao),
        "candidate_rows": len(candidate),
        "columns": len(candidate_fields),
        "changed_accepted_rows": 0,
        "public_feature_table_sha256": _sha256(args.public_feature_table),
        "candidate_feature_table_sha256": _sha256(args.candidate_feature_table),
        "production_plan_sha256": _sha256(args.production_plan),
        "production_report_sha256": _sha256(args.production_report),
        "actual_node_hours": report["pbs_gate"]["node_hours"],
        "public_merge_authorized": False,
    }


def _junit(path: Path, elapsed: float, error: BaseException | None) -> None:
    suite = ET.Element(
        "testsuite",
        name="g52_gao_candidate",
        tests="1",
        failures=str(int(error is not None)),
        errors="0",
        time=f"{elapsed:.6f}",
    )
    case = ET.SubElement(
        suite,
        "testcase",
        classname="g52",
        name="candidate_release_gate",
        time=f"{elapsed:.6f}",
    )
    if error is not None:
        failure = ET.SubElement(
            case, "failure", message=str(error), type=type(error).__name__
        )
        failure.text = traceback.format_exc()
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--public-feature-table",
        type=Path,
        default=ROOT / "scripts" / "Hamiltonian_features.csv",
    )
    parser.add_argument("--candidate-feature-table", type=Path, required=True)
    parser.add_argument(
        "--problem-instances", type=Path, default=ROOT / "problem_instances"
    )
    parser.add_argument("--gao-instances", type=Path, required=True)
    parser.add_argument("--production-plan", type=Path, required=True)
    parser.add_argument("--production-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--junit-xml", type=Path, required=True)
    parser.add_argument("--expected-public-rows", type=int, default=591)
    parser.add_argument("--expected-gao-rows", type=int, default=127)
    parser.add_argument("--expected-total-rows", type=int, default=718)
    parser.add_argument("--maximum-node-hours", type=float, default=15.0)
    args = parser.parse_args()
    started = time.monotonic()
    try:
        result = _verify(args)
    except BaseException as error:
        _junit(args.junit_xml, time.monotonic() - started, error)
        raise
    _junit(args.junit_xml, time.monotonic() - started, None)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
