import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import qb_gsee_benchmark.ml.ml11c_frontend_extensions as ml11c

ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_ml11c_freeze_is_scoped_and_outcome_blind():
    protocol = _read_json(
        ROOT / "analysis/ml11c_frontend_extensions/preregistration.json"
    )
    assert protocol["status"] == "frozen_before_geometry_derivation"
    assert protocol["delivery"]["base_v3_unchanged"] is True
    assert protocol["delivery"]["prior_ml11b_addendum_unchanged"] is True
    assert protocol["geometry"]["expected_objects"] == 16
    assert protocol["geometry"]["profile_rungs"] == {
        "g50_dmrg_bond_dimension_v1": 4,
        "g50_shci_orbopt_variational_eps_var_v1": 4,
        "g50_trimci_target_determinants_v1": 7,
        "ipie_single_budget_v1": 1,
    }
    assert protocol["geometry"]["threshold_factor"] == 1.0
    assert protocol["geometry"]["normalization"] == {
        "empty_geometry": None,
        "nonempty_type": "MultiPolygon",
        "normalize_before_serialization": True,
        "rings_closed": True,
    }
    assert protocol["index_assertions"] == {
        "gradeable_population": 609,
        "no_reference_population": 109,
    }
    assert protocol["optional_contrast_display_table"]["included"] is False


def test_ml11c_schema_is_valid():
    schema = _read_json(
        ROOT
        / "analysis/ml11c_frontend_extensions/combined_addendum_v3_1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["artifact_id"]["const"] == ml11c.ARTIFACT_ID


def test_ml11c_unknown_name_gets_stub_and_warning():
    base = {"mapping": []}
    with pytest.warns(UserWarning, match="names.json stub requires public copy"):
        mapping = ml11c._extended_mapping(
            base, {("endpoint_class", "new_machine_state")}
        )
    stub = next(
        row
        for row in mapping["mapping"]
        if row["internal_identifier"] == "new_machine_state"
    )
    assert stub["public_name"] is None
    assert stub["public_description"] is None
    assert mapping["governance"]["build_warning_until_filled"] is True


def test_ml11c_combined_addendum_geometry_and_mapping(tmp_path: Path):
    output = tmp_path / "frontend_combined_addendum_v3_1"
    report = ml11c.build_combined_addendum(ROOT, output)
    assert report["status"] == "pass"
    assert report["rungs_verified"] == 16
    assert report["geometry_rows_verified"] == 68

    index = _read_json(output / "index.json")
    assert index["assertions"] == {
        "gradeable_population": 609,
        "no_reference_population": 109,
    }
    footprints = _read_json(
        output / index["entrypoints"]["per_rung_footprints"]
    )
    records = [
        dict(zip(footprints["columns"], row)) for row in footprints["rows"]
    ]
    assert Counter(row["solver_family_id"] for row in records) == {
        "dmrg": 4,
        "ipie_afqmc": 1,
        "shci": 4,
        "trimci": 7,
    }
    assert all(row["projection_refit"] is False for row in records)

    polygons = _read_json(
        output / index["entrypoints"]["per_rung_polygons"]
    )["rows"]
    for row in polygons:
        geometry = row["geometry"]
        assert geometry is None or geometry["type"] == "MultiPolygon"
        assert row["geometry_status"] in {"estimated", "degenerate", "empty"}

    registry = _read_json(
        output / index["entrypoints"]["normalized_base_geometry"]
    )["rows"]
    corpus = [
        row
        for row in registry
        if row["source_path"].endswith("pyscf_corpus_polygons.json")
    ]
    assert len(corpus) == 10
    assert all(
        row["geometry"] is None or row["geometry"]["type"] == "MultiPolygon"
        for row in corpus
    )

    names = _read_json(output / "names.json")
    assert len(names["mapping"]) == 109
    assert all(
        row["public_name"] and row["public_description"]
        for row in names["mapping"]
    )
