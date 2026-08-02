import json
from pathlib import Path

from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.ml11_frontend_bundle import (
    ARTIFACT_ID,
    _definitions,
    _forbidden_term,
    build_ml11_frontend_bundle,
    verify_ml11_frontend_bundle,
)

ROOT = Path(__file__).resolve().parents[2]


def test_ml11_schema_and_normative_definitions():
    schema = json.loads(
        (
            ROOT
            / "analysis/ml11_frontend_bundle/frontend_bundle_v3.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["artifact_id"]["const"] == ARTIFACT_ID

    protocol = json.loads(
        (
            ROOT / "analysis/ml11_frontend_bundle/preregistration.json"
        ).read_text(encoding="utf-8")
    )
    definitions = _definitions(protocol)
    assert definitions["definitions_are_normative"]
    assert definitions["contract_requirement"] == "P-7"
    assert definitions["metric_distinction"]["binding_selection_columns"] == 191
    assert definitions["metric_distinction"]["frontend_feature_columns"] == 193
    assert not definitions["release"]["public_deployment_authorized"]


def test_ml11_protocol_keeps_promoted_scope_and_no_gate_disclosure():
    protocol = json.loads(
        (
            ROOT / "analysis/ml11_frontend_bundle/preregistration.json"
        ).read_text(encoding="utf-8")
    )
    assert protocol["execution"]["source_policy"] == "promoted artifact trees only"
    assert not protocol["execution"]["new_analysis"]
    assert not protocol["execution"]["new_solver_runs"]
    decision = protocol["no_gate_decisions"]["per_variant_ability_consistency"]
    assert decision["status"] == "unavailable_from_promoted_scope"


def test_ml11_build_is_complete_and_uses_clean_vocabulary(tmp_path):
    output = tmp_path / "frontend_bundle_v3"
    report = build_ml11_frontend_bundle(ROOT, output)
    assert report["status"] == "pass"
    assert verify_ml11_frontend_bundle(output)["index_sha256"] == report["index_sha256"]

    index = json.loads((output / "index.json").read_text(encoding="utf-8"))
    assert index["counts"]["g50_retained_dmrg_terminal_cells"] == 66
    assert index["counts"]["difficulty_tasks"] == 96
    assert index["counts"]["group_multiplicity_rows"] == 25
    assert index["counts"]["pyscf_label_rows"] == 3590
    availability = json.loads(
        (
            output / "layers/difficulty/variant_ability_consistency.json"
        ).read_text(encoding="utf-8")
    )
    assert availability["rows"] == []
    forbidden = _forbidden_term()
    assert all(
        forbidden not in path.read_bytes().lower()
        for path in output.rglob("*")
        if path.is_file()
    )
