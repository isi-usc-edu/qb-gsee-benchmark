from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import pytest

from qb_gsee_benchmark.features.corpus_runner import load_corpus_fcidumps
from scripts.verify_g52_gao_candidate import _verify

ROOT = Path(__file__).resolve().parents[2]
GAO = ROOT / "problem_instances" / "small_molecules" / "gao_distributed_fci"
PREMERGE_TABLE_SHA256 = (
    "8f0d89ec2cc7cf933a57c4ace7d32cd62d478c0fb8f8272aae4d36d387d45b2b"
)
ACKNOWLEDGED_G58_TABLE_SHA256 = (
    "b5f8a78c3fd8fa9ba1e5dce4e8e2986bfc19346b26375e22763816efa5cdc8f7"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def test_g52_public_table_is_a_reviewed_release_state() -> None:
    table = ROOT / "scripts" / "Hamiltonian_features.csv"
    report = json.loads(
        (ROOT / "analysis/feature_schema/g40_p2_production_report.json").read_text()
    )
    contract = ROOT / "analysis/feature_schema/g40_p2_feature_contract.json"
    corpus = {
        record.task_uuid for record in load_corpus_fcidumps(ROOT / "problem_instances")
    }
    gao = {record.task_uuid for record in load_corpus_fcidumps(GAO)}
    public = {row["task_uuid"] for row in _rows(table)}
    table_sha256 = _sha256(table)

    assert len(corpus) == 718
    assert len(gao) == 127
    assert report["status"] == "passed"
    assert report["successful_states"] == 591
    assert report["feature_contract_sha256"] == _sha256(contract)
    if table_sha256 == PREMERGE_TABLE_SHA256:
        assert len(public) == 591
        assert public == corpus - gao
        assert report["output_feature_table_sha256"] == table_sha256
    else:
        assert table_sha256 == ACKNOWLEDGED_G58_TABLE_SHA256
        assert len(public) == 718
        assert public == corpus


def _instance(task_uuid: str, data_uuid: str, short_name: str) -> dict[str, object]:
    return {
        "problem_instance_uuid": f"instance-{task_uuid}",
        "short_name": short_name,
        "tasks": [
            {
                "task_uuid": task_uuid,
                "features": {"num_orbitals": 2, "num_electrons": 2, "ms2": 0},
                "supporting_files": [
                    {
                        "instance_data_object_uuid": data_uuid,
                        "instance_data_object_url": f"https://example.test/{data_uuid}.fcidump",
                        "instance_data_checksum": "0" * 40,
                        "instance_data_checksum_type": "sha1sum",
                        "is_fcidump_file": True,
                    }
                ],
            }
        ],
    }


def test_g52_candidate_verifier_preserves_accepted_rows_and_merge_gate(
    tmp_path: Path,
) -> None:
    instances = tmp_path / "instances"
    gao_instances = instances / "gao"
    old_instances = instances / "old"
    gao_instances.mkdir(parents=True)
    old_instances.mkdir()
    old_task = "old-task"
    gao_task = "gao-task"
    (old_instances / "old.json").write_text(
        json.dumps(_instance(old_task, "old-data", "old")) + "\n"
    )
    (gao_instances / "gao.json").write_text(
        json.dumps(_instance(gao_task, "gao-data", "gao")) + "\n"
    )

    fields = ["task_uuid", "n_orbs", "mfproto_features_version"]
    public_table = tmp_path / "public.csv"
    candidate_table = tmp_path / "candidate.csv"
    with public_table.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow(
            {
                "task_uuid": old_task,
                "n_orbs": "2",
                "mfproto_features_version": "g40_p2_mfproto_v3",
            }
        )
    with candidate_table.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "task_uuid": old_task,
                    "n_orbs": "2",
                    "mfproto_features_version": "g40_p2_mfproto_v3",
                },
                {
                    "task_uuid": gao_task,
                    "n_orbs": "2",
                    "mfproto_features_version": "g40_p2_mfproto_v3",
                },
            ]
        )
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_version": "g52_gao_p2_backfill_plan_v1",
                "corpus_tasks": 2,
                "preseeded_states": 1,
                "pending_tasks": 1,
                "pending_only_shards": True,
                "tasks": [
                    {"task_uuid": old_task, "preseeded_from_pilot": True},
                    {"task_uuid": gao_task, "preseeded_from_pilot": False},
                ],
            }
        )
        + "\n"
    )
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "status": "passed",
                "report_version": "g52_gao_p2_backfill_v1",
                "successful_states": 2,
                "rows_after": 2,
                "columns_after": 3,
                "changed_populated_cells": 0,
                "output_feature_table_sha256": _sha256(candidate_table),
                "pbs_gate": {"node_hours": 1.25},
            }
        )
        + "\n"
    )
    args = argparse.Namespace(
        public_feature_table=public_table,
        candidate_feature_table=candidate_table,
        problem_instances=instances,
        gao_instances=gao_instances,
        production_plan=plan,
        production_report=report,
        expected_public_rows=1,
        expected_gao_rows=1,
        expected_total_rows=2,
        maximum_node_hours=15.0,
    )
    result = _verify(args)
    assert result["status"] == "passed"
    assert result["public_merge_authorized"] is False

    rows = _rows(candidate_table)
    rows[0]["n_orbs"] = "3"
    with candidate_table.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="changed accepted rows"):
        _verify(args)
