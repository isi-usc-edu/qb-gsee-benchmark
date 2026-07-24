from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

from qb_gsee_benchmark.solver_families import (
    SolverFamilyCatalog,
    enrich_attempts_with_solver_families,
    load_solver_family_catalog,
)

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "analysis/solver_taxonomy/solver_families.v1.json"
SCHEMA_PATH = ROOT / "analysis/solver_taxonomy/solver_families.v1.schema.json"


def _load_export_module():
    path = ROOT / "scripts/export_metrics_bundle.py"
    spec = importlib.util.spec_from_file_location("solver_family_export", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_solver_family_catalog_validates_and_recounts() -> None:
    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    ).validate(document)
    catalog = load_solver_family_catalog()
    assert len(catalog.families) == 12
    assert len(catalog.variants) == 44
    assert document["counts"] == {
        "families": 12,
        "variants": 44,
        "committed_variants": 28,
        "reserved_g50_variants": 16,
        "resource_ladders": 5,
    }


def test_every_committed_solution_identity_resolves_exactly() -> None:
    catalog = load_solver_family_catalog()
    observed: set[str] = set()
    for path in sorted((ROOT / "solution_files").rglob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        solver = document.get("solver_details")
        if not isinstance(solver, dict):
            continue
        metadata = catalog.resolve(
            str(solver.get("solver_uuid", "")),
            str(solver.get("solver_short_name", "")),
        )
        assert metadata.catalog_status == "committed", path
        observed.add(metadata.solver_uuid)

    declared_committed = {
        solver_uuid
        for solver_uuid, row in catalog.variants.items()
        if row["catalog_status"] == "committed"
    }
    assert observed == declared_committed


def test_g50_resource_ladders_have_stable_family_metadata() -> None:
    catalog = load_solver_family_catalog()
    expected = {
        "g50_dmrg_bond_dimension_v1": ("dmrg", [256, 512, 1024, 2048]),
        "g50_shci_orbopt_variational_eps_var_v1": (
            "shci",
            [2e-4, 1e-4, 5e-5, 2e-5],
        ),
        "g50_trimci_target_determinants_v1": (
            "trimci",
            [100000, 250000, 500000, 1000000, 2000000, 5000000, 10000000],
        ),
    }
    for ladder_id, (family_id, values) in expected.items():
        members = [
            catalog.resolve(row["solver_uuid"])
            for row in catalog.variants.values()
            if (row.get("resource_axis") or {}).get("ladder_id") == ladder_id
        ]
        members.sort(key=lambda row: int(row.resource_axis["rank"]))
        assert [row.family_id for row in members] == [family_id] * len(values)
        assert [row.resource_axis["value"] for row in members] == values
        assert [row.resource_axis["rank"] for row in members] == list(
            range(len(values))
        )
        assert {row.catalog_status for row in members} == {"reserved_g50"}


def test_solver_family_lookup_and_ladder_validation_fail_closed() -> None:
    catalog = load_solver_family_catalog()
    trimci = catalog.resolve(
        "1e75f9d9-b6cf-500d-8145-a5b0ca106102", "TrimCI_ndet_100000"
    )
    assert trimci.family_id == "trimci"
    assert trimci.as_attempt_fields()["solver_resource_rank"] == 0
    with pytest.raises(KeyError, match="absent"):
        catalog.resolve("00000000-0000-0000-0000-000000000000")
    with pytest.raises(ValueError, match="UUID/name mismatch"):
        catalog.resolve(trimci.solver_uuid, "TrimCI_ndet_250000")

    document = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    mutated = deepcopy(document)
    members = [
        row
        for row in mutated["variants"]
        if (row.get("resource_axis") or {}).get("ladder_id")
        == "g50_trimci_target_determinants_v1"
    ]
    members[-1]["resource_axis"]["rank"] = 5
    with pytest.raises(ValueError, match="ranks are not contiguous"):
        SolverFamilyCatalog(mutated)


def test_production_attempt_enrichment_propagates_solver_family_fields() -> None:
    module = _load_export_module()
    _tasks, raw_attempts = module.load_committed_artifacts(ROOT)
    attempts = enrich_attempts_with_solver_families(ROOT, raw_attempts)
    assert attempts
    required = {
        "solver_uuid",
        "solver_family_id",
        "solver_family_uuid",
        "solver_family_display_name",
        "solver_variant_id",
        "solver_variant_short_name",
        "solver_variant_display_name",
        "solver_implementation_id",
        "solver_result_semantics",
        "solver_catalog_status",
        "solver_resource_ladder_id",
        "solver_resource_axis_name",
        "solver_resource_value",
        "solver_resource_units",
        "solver_resource_rank",
    }
    assert all(required <= set(row) for row in attempts)
    assert {row["solver_catalog_status"] for row in attempts} == {"committed"}
    assert "trimci" in {row["solver_family_id"] for row in attempts}

    shci = next(row for row in attempts if row["solver"] == "SHCI_var_2e-4")
    assert shci["solver_family_id"] == "shci"
    assert shci["solver_resource_ladder_id"] == "shci_variational_eps_var_v1"
    assert shci["solver_resource_value"] == pytest.approx(2e-4)
    assert shci["solver_resource_rank"] == 0

    conflicting = [dict(raw_attempts[0]), *raw_attempts[1:]]
    conflicting[0]["solver"] = "wrong-name"
    with pytest.raises(ValueError, match="solver disagrees"):
        enrich_attempts_with_solver_families(ROOT, conflicting)
