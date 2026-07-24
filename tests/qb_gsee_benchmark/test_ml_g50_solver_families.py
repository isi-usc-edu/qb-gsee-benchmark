from __future__ import annotations

import json
from pathlib import Path

import pytest

from qb_gsee_benchmark.ml.g50_solver_families import (
    derive_feature_policy,
    g50_variant_rows,
    load_preregistration,
    run_outcome_blind_preflight,
)

ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml_g50_solver_families/preregistration.json"


def test_g50_outcome_blind_preflight(tmp_path: Path) -> None:
    report = run_outcome_blind_preflight(ROOT, PREREGISTRATION, tmp_path / "preflight")
    assert report["status"] == "pass"
    assert report["scientific_outcomes_consumed"] is False
    assert report["model_fitted"] is False
    assert report["panel"] == {
        "corpus_tasks": 718,
        "selected_tasks": 96,
        "canonical_families": 40,
        "terminal_contract_rows": 384,
        "analysis_solver_families": 4,
        "analysis_variants": 18,
    }
    assert report["feature_census"]["selected"] == 193
    assert report["feature_census"]["jw"] == 17


def test_g50_variant_catalog_has_complete_resource_ladders() -> None:
    preregistration = load_preregistration(PREREGISTRATION)
    catalog_path = ROOT / preregistration["inputs"]["solver_family_catalog"]["path"]
    rows = g50_variant_rows(catalog_path)
    assert len(rows) == 18
    by_family = {}
    for row in rows:
        by_family.setdefault(row["solver_family_id"], []).append(row)
    assert [row["resource_value"] for row in by_family["dmrg"]] == [
        256,
        512,
        1024,
        2048,
    ]
    assert [
        row["resource_value"] for row in by_family["trimci"] if row["resource_value"]
    ] == [
        100000,
        250000,
        500000,
        1000000,
        2000000,
        5000000,
        10000000,
    ]


def test_g50_preflight_rejects_changed_input_hash(tmp_path: Path) -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    payload["inputs"]["feature_table"]["sha256"] = "0" * 64
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="changed pinned input"):
        run_outcome_blind_preflight(ROOT, changed, tmp_path / "output")
