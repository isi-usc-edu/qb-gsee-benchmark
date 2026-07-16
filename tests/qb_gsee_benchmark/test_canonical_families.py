from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from qb_gsee_benchmark.canonical_families import (
    canonical_problem_family,
    load_canonical_families,
)

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "analysis/feature_schema/canonical_families_v1.json"


def test_canonical_family_artifacts_rebuild_and_verify() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_canonical_families.py"), "--check"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["status"] == "passed"
    assert report["effective"] is True
    assert report["task_count"] == 718
    assert report["family_count"] == 40


def test_task_split_short_names_require_task_uuid() -> None:
    document = load_canonical_families()
    mixed = [
        task
        for task in document["tasks"]
        if task["problem_instance_short_name"] == "block2_siam_ueg_script_exact"
    ]
    assert len({task["canonical_family_recommended"] for task in mixed}) == 2
    with pytest.raises(ValueError, match="task_uuid is required"):
        canonical_problem_family("block2_siam_ueg_script_exact")
    for task in mixed:
        assert (
            canonical_problem_family(
                task["problem_instance_short_name"],
                task_uuid=task["task_uuid"],
            )
            == task["canonical_family_recommended"]
        )


def test_canonical_family_lookup_fails_closed() -> None:
    document = load_canonical_families()
    task = document["tasks"][0]
    with pytest.raises(KeyError, match="absent"):
        canonical_problem_family(
            task["problem_instance_short_name"], task_uuid="missing"
        )
    with pytest.raises(ValueError, match="task/short-name mismatch"):
        canonical_problem_family("wrong-short-name", task_uuid=task["task_uuid"])


def test_mutated_binding_metadata_is_rejected(tmp_path: Path) -> None:
    document = json.loads(ARTIFACT.read_text())
    document["effective"] = False
    mutated = tmp_path / "canonical_families.json"
    mutated.write_text(json.dumps(document) + "\n")
    with pytest.raises(ValueError, match="effective O32 binding"):
        load_canonical_families(mutated)


def test_mutated_family_content_is_rejected(tmp_path: Path) -> None:
    document = json.loads(ARTIFACT.read_text())
    document["tasks"][0]["canonical_family_coarse_alternative"] = "unreviewed"
    mutated = tmp_path / "canonical_families.json"
    mutated.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_canonical_families(mutated)
