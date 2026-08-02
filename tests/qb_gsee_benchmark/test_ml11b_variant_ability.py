import json
from pathlib import Path

from jsonschema import Draft202012Validator

import qb_gsee_benchmark.ml.ml11b_variant_ability as ml11b

ROOT = Path(__file__).resolve().parents[2]


def test_ml11b_freeze_excludes_continuous_model_quantities():
    protocol = json.loads(
        (
            ROOT / "analysis/ml11b_variant_ability/preregistration.json"
        ).read_text(encoding="utf-8")
    )
    assert protocol["status"] == "frozen_before_extraction"
    assert protocol["promotion"]["new_sampling"] is False
    assert protocol["no_gate_decision"]["consistency_fields_null"] is True
    assert protocol["no_gate_decision"]["consistency_availability"] == (
        "excluded_continuous_model_quantity"
    )
    assert "binary_ability_mean" in protocol["authorized_fields"]
    assert "consistency_*" in protocol["excluded_fields"]


def test_ml11b_schema_is_valid():
    schema = json.loads(
        (
            ROOT
            / "analysis/ml11b_variant_ability/frontend_addendum_v3_1.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["artifact_id"]["const"] == (
        ml11b.ADDENDUM_ARTIFACT_ID
    )


def test_ml11b_two_source_extractions_and_addendum_are_deterministic(
    tmp_path: Path, monkeypatch
):
    first = tmp_path / "promotion_1"
    second = tmp_path / "promotion_2"
    final = tmp_path / "promotion_final"
    identity = tmp_path / "promotion_identity.json"
    ml11b.build_scoped_variant_ability(
        ROOT, ROOT / "analysis/ml9_bayesian_irt/raw_runs/run_1", first
    )
    ml11b.build_scoped_variant_ability(
        ROOT, ROOT / "analysis/ml9_bayesian_irt/raw_runs/run_2", second
    )
    report = ml11b.finalize_identical_runs(
        first,
        second,
        final,
        identity,
        "test_ml11b_identity",
    )
    assert report["status"] == "pass"
    assert report["file_count"] == 4
    monkeypatch.setattr(ml11b, "PROMOTION_IDENTITY", identity)

    addendum = tmp_path / "frontend_ability_addendum_v3_1"
    built = ml11b.build_addendum_bundle(ROOT, final, addendum)
    assert built["status"] == "pass"
    assert built["rows_verified"] == 18
    table = json.loads(
        (
            addendum
            / "layers/difficulty/variant_ability_consistency.json"
        ).read_text(encoding="utf-8")
    )
    records = [dict(zip(table["columns"], row)) for row in table["rows"]]
    assert len(records) == 18
    assert all(row["consistency_mean"] is None for row in records)
    assert all(
        row["consistency_availability"]
        == "excluded_continuous_model_quantity"
        for row in records
    )
