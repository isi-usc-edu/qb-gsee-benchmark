import json
from pathlib import Path

from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.g59_frontend_bundle import (
    ARTIFACT_ID,
    EXPECTED_COUNTS,
    _definitions,
)

ROOT = Path(__file__).resolve().parents[2]


def test_frontend_v2_schema_and_denominator_contract():
    schema = json.loads(
        (
            ROOT / "analysis/ml_g59_panel_refresh/frontend_bundle_v2.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["artifact_id"]["const"] == ARTIFACT_ID

    definitions = _definitions()
    denominators = definitions["denominators"]
    assert denominators["current_panel"]["n"] == 96
    assert denominators["current_gradeable_panel"]["n"] == 96
    assert denominators["current_gradeable_panel"]["same_membership_as_current_panel"]
    assert denominators["historical_final_v4_gradeable_sensitivity"]["n"] == 80
    assert EXPECTED_COUNTS["gradeable_corpus_tasks"] == 609
    assert "family-grouped" in definitions["estimators"]["design_based_ratio_of_record"]


def test_frontend_v2_distinguishes_terminal_and_ladder_semantics():
    definitions = _definitions()
    metrics = definitions["metrics"]
    assert "distinct from the last completed" in metrics["dmrg_terminal_cell"]
    assert "bounded fail" in metrics["observed_bounded_run_outcome"]
    assert definitions["display_strings"]["predicted"] == "estimated solvability"
