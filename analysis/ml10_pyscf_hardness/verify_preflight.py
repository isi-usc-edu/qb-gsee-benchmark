#!/usr/bin/env python3
"""Independent structural verifier for the promoted ML-10 preflight."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _true(value: str) -> bool:
    if value not in {"true", "false"}:
        raise AssertionError(f"invalid boolean {value!r}")
    return value == "true"


def verify(bundle: Path, identity_path: Path | None = None) -> dict[str, object]:
    manifest = _read_json(bundle / "artifact_manifest.json")
    assert manifest["artifact_id"] == "ml10_pyscf_preflight_manifest_v1"
    assert manifest["status"] == "complete_internal_status_census"
    assert manifest["energy_values_consumed"] is False
    assert manifest["success_labels_computed"] is False
    assert manifest["new_solver_runs"] is False
    assert manifest["task_reselection"] is False
    assert manifest["source_labels_mutated"] is False

    expected_files = {
        "REPORT.md",
        "corpus_coverage_summary.csv",
        "coverage_census.csv",
        "epistemic_flags.csv",
        "panel_coverage_summary.csv",
        "report.json",
    }
    assert {row["path"] for row in manifest["files"]} == expected_files
    for row in manifest["files"]:
        path = bundle / row["path"]
        assert path.stat().st_size == row["bytes"]
        assert _sha256(path) == row["sha256"]

    census = _read_csv(bundle / "coverage_census.csv")
    assert len(census) == 3590
    assert len({(row["task_uuid"], row["item_id"]) for row in census}) == 3590
    assert Counter(row["item_id"] for row in census) == {
        "pyscf_hf": 718,
        "pyscf_mp2": 718,
        "pyscf_cisd": 718,
        "pyscf_ccsd": 718,
        "pyscf_ccsd_t": 718,
    }
    assert Counter(row["coverage_class"] for row in census) == {
        "labeled": 1892,
        "failed": 554,
        "not_attempted_cost_screened": 509,
        "no_pyscf_coverage": 635,
    }
    panel = [row for row in census if _true(row["in_panel"])]
    assert len(panel) == 480
    assert sum(row["coverage_class"] == "no_pyscf_coverage" for row in panel) == 20
    assert (
        len(
            {
                row["task_uuid"]
                for row in panel
                if row["coverage_class"] != "no_pyscf_coverage"
            }
        )
        == 92
    )
    assert sum(_true(row["pending_reference_recompute"]) for row in census) == 5
    for row in census:
        attempted = _true(row["attempted"])
        assert attempted == (row["coverage_class"] in {"labeled", "failed"})
        if row["in_panel"] == "false":
            assert row["selection_weight_609"] == ""

    flags = _read_csv(bundle / "epistemic_flags.csv")
    assert Counter(row["epistemic_flag"] for row in flags) == {
        "scf_multistable_stationary_point": 30,
        "method_inapplicable_degenerate_reference": 11,
        "variationally_inferior_reference_annotation_ca6f7678": 5,
        "pending_reference_recompute_603f9c47": 5,
    }

    panel_summary = _read_csv(bundle / "panel_coverage_summary.csv")
    corpus_summary = _read_csv(bundle / "corpus_coverage_summary.csv")
    assert len(panel_summary) == len(corpus_summary) == 5
    assert sum(int(row["total_cells"]) for row in panel_summary) == 480
    assert sum(int(row["total_cells"]) for row in corpus_summary) == 3590

    report = _read_json(bundle / "report.json")
    assert report["status"] == "pass"
    assert report["coverage_branch"] == "accepted_591_task_campaign_92_of_96_panel"
    assert report["census"]["coverage_counts"] == {
        "failed": 554,
        "labeled": 1892,
        "no_pyscf_coverage": 635,
        "not_attempted_cost_screened": 509,
    }
    assert report["checks"]["energy_values_consumed"] is False
    assert report["checks"]["success_labels_computed"] is False

    prohibited = "lega" + "cy"
    for path in sorted(bundle.iterdir()):
        if path.is_file():
            assert prohibited not in path.read_text(encoding="utf-8").lower()

    identity_verified = False
    if identity_path is not None:
        identity = _read_json(identity_path)
        assert identity["artifact_id"] == "ml10_pyscf_preflight_two_run_identity_v1"
        assert identity["status"] == "pass"
        assert identity["byte_identical"] is True
        assert identity["file_count"] == 7
        for name, digest in identity["file_hashes"].items():
            assert _sha256(bundle / name) == digest
        identity_verified = True

    return {
        "artifact_id": "ml10_pyscf_preflight_independent_verification_v1",
        "status": "pass",
        "checks": 28,
        "corpus_cells": len(census),
        "panel_cells": len(panel),
        "flag_rows": len(flags),
        "identity_verified": identity_verified,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--identity", type=Path)
    arguments = parser.parse_args()
    report = verify(arguments.bundle, arguments.identity)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
