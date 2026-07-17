from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from qb_gsee_benchmark.public_provenance import (
    public_provenance_view,
    threshold_display_label,
)


ROOT = Path(__file__).resolve().parents[2]
G56 = ROOT / "analysis/provenance_hygiene/g56"


def load_instances() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((ROOT / "problem_instances").rglob("*.json"))
    ]


def pointer_get(document: object, pointer: str) -> object:
    current = document
    for encoded in pointer.removeprefix("/").split("/"):
        part = encoded.replace("~1", "/").replace("~0", "~")
        current = current[int(part)] if isinstance(current, list) else current[part]
    return current


def compute_threshold(convention: dict) -> float:
    parameters = convention["formula_parameters"]
    kind = convention["kind"]
    count = convention["scale_count"]
    if kind in {"fixed", "control"}:
        return parameters["fixed_value_hartree"]
    if kind == "per_site":
        return parameters["per_unit_value_hartree"] * count
    if kind == "hybrid_per_site_statistical_floor":
        return max(
            parameters["per_unit_value_hartree"] * count,
            parameters["statistical_floor_multiplier"]
            * parameters["reference_standard_error_hartree"],
        )
    if kind == "per_site_energy_scaled":
        return (
            parameters["per_site_dimensionless_factor"]
            * count
            * parameters["energy_scale_hartree"]
        )
    raise AssertionError(kind)


def test_g56_corpus_counts_thresholds_and_internal_records() -> None:
    instances = load_instances()
    assert len(instances) == 218
    tasks = [task for document in instances for task in document["tasks"]]
    assert len(tasks) == 718

    kinds = Counter()
    for task in tasks:
        requirements = task["requirements"]
        convention = requirements["threshold_convention"]
        kinds[convention["kind"]] += 1
        computed = compute_threshold(convention)
        assert computed == convention["computed_threshold_hartree"]
        assert computed == requirements["absolute_accuracy_threshold"]
        assert threshold_display_label(requirements) == convention["display_label"]
    assert kinds == {
        "fixed": 421,
        "per_site": 239,
        "hybrid_per_site_statistical_floor": 48,
        "per_site_energy_scaled": 1,
        "control": 9,
    }

    records = []
    for document in instances:
        document_records = []
        owners = [document, *document["tasks"]]
        for owner in owners:
            document_records.extend(
                owner.get("internal_provenance", {}).get("migration_records", [])
            )
        records.extend(document_records)
        for record in document_records:
            assert hashlib.sha256(record["original_value"].encode()).hexdigest() == (
                record["original_value_sha256"]
            )
            replacement = pointer_get(document, record["public_replacement_pointer"])
            assert hashlib.sha256(str(replacement).encode()).hexdigest() == (
                record["public_replacement_value_sha256"]
            )
    assert len(records) == 264


def test_g56_public_projection_is_allowlisted() -> None:
    internal_values = {
        row["value"]
        for row in csv.DictReader(
            (G56 / "source_census/g56_public_provenance_census.csv").open()
        )
        if row["internal_pointer"] == "True"
    }
    for document in load_instances():
        view = public_provenance_view(document)
        rendered = json.dumps(view, ensure_ascii=False)
        assert "internal_provenance" not in rendered
        assert not any(value in rendered for value in internal_values)
        assert "MATT_DECISION_QUEUE" not in rendered
        for local_prefix in ("analysis", "work", "scripts"):
            pattern = rf"(?<![A-Za-z0-9_:/.-]){local_prefix}/"
            assert re.search(pattern, rendered) is None


def test_g56_descriptors_encoding_and_planted_feature_mirrors() -> None:
    descriptor_rows = list(
        csv.DictReader((G56 / "g56_descriptor_ledger.csv").open())
    )
    assert len(descriptor_rows) == 234
    expected = {
        row["task_uuid"]: (
            int(row["header_num_orbitals"]),
            int(row["header_num_electrons"]),
        )
        for row in descriptor_rows
    }

    planted = []
    for document in load_instances():
        assert "â€“" not in json.dumps(document.get("references", []), ensure_ascii=False)
        for task in document["tasks"]:
            if task["task_uuid"] in expected:
                assert (
                    task["features"]["num_orbitals"],
                    task["features"]["num_electrons"],
                ) == expected[task["task_uuid"]]
            if document["short_name"].startswith("planted_solution_"):
                planted.append(task)
                assert task["planted_solution"] is True
                assert task["features"]["planted_solution"] is True
    assert len(planted) == 11


def test_g56_feature_catalog_and_prototype_paths() -> None:
    rows = list(
        csv.DictReader(
            (ROOT / "analysis/feature_schema/feature_column_metadata.csv").open()
        )
    )
    assert len(rows) == 580
    assert sum(
        row["model_eligible"] == "True" and row["cost_class"] == "jw_encoding"
        for row in rows
    ) == 17
    assert not any("legacy_jw" in json.dumps(row) for row in rows)

    for suffix in ("csv", "json", "md"):
        assert (
            ROOT
            / f"analysis/solver_panel/g31_prototype_lattice_task_mapping.{suffix}"
        ).is_file()
        assert not (
            ROOT / f"analysis/solver_panel/g31_legacy_lattice_task_mapping.{suffix}"
        ).exists()
    assert (
        ROOT / "scripts/solver_panel/build_prototype_lattice_task_mapping.py"
    ).is_file()
    assert not (
        ROOT / "scripts/solver_panel/build_legacy_lattice_task_mapping.py"
    ).exists()


def test_g56_problem_schema_validates_all_instances() -> None:
    schema_paths = [
        ROOT / "schemas/problem_instance.schema.0.0.2.json",
        ROOT / "schemas/uuid.schema.json",
        ROOT / "schemas/timestamp.schema.json",
    ]
    schemas = [json.loads(path.read_text()) for path in schema_paths]
    registry = Registry()
    for schema in schemas:
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(schema["$id"], resource)
    Draft202012Validator.check_schema(schemas[0])
    validator = Draft202012Validator(schemas[0], registry=registry)
    errors = []
    for document in load_instances():
        errors.extend(validator.iter_errors(document))
    assert not errors, "\n".join(error.message for error in errors[:20])


def test_go3_peak_rss_fields_are_optional() -> None:
    schema = json.loads(
        (ROOT / "schemas/solution.schema.0.0.1.json").read_text()
    )
    Draft202012Validator.check_schema(schema)
    resources = schema["properties"]["solution_data"]["items"]["properties"][
        "classical_resources"
    ]
    validator = Draft202012Validator(resources)
    validator.validate({})
    validator.validate(
        {
            "peak_rss_bytes": 697_540_608,
            "peak_rss_measurement_method": "/usr/bin/time -v maximum resident set size",
        }
    )
    with pytest.raises(Exception):
        validator.validate({"peak_rss_bytes": -1})


def test_g56_independent_semantic_verifier() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(G56 / "verify_g56_migration.py"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PASS: 27 independent G-56 checks" in completed.stdout
