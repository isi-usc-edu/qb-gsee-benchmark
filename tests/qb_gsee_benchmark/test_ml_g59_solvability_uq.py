import json
from pathlib import Path

from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.core_set import sha256_file
from qb_gsee_benchmark.ml.solvability_uq import _report_schema

ROOT = Path(__file__).resolve().parents[2]
AMENDMENT = ROOT / "analysis/ml_g59_solvability_uq/amendment_post_g59_uq.json"


def test_post_g59_uq_amendment_is_frozen_and_binds_parent_artifacts():
    payload = json.loads(AMENDMENT.read_text(encoding="utf-8"))
    assert payload["amendment_id"] == "ml_g59_solvability_uq_amendment_v1"
    assert payload["frozen_before_refit"] is True
    assert payload["scope"]["training_panel_tasks"] == 96
    assert payload["scope"]["design_population_covered"] == 609
    assert payload["scope"]["design_population_orphaned"] == 0
    assert payload["frozen_policy"]["design_ratio_role"] == "ratio_of_record"
    assert payload["frozen_policy"]["validated_predictor_claim"] is False
    assert payload["prior_exposure"]["post_g59_model_fitted_before_freeze"] is False

    parent = payload["parent_uq"]
    assert (
        sha256_file(ROOT / parent["preregistration_path"])
        == parent["preregistration_sha256"]
    )
    assert (
        sha256_file(ROOT / parent["accepted_manifest_path"])
        == parent["accepted_manifest_sha256"]
    )
    panel = payload["panel_refresh"]
    assert sha256_file(ROOT / panel["amendment_path"]) == panel["amendment_sha256"]


def test_uq_report_schema_can_bind_a_revision_artifact_id():
    legacy = _report_schema()
    assert "analysis_revision" not in legacy["properties"]

    schema = _report_schema("revision-artifact", include_analysis_revision=True)
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["artifact_id"]["const"] == "revision-artifact"
    assert schema["properties"]["analysis_revision"] == {"type": "object"}
