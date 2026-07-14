#!/usr/bin/env python3
"""Prepare deterministic, restart-safe G40 P2 production shards."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import xml.etree.ElementTree as ET
from bisect import bisect_left
from pathlib import Path
from typing import Any

from qb_gsee_benchmark.features.corpus_runner import (
    CorpusFcidump,
    load_corpus_fcidumps,
    write_corpus_manifest_jsonl,
)

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _feature_norbs(path: Path) -> dict[str, int]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, int] = {}
    for row in rows:
        task_uuid = row["task_uuid"]
        if task_uuid in result:
            raise ValueError(f"duplicate feature-table task UUID {task_uuid}")
        value = row.get("n_orbs", "")
        if not value:
            raise ValueError(f"feature table lacks n_orbs for {task_uuid}")
        result[task_uuid] = int(value)
    return result


def _validate_state(
    state: dict[str, Any],
    record: CorpusFcidump,
    *,
    extractor_version: str,
    code_revision: str,
    configuration: dict[str, Any],
    contract_columns: set[str],
) -> None:
    expected = {
        "task_uuid": record.task_uuid,
        "instance_data_object_uuid": record.instance_data_object_uuid,
        "source_url": record.url,
        "declared_checksum": record.checksum,
        "declared_checksum_type": record.checksum_type,
        "manifest_signature": record.signature(),
        "manifest_ms2_metadata": record.ms2_metadata,
        "extractor_version": extractor_version,
        "code_revision": code_revision,
        "configuration": configuration,
        "status": "success",
    }
    mismatches = {
        key: {"expected": value, "observed": state.get(key)}
        for key, value in expected.items()
        if state.get(key) != value
    }
    if mismatches:
        raise ValueError(f"invalid state metadata for {record.task_uuid}: {mismatches}")
    source_sha256 = state.get("source_sha256")
    if (
        not isinstance(source_sha256, str)
        or len(source_sha256) != 64
        or any(
            character not in "0123456789abcdef" for character in source_sha256.lower()
        )
    ):
        raise ValueError(f"state {record.task_uuid} has invalid source_sha256")
    if set(state.get("features") or {}) != contract_columns:
        raise ValueError(f"state {record.task_uuid} does not match P2 contract")


def _runtime_model(
    seed_states: dict[str, dict[str, Any]], norbs: dict[str, int]
) -> tuple[list[int], list[float], dict[int, list[str]]]:
    observations: dict[int, list[tuple[float, str]]] = {}
    for task_uuid, state in seed_states.items():
        observations.setdefault(norbs[task_uuid], []).append(
            (float(state["walltime_seconds"]), task_uuid)
        )
    if not observations:
        raise ValueError("at least one passed pilot state is required")
    sample_norbs = sorted(observations)
    envelope: list[float] = []
    sources: dict[int, list[str]] = {}
    maximum = 0.0
    active_sources: list[str] = []
    for norb in sample_norbs:
        local_max = max(value for value, _ in observations[norb])
        if local_max >= maximum:
            maximum = local_max
            active_sources = sorted(
                task_uuid
                for value, task_uuid in observations[norb]
                if value == local_max
            )
        envelope.append(maximum)
        sources[norb] = list(active_sources)
    return sample_norbs, envelope, sources


def _prediction(
    norb: int, sample_norbs: list[int], envelope: list[float]
) -> tuple[float, int, str]:
    index = bisect_left(sample_norbs, norb)
    if index < len(sample_norbs):
        return envelope[index], sample_norbs[index], "next_observed_norb_envelope"
    maximum_norb = sample_norbs[-1]
    return (
        envelope[-1] * (norb / maximum_norb) ** 3,
        maximum_norb,
        "cubic_extrapolation_above_pilot_maximum",
    )


def _write_text_exact(path: Path, text: str) -> None:
    if path.exists() and path.read_text() != text:
        raise ValueError(f"refusing to replace nonmatching plan artifact {path}")
    path.write_text(text)


def _copy_bundle_evidence(source: Path, destination: Path) -> dict[str, str]:
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError(f"missing or empty bundle evidence: {source}")
    if destination.exists():
        if _sha256(destination) != _sha256(source):
            raise ValueError(f"refusing to replace nonmatching evidence {destination}")
    else:
        shutil.copyfile(source, destination)
    return {"path": str(destination), "sha256": _sha256(destination)}


def _validate_cold_junit(path: Path) -> None:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = sum(int(suite.get("tests", "0")) for suite in suites)
    failures = sum(int(suite.get("failures", "0")) for suite in suites)
    errors = sum(int(suite.get("errors", "0")) for suite in suites)
    if tests < 1 or failures or errors:
        raise ValueError(
            f"cold JUnit is not passing: tests={tests}, failures={failures}, errors={errors}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--problem-instances", type=Path, default=ROOT / "problem_instances"
    )
    parser.add_argument(
        "--feature-table",
        type=Path,
        default=ROOT / "scripts" / "Hamiltonian_features.csv",
    )
    parser.add_argument(
        "--feature-contract",
        type=Path,
        default=ROOT / "analysis" / "feature_schema" / "g40_p2_feature_contract.json",
    )
    parser.add_argument("--pilot-report", type=Path, required=True)
    parser.add_argument("--pilot-state-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--junit-xml", type=Path, required=True)
    parser.add_argument("--mock-submission-log", type=Path, required=True)
    parser.add_argument("--preflight-log", type=Path, required=True)
    parser.add_argument("--shards", type=int, default=15)
    args = parser.parse_args()
    if args.shards < 1:
        raise ValueError("--shards must be positive")

    pilot = json.loads(args.pilot_report.read_text())
    if pilot.get("status") != "passed":
        raise ValueError("production requires a passed P2 pilot")
    contract = json.loads(args.feature_contract.read_text())
    if contract.get("contract_version") != "g40_p2_feature_contract_v3":
        raise ValueError("unexpected P2 feature contract")
    if pilot["output_contract"]["sha256"] != _sha256(args.feature_contract):
        raise ValueError("pilot and production feature contracts differ")
    contract_columns = set(contract["output_columns"])
    records = load_corpus_fcidumps(args.problem_instances)
    records_by_uuid = {record.task_uuid: record for record in records}
    norbs = _feature_norbs(args.feature_table)
    if set(norbs) != set(records_by_uuid):
        raise ValueError("feature table does not exactly match the live corpus")

    expected_seed_ledger = {
        item["path"]: item["sha256"] for item in pilot["state_ledger"]
    }
    seed_paths = sorted(args.pilot_state_dir.glob("*.mfproto.json"))
    if {path.name for path in seed_paths} != set(expected_seed_ledger):
        raise ValueError("pilot state files do not exactly match its evidence ledger")
    seed_states: dict[str, dict[str, Any]] = {}
    for path in seed_paths:
        if _sha256(path) != expected_seed_ledger[path.name]:
            raise ValueError(f"pilot state checksum mismatch: {path.name}")
        state = json.loads(path.read_text())
        task_uuid = state["task_uuid"]
        if path.name != f"{task_uuid}.mfproto.json":
            raise ValueError(f"pilot state filename does not match task UUID: {path}")
        if task_uuid not in records_by_uuid:
            raise ValueError(f"pilot state is outside the live corpus: {task_uuid}")
        _validate_state(
            state,
            records_by_uuid[task_uuid],
            extractor_version=pilot["extractor_version"],
            code_revision=pilot["code_revision"],
            configuration=pilot["configuration"],
            contract_columns=contract_columns,
        )
        seed_states[task_uuid] = state

    args.output_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = args.output_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    _validate_cold_junit(args.junit_xml)
    bundle_evidence = []
    for name, source in (
        ("cold_tests.junit.xml", args.junit_xml),
        ("mock_submission.log", args.mock_submission_log),
        ("improv_preflight.log", args.preflight_log),
    ):
        destination = evidence_dir / name
        item = _copy_bundle_evidence(source, destination)
        item["path"] = str(destination.relative_to(args.output_dir))
        bundle_evidence.append(item)
    state_dir = args.output_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    for existing in sorted(state_dir.glob("*.mfproto.json")):
        state = json.loads(existing.read_text())
        task_uuid = state.get("task_uuid")
        if existing.name != f"{task_uuid}.mfproto.json":
            raise ValueError(
                f"production state filename does not match task UUID: {existing}"
            )
        if task_uuid not in records_by_uuid:
            raise ValueError(f"production state is outside live corpus: {existing}")
        _validate_state(
            state,
            records_by_uuid[task_uuid],
            extractor_version=pilot["extractor_version"],
            code_revision=pilot["code_revision"],
            configuration=pilot["configuration"],
            contract_columns=contract_columns,
        )
    for source in seed_paths:
        destination = state_dir / source.name
        if destination.exists():
            if _sha256(destination) != _sha256(source):
                raise ValueError(f"existing seeded state differs: {destination}")
            continue
        temporary = destination.with_suffix(destination.suffix + ".partial")
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)

    sample_norbs, envelope, sources = _runtime_model(seed_states, norbs)
    tasks = []
    for record in records:
        prediction, sample_norb, method = _prediction(
            norbs[record.task_uuid], sample_norbs, envelope
        )
        pending_prediction = 0.0 if record.task_uuid in seed_states else prediction
        tasks.append(
            {
                "task_uuid": record.task_uuid,
                "n_orbs": norbs[record.task_uuid],
                "manifest_signature": record.signature(),
                "preseeded_from_pilot": record.task_uuid in seed_states,
                "predicted_task_seconds": prediction,
                "predicted_pending_seconds": pending_prediction,
                "prediction_method": method,
                "prediction_sample_norb": sample_norb,
                "prediction_source_task_uuids": sources[sample_norb],
            }
        )

    shard_tasks: list[list[dict[str, Any]]] = [[] for _ in range(args.shards)]
    shard_loads = [0.0] * args.shards
    for task in sorted(
        tasks,
        key=lambda item: (-item["predicted_pending_seconds"], item["task_uuid"]),
    ):
        shard = min(range(args.shards), key=lambda index: (shard_loads[index], index))
        task["shard"] = shard
        shard_tasks[shard].append(task)
        shard_loads[shard] += task["predicted_pending_seconds"]

    write_corpus_manifest_jsonl(records, args.output_dir / "corpus_manifest.jsonl")
    for index, items in enumerate(shard_tasks):
        text = "".join(f"{item['task_uuid']}\n" for item in items)
        _write_text_exact(args.output_dir / f"shard_{index:02d}.txt", text)
    plan = {
        "plan_version": "g40_p2_production_plan_v2",
        "extractor_version": pilot["extractor_version"],
        "extractor_code_revision": pilot["code_revision"],
        "configuration": pilot["configuration"],
        "corpus_tasks": len(records),
        "shards": args.shards,
        "preseeded_states": len(seed_states),
        "predicted_pending_node_hours": sum(shard_loads) / 3600.0,
        "predicted_shard_seconds": shard_loads,
        "runtime_model": {
            "method": "monotone_next_norb_pilot_envelope_then_cubic_extrapolation",
            "sample_norbs": sample_norbs,
            "envelope_seconds": envelope,
        },
        "artifacts": {
            "pilot_report_sha256": _sha256(args.pilot_report),
            "feature_contract_sha256": _sha256(args.feature_contract),
            "input_feature_table_sha256": _sha256(args.feature_table),
            "corpus_manifest_sha256": _sha256(
                args.output_dir / "corpus_manifest.jsonl"
            ),
            "bundle_evidence": bundle_evidence,
        },
        "seed_state_ledger": [
            {"path": path.name, "sha256": _sha256(path)} for path in seed_paths
        ],
        "tasks": sorted(tasks, key=lambda item: item["task_uuid"]),
    }
    plan_text = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    _write_text_exact(args.output_dir / "production_plan.json", plan_text)
    print(
        json.dumps(
            {
                "corpus_tasks": len(records),
                "preseeded_states": len(seed_states),
                "shards": args.shards,
                "maximum_predicted_shard_seconds": max(shard_loads),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
