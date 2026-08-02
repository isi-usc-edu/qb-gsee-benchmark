"""Deterministic internal frontend bundle over accepted promoted ML artifacts."""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.core_set import _require, sha256_file
from qb_gsee_benchmark.ml.g50_frontend_bundle import (
    _file_record,
    _json_scalar,
    _write_json,
    write_deterministic_zip,
)
from qb_gsee_benchmark.ml.g59_frontend_bundle import build_g59_frontend_bundle

ARTIFACT_ID = "ml11_frontend_bundle_v3"
SCHEMA_VERSION = "3.0.0"
ANALYSIS_DIRECTORY = Path("analysis/ml11_frontend_bundle")
PREREGISTRATION = ANALYSIS_DIRECTORY / "preregistration.json"
CONTRACT = ANALYSIS_DIRECTORY / "CONTRACT.md"
INDEX_SCHEMA = ANALYSIS_DIRECTORY / "frontend_bundle_v3.schema.json"
BUNDLE_NAME = "frontend_bundle_v3"


@dataclass(frozen=True)
class TableSpec:
    layer: str
    name: str
    source_id: str
    source: str
    primary_key: tuple[str, ...]
    estimate_label: str


TABLE_SPECS = (
    TableSpec("instance_space", "coordinates", "instance_space", "analysis/ml9_instance_space/final_v1/corpus_coordinates.csv", ("task_uuid",), "frozen coordinate estimate"),
    TableSpec("instance_space", "panel_coordinates", "instance_space", "analysis/ml9_instance_space/final_v1/panel_coordinates.csv", ("task_uuid",), "frozen coordinate estimate"),
    TableSpec("instance_space", "solver_family_footprints", "instance_space", "analysis/ml9_instance_space/final_v1/trace_footprints.csv", ("threshold_factor", "target", "footprint_kind"), "descriptive geometry estimate"),
    TableSpec("instance_space", "solver_family_bootstrap_intervals", "instance_space", "analysis/ml9_instance_space/final_v1/bootstrap_intervals.csv", ("threshold_factor", "target", "footprint_kind", "metric"), "family-block bootstrap estimate"),
    TableSpec("instance_space", "cloister_boundary", "instance_space", "analysis/ml9_instance_space/final_v1/cloister_boundary.csv", ("boundary_id", "vertex_index"), "frozen theoretical boundary estimate"),
    TableSpec("instance_space", "solver_family_pythia_gates", "instance_space", "analysis/ml9_instance_space/final_v1/pythia_gate.csv", ("threshold_factor", "target"), "cross-validated feature-adequacy estimate"),
    TableSpec("instance_space", "acquisition_priorities", "instance_space", "analysis/ml9_instance_space/final_v1/priority_targets.csv", ("task_uuid",), "acquisition-priority estimate"),
    TableSpec("instance_space", "projection_features", "instance_space", "analysis/ml9_instance_space/final_v1/projection_features.csv", ("projection_rank",), "frozen projection artifact"),
    TableSpec("instance_space", "feature_preprocessing", "instance_space", "analysis/ml9_instance_space/final_v1/feature_preprocessing.csv", ("column",), "frozen preprocessing artifact"),
    TableSpec("instance_space", "projection_matrix", "instance_space", "analysis/ml9_instance_space/final_v1/projection_matrix.csv", ("axis", "column"), "frozen projection artifact"),
    TableSpec("instance_space", "pyscf_panel_footprints", "pyscf_instance_space", "analysis/ml10_instance_space/final_v3/panel_trace_footprints.csv", ("target",), "descriptive geometry estimate"),
    TableSpec("instance_space", "pyscf_corpus_footprints", "pyscf_instance_space", "analysis/ml10_instance_space/final_v3/corpus_trace_footprints.csv", ("target",), "external observed geometry estimate"),
    TableSpec("instance_space", "pyscf_bootstrap_intervals", "pyscf_instance_space", "analysis/ml10_instance_space/final_v3/bootstrap_intervals.csv", ("target", "metric"), "family-block bootstrap estimate"),
    TableSpec("instance_space", "pyscf_panel_pythia_gates", "pyscf_instance_space", "analysis/ml10_instance_space/final_v3/panel_pythia_gate.csv", ("target",), "cross-validated feature-adequacy estimate"),
    TableSpec("instance_space", "pyscf_external_validation", "pyscf_instance_space", "analysis/ml10_instance_space/final_v3/corpus_validation.csv", ("target",), "external-validation estimate"),
    TableSpec("instance_space", "portfolio_union", "pyscf_instance_space", "analysis/ml10_instance_space/final_v3/portfolio_union_comparison.csv", ("portfolio",), "observed portfolio summary"),
    TableSpec("difficulty", "task_difficulty", "difficulty", "analysis/ml9_bayesian_irt/final_v1/difficulty_handoff_ml9d.csv", ("task_uuid",), "frozen posterior estimate"),
    TableSpec("resource_profiles", "ladder_endpoints", "ladder_resource_profiles", "analysis/ml9_resource_profiles/final_v1/resource_to_solution.csv", ("task_uuid", "profile_track_id", "threshold_factor"), "observed censored endpoint"),
    TableSpec("resource_profiles", "ladder_profiles", "ladder_resource_profiles", "analysis/ml9_resource_profiles/final_v1/data_profiles.csv", ("profile_track_id", "threshold_factor", "resource_rank"), "descriptive profile"),
    TableSpec("resource_profiles", "ladder_stability", "ladder_resource_profiles", "analysis/ml9_resource_profiles/final_v1/threshold_stability.csv", ("profile_track_id", "comparison_threshold_factor"), "descriptive stability estimate"),
    TableSpec("resource_profiles", "ladder_conditional_quantiles", "ladder_resource_profiles", "analysis/ml9_resource_profiles/final_v1/conditional_resource_quantiles.csv", ("profile_track_id", "threshold_factor"), "success-conditional quantile estimate"),
    TableSpec("resource_profiles", "combined_endpoints", "combined_resource_profiles", "analysis/ml10_resource_profiles/final_v3/resource_to_solution.csv", ("task_uuid", "profile_track_id", "threshold_factor"), "observed censored endpoint"),
    TableSpec("resource_profiles", "combined_profiles", "combined_resource_profiles", "analysis/ml10_resource_profiles/final_v3/data_profiles.csv", ("profile_track_id", "threshold_factor", "resource_rank"), "descriptive profile"),
    TableSpec("resource_profiles", "combined_stability", "combined_resource_profiles", "analysis/ml10_resource_profiles/final_v3/threshold_stability.csv", ("profile_track_id", "comparison_threshold_factor"), "descriptive stability estimate"),
    TableSpec("resource_profiles", "combined_conditional_quantiles", "combined_resource_profiles", "analysis/ml10_resource_profiles/final_v3/conditional_resource_quantiles.csv", ("profile_track_id", "threshold_factor"), "success-conditional quantile estimate"),
    TableSpec("resource_profiles", "pyscf_single_budget_profiles", "combined_resource_profiles", "analysis/ml10_resource_profiles/final_v3/pyscf_single_budget_profiles.csv", ("method", "threshold_factor"), "partially identified descriptive estimate"),
    TableSpec("resource_profiles", "combined_runstatus", "combined_resource_profiles", "analysis/ml10_resource_profiles/final_v3/runstatus.csv", ("task_uuid", "solver_variant_id", "threshold_factor"), "observed run status"),
    TableSpec("resource_profiles", "combined_attempt_coverage", "combined_resource_profiles", "analysis/ml10_resource_profiles/final_v3/attempt_coverage.csv", ("task_uuid", "solver_variant_id"), "observed attempt coverage"),
    TableSpec("resource_profiles", "companion_variants", "combined_resource_profiles", "analysis/ml10_resource_profiles/final_v3/companion_variants.csv", ("task_uuid", "solver_variant_id", "threshold_factor"), "observed companion status"),
    TableSpec("group_inference", "contrast_estimates", "group_inference", "analysis/ml9_grouped_inference/final_v1/contrast_estimates.csv", ("target_kind", "target", "contrast_id", "estimator"), "grouped descriptive inference estimate"),
    TableSpec("group_inference", "multiplicity_results", "group_inference", "analysis/ml9_grouped_inference/final_v1/multiplicity_results.csv", ("target_kind", "target", "contrast_id"), "multiplicity-adjusted inference estimate"),
    TableSpec("pyscf", "labels", "pyscf_labels", "analysis/ml10_pyscf_desk/final_v2/pyscf_labels.csv", ("task_uuid", "item_id"), "observed label or explicit missingness class"),
    TableSpec("pyscf", "method_frontiers", "pyscf_labels", "analysis/ml10_pyscf_desk/final_v2/method_frontiers.csv", ("task_uuid",), "observed method frontier"),
    TableSpec("pyscf", "panel_unions", "pyscf_labels", "analysis/ml10_pyscf_desk/final_v2/panel_unions.csv", ("target",), "descriptive union estimate"),
    TableSpec("pyscf", "design_based_ratios", "pyscf_labels", "analysis/ml10_pyscf_desk/final_v2/design_based_ratios.csv", ("item_id",), "design-based descriptive estimate"),
    TableSpec("pyscf", "corpus_near_census_rates", "pyscf_labels", "analysis/ml10_pyscf_desk/final_v2/corpus_near_census_rates.csv", ("item_id",), "near-census descriptive estimate"),
)

JSON_SPECS = (
    ("instance_space", "solver_family_polygons", "instance_space", "analysis/ml9_instance_space/final_v1/trace_polygons.json", "descriptive geometry estimate"),
    ("instance_space", "cloister_coverage", "instance_space", "analysis/ml9_instance_space/final_v1/cloister_coverage.json", "frozen theoretical coverage estimate"),
    ("instance_space", "pyscf_panel_polygons", "pyscf_instance_space", "analysis/ml10_instance_space/final_v3/panel_trace_polygons.json", "descriptive geometry estimate"),
    ("instance_space", "pyscf_corpus_polygons", "pyscf_instance_space", "analysis/ml10_instance_space/final_v3/corpus_trace_polygons.json", "external observed geometry estimate"),
    ("instance_space", "projection_binding", "pyscf_instance_space", "analysis/ml10_instance_space/final_v3/projection_binding.json", "frozen projection audit fact"),
)

BASE_FILES = (
    "catalog.json",
    "features.json",
    "observations.json",
    "coverage.json",
    "summaries.json",
    "uncertainty.json",
    "dmrg_terminal_cells.json",
    "g59_parent_terminal_cells.json",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _table_records(payload: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    for row in payload["rows"]:
        yield dict(zip(payload["columns"], row))


def _table_payload(root: Path, spec: TableSpec) -> dict[str, Any]:
    source = root / spec.source
    frame = pd.read_csv(source, float_precision="round_trip", low_memory=False)
    columns = list(map(str, frame.columns))
    _require(set(spec.primary_key) <= set(columns), f"missing key: {spec.name}")
    rows = [
        [_json_scalar(value) for value in row]
        for row in frame.itertuples(index=False, name=None)
    ]
    keys = [
        tuple(row[columns.index(column)] for column in spec.primary_key)
        for row in rows
    ]
    _require(len(keys) == len(set(keys)), f"duplicate key: {spec.name}")
    return {
        "artifact_id": f"{ARTIFACT_ID}_{spec.name}",
        "bundle_materialization": "derivable_at_export",
        "columns": columns,
        "encoding": "row_array_table_v1",
        "estimate_label": spec.estimate_label,
        "layer": spec.layer,
        "primary_key": list(spec.primary_key),
        "rows": rows,
        "source_id": spec.source_id,
        "source_path": spec.source,
        "source_sha256": sha256_file(source),
        "source_state": "frozen_artifact",
        "table_name": spec.name,
    }


def _verify_sources(root: Path, preregistration: Mapping[str, Any]) -> None:
    for binding in preregistration["source_bindings"]:
        manifest_path = root / binding["manifest_path"]
        identity_path = root / binding["identity_path"]
        _require(sha256_file(manifest_path) == binding["manifest_sha256"], f"source manifest drift: {binding['source_id']}")
        _require(sha256_file(identity_path) == binding["identity_sha256"], f"source identity drift: {binding['source_id']}")
        identity = _read_json(identity_path)
        _require(identity.get("status") == "pass", f"source identity failed: {binding['source_id']}")
        manifest = _read_json(manifest_path)
        directory = manifest_path.parent
        for record in manifest["files"]:
            path = directory / str(record["path"])
            _require(path.is_file(), f"missing promoted source: {path}")
            _require(path.stat().st_size == int(record["bytes"]), f"source size drift: {path}")
            _require(sha256_file(path) == record["sha256"], f"source hash drift: {path}")


def _copy_base(root: Path, output: Path) -> tuple[list[str], Mapping[str, Any]]:
    staging = output.parent / f".{output.name}.base_v2"
    _require(not staging.exists(), f"base staging exists: {staging}")
    try:
        build_g59_frontend_bundle(root, staging)
        base_index = _read_json(staging / "index.json")
        relatives = list(BASE_FILES) + [row["path"] for row in base_index["prediction_chunks"]]
        for relative in relatives:
            destination = output / "base" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(staging / relative, destination)
        return [f"base/{relative}" for relative in relatives], base_index
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _humanize(identifier: str) -> str:
    words = identifier.replace("-", "_").split("_")
    acronyms = {"afqmc": "AFQMC", "ccsd": "CCSD", "ci": "CI", "dmrg": "DMRG", "fci": "FCI", "hf": "HF", "mp2": "MP2", "shci": "SHCI", "uhf": "UHF"}
    return " ".join(acronyms.get(word.lower(), word.capitalize()) for word in words)


def _public_name_mapping(catalog: Mapping[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    family_names = {
        "dmrg": "DMRG bond-dimension ladder",
        "ipie_afqmc": "phaseless AFQMC trial-state calculation",
        "shci": "SHCI threshold ladder",
        "trimci": "selected-CI determinant ladder",
    }
    for internal, public in sorted(family_names.items()):
        entries.append({"identifier_kind": "solver_family", "internal_identifier": internal, "public_description": public, "public_name": public})
    for row in catalog["solver_variants"]:
        family = str(row["solver_family_id"])
        value = row.get("resource_value")
        if family == "dmrg":
            public = f"DMRG bond dimension {int(value)}"
        elif family == "ipie_afqmc":
            public = "phaseless AFQMC with UHF trial state"
        elif family == "shci" and value is not None:
            public = f"SHCI variational threshold {float(value):.0e}"
        elif family == "shci":
            public = "SHCI terminal perturbative correction"
        elif family == "trimci" and value is not None:
            public = f"selected-CI target {int(value):,} determinants"
        else:
            public = "selected-CI default schedule"
        entries.append({"aliases": [str(row["solver_uuid"])], "identifier_kind": "solver_variant", "internal_identifier": str(row["solver_variant_id"]), "public_description": public, "public_name": public})
    for row in catalog["canonical_families"]:
        identifier = str(row["canonical_family"])
        entries.append({"identifier_kind": "task_family", "internal_identifier": identifier, "public_description": f"Canonical task family: {_humanize(identifier)}", "public_name": _humanize(identifier)})
    methods = {"pyscf_hf": "Hartree--Fock", "pyscf_mp2": "second-order Moller--Plesset", "pyscf_ccsd": "coupled cluster with singles and doubles", "pyscf_ccsd_t": "coupled cluster with perturbative triples", "pyscf_cisd": "configuration interaction with singles and doubles"}
    for internal, public in sorted(methods.items()):
        entries.append({"identifier_kind": "electronic_structure_method", "internal_identifier": internal, "public_description": public, "public_name": public})
    campaigns = {
        "g50": "solver-family ladder campaign",
        "g59": "panel completion campaign",
        "ml9a": "instance-space analysis",
        "ml9b": "censored resource profiles",
        "ml9c": "task-difficulty instrument",
        "ml9d": "grouped feature inference",
        "ml10a": "electronic-structure footprint extension",
        "ml10b": "electronic-structure resource extension",
        "ml10d": "electronic-structure label census",
    }
    for internal, public in sorted(campaigns.items()):
        entries.append({"identifier_kind": "campaign", "internal_identifier": internal, "public_description": public, "public_name": public})
    entries.sort(key=lambda row: (row["identifier_kind"], row["internal_identifier"]))
    return {
        "artifact_id": f"{ARTIFACT_ID}_public_name_mapping",
        "fallback_public_name": "Unmapped internal identifier",
        "internal_identifiers_are_displayable": False,
        "mapping": entries,
        "status": "normative_translation_boundary",
    }


def _definitions(preregistration: Mapping[str, Any]) -> dict[str, Any]:
    layers = {
        "base": "Observed and estimated solver-family records carried forward from bundle v2.",
        "instance_space": "Frozen coordinates and descriptive footprint geometry; failed adequacy gates remain attached.",
        "difficulty": "Frozen task posterior estimates and accepted corroboration metadata.",
        "resource_profiles": "Observed endpoint classes plus descriptive censored profiles and conditional quantiles.",
        "group_inference": "Grouped descriptive inference with multiplicity-adjusted honest-negative results.",
        "pyscf": "Observed electronic-structure labels, explicit missingness classes, and descriptive frontiers.",
    }
    return {
        "artifact_id": f"{ARTIFACT_ID}_definitions",
        "contract_requirement": "P-7",
        "definitions_are_normative": True,
        "derivation_contract": "contract/CONTRACT.md",
        "difficulty_corroboration": {
            "expanded_item_scale_pearson_concordance": 0.983,
            "one_factor_cross_validation_passes": 5,
            "one_factor_cross_validation_total": 5,
            "second_axis_hypotheses_supported": False,
            "single_reference_hypothesis_supported": False,
            "ipie_afqmc_hypothesis_supported": False,
            "two_factor_identifiable": False,
            "output_kind": "accepted_display_metadata"
        },
        "endpoint_taxonomy": {
            "competing_risk_crash_or_failure": "attempt ended in a distinct failure risk and is not pooled with walltime censoring",
            "cost_screened": "method was deliberately not attempted under the accepted cost screen",
            "ladder_exhaustion": "all accepted ladder rungs were exhausted without solution",
            "no_coverage": "no accepted campaign coverage exists",
            "solution": "accepted endpoint satisfied the stored task threshold",
            "walltime": "right-censored by walltime"
        },
        "estimate_labels": {
            "descriptive": "descriptive estimate; not a population ratio unless explicitly marked design-based",
            "external_validation": "external-validation estimate; failed gates are findings, not missing results",
            "frozen_posterior": "frozen posterior estimate; do not refit at export",
            "observed": "observed accepted record",
            "prediction": "estimated solvability; not a validated predictor"
        },
        "layers": {
            name: {
                "bundle_materialization": "derivable_at_export",
                "definition": definition,
                "source_state": "frozen_artifact"
            }
            for name, definition in layers.items()
        },
        "metric_distinction": preregistration["metric_disclosure"],
        "release": {
            "public_deployment_authorized": False,
            "validated_predictor_claim": False
        },
        "state_vocabulary": {
            "bundle_materialization": ["derivable_at_export"],
            "source_state": ["frozen_artifact"]
        }
    }


def _difficulty_availability(preregistration: Mapping[str, Any]) -> dict[str, Any]:
    decision = preregistration["no_gate_decisions"]["per_variant_ability_consistency"]
    return {
        "artifact_id": f"{ARTIFACT_ID}_variant_ability_consistency",
        "availability": decision["status"],
        "bundle_materialization": "derivable_at_export",
        "columns": ["solver_variant_id", "binary_ability_mean", "binary_ability_hdi_2_5pct", "binary_ability_hdi_97_5pct", "consistency_mean", "consistency_hdi_2_5pct", "consistency_hdi_97_5pct"],
        "encoding": "row_array_table_v1",
        "estimate_label": "not available from promoted scope",
        "layer": "difficulty",
        "primary_key": ["solver_variant_id"],
        "reason": decision["reason"],
        "rows": [],
        "source_state": "frozen_artifact",
        "table_name": "variant_ability_consistency"
    }


def _readme() -> str:
    return """# Hardness-instrument frontend bundle v3

Load `index.json` first and treat `definitions.json` as normative. The six
layers expose accepted observations, estimates, frozen instance-space
placement, task difficulty, censored resource records, grouped inference, and
electronic-structure method coverage. `public_name_mapping.json` is the only
UI naming boundary; machine identifiers must not be rendered.

This archive is internal. It makes no validated-predictor claim and does not
authorize a public deployment. Feature-adequacy and external-validation
failures are included as findings alongside the affected footprint geometry.
"""


def build_ml11_frontend_bundle(repository_root: Path, output_directory: Path) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    output_directory = output_directory.resolve()
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    preregistration = _read_json(repository_root / PREREGISTRATION)
    _require(preregistration.get("status") == "frozen_before_export", "protocol is not frozen")
    _verify_sources(repository_root, preregistration)
    output_directory.mkdir(parents=True)

    base_paths, base_index = _copy_base(repository_root, output_directory)
    layer_paths: dict[str, list[str]] = {name: [] for name in ("base", "instance_space", "difficulty", "resource_profiles", "group_inference", "pyscf")}
    layer_paths["base"].extend(base_paths)

    row_counts: dict[str, int] = {}
    for spec in TABLE_SPECS:
        payload = _table_payload(repository_root, spec)
        relative = f"layers/{spec.layer}/{spec.name}.json"
        _write_json(output_directory / relative, payload)
        layer_paths[spec.layer].append(relative)
        row_counts[f"{spec.layer}.{spec.name}"] = len(payload["rows"])

    for layer, name, source_id, source_relative, estimate_label in JSON_SPECS:
        source = repository_root / source_relative
        relative = f"layers/{layer}/{name}.json"
        _write_json(output_directory / relative, {
            "artifact_id": f"{ARTIFACT_ID}_{name}",
            "bundle_materialization": "derivable_at_export",
            "data": _read_json(source),
            "estimate_label": estimate_label,
            "layer": layer,
            "source_id": source_id,
            "source_path": source_relative,
            "source_sha256": sha256_file(source),
            "source_state": "frozen_artifact"
        })
        layer_paths[layer].append(relative)

    unavailable = _difficulty_availability(preregistration)
    unavailable_path = "layers/difficulty/variant_ability_consistency.json"
    _write_json(output_directory / unavailable_path, unavailable)
    layer_paths["difficulty"].append(unavailable_path)
    row_counts["difficulty.variant_ability_consistency"] = 0

    definitions_path = "definitions.json"
    mapping_path = "public_name_mapping.json"
    contract_path = "contract/CONTRACT.md"
    schema_path = "schema/index.schema.json"
    _write_json(output_directory / definitions_path, _definitions(preregistration), pretty=True)
    catalog = _read_json(output_directory / "base/catalog.json")
    _write_json(output_directory / mapping_path, _public_name_mapping(catalog), pretty=True)
    (output_directory / contract_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repository_root / CONTRACT, output_directory / contract_path)
    (output_directory / schema_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(repository_root / INDEX_SCHEMA, output_directory / schema_path)
    (output_directory / "README.md").write_text(_readme(), encoding="utf-8")

    supporting = ["README.md", definitions_path, mapping_path, contract_path, schema_path]
    files = []
    for relative in sorted(path for values in layer_paths.values() for path in values):
        row_count = row_counts.get(relative.replace("layers/", "").removesuffix(".json").replace("/", "."))
        files.append(_file_record(output_directory, relative, role="frontend_layer", row_count=row_count))
    for relative in supporting:
        role = "normative_definitions" if relative == definitions_path else "contract" if relative == contract_path else "public_name_mapping" if relative == mapping_path else "schema" if relative == schema_path else "documentation"
        files.append(_file_record(output_directory, relative, role=role))
    files.sort(key=lambda row: row["path"])

    layer_labels = {
        "base": "observations and estimates are labeled per carried-forward table",
        "instance_space": "descriptive geometry estimate with explicit adequacy gates",
        "difficulty": "frozen posterior estimate",
        "resource_profiles": "observed endpoints and descriptive conditional summaries",
        "group_inference": "multiplicity-adjusted descriptive inference estimate",
        "pyscf": "observed labels and descriptive coverage estimates",
    }
    index = {
        "$schema": schema_path,
        "artifact_id": ARTIFACT_ID,
        "counts": {
            "base_observations": base_index["counts"]["observations"],
            "base_prediction_rows": base_index["counts"]["predictions"],
            "corpus_tasks": 718,
            "difficulty_tasks": row_counts["difficulty.task_difficulty"],
            "g50_retained_dmrg_terminal_cells": 66,
            "group_multiplicity_rows": row_counts["group_inference.multiplicity_results"],
            "panel_tasks": 96,
            "projection_features": row_counts["instance_space.projection_features"],
            "pyscf_label_rows": row_counts["pyscf.labels"],
            "solver_variants": 18,
            "table_rows": dict(sorted(row_counts.items()))
        },
        "entrypoints": {
            "contract": contract_path,
            "definitions": definitions_path,
            "public_name_mapping": mapping_path,
            "base_catalog": "base/catalog.json",
            "base_features": "base/features.json",
            "base_observations": "base/observations.json",
            "base_uncertainty": "base/uncertainty.json",
            "instance_coordinates": "layers/instance_space/coordinates.json",
            "task_difficulty": "layers/difficulty/task_difficulty.json",
            "resource_endpoints": "layers/resource_profiles/combined_endpoints.json",
            "group_multiplicity": "layers/group_inference/multiplicity_results.json",
            "pyscf_labels": "layers/pyscf/labels.json"
        },
        "files": files,
        "layers": {
            name: {
                "bundle_materialization": "derivable_at_export",
                "estimate_label": layer_labels[name],
                "paths": sorted(paths),
                "source_state": "frozen_artifact"
            }
            for name, paths in layer_paths.items()
        },
        "release_scope": {
            "intended_use": "internal clone-and-extend frontend",
            "public_deployment_authorized": False,
            "validated_predictor_claim": False
        },
        "schema_version": SCHEMA_VERSION,
        "source_bindings": preregistration["source_bindings"],
        "status": "complete_internal_frozen_scale_bundle"
    }
    _write_json(output_directory / "index.json", index, pretty=True)
    return verify_ml11_frontend_bundle(output_directory)


def _verify_table(path: Path, expected_rows: int | None = None) -> list[dict[str, Any]]:
    payload = _read_json(path)
    _require(payload.get("encoding") == "row_array_table_v1", f"wrong table encoding: {path}")
    columns = payload["columns"]
    rows = payload["rows"]
    _require(all(len(row) == len(columns) for row in rows), f"row width: {path}")
    if expected_rows is not None:
        _require(len(rows) == expected_rows, f"row count: {path}")
    keys = payload["primary_key"]
    records = list(_table_records(payload))
    values = [tuple(row[column] for column in keys) for row in records]
    _require(len(values) == len(set(values)), f"duplicate key: {path}")
    return records


def _forbidden_term() -> bytes:
    return ("lega" + "cy").encode("ascii")


def verify_ml11_frontend_bundle(output_directory: Path) -> dict[str, Any]:
    output_directory = output_directory.resolve()
    index = _read_json(output_directory / "index.json")
    schema = _read_json(output_directory / index["$schema"])
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(index)
    _require(index["artifact_id"] == ARTIFACT_ID, "wrong artifact id")
    _require(index["schema_version"] == SCHEMA_VERSION, "wrong schema version")
    _require(index["release_scope"]["public_deployment_authorized"] is False, "public release drift")
    _require(index["release_scope"]["validated_predictor_claim"] is False, "predictor claim drift")

    expected_files = {"index.json"}
    forbidden = _forbidden_term()
    for record in index["files"]:
        relative = str(record["path"])
        path = output_directory / relative
        _require(path.resolve().is_relative_to(output_directory), f"unsafe path: {relative}")
        _require(path.is_file(), f"missing file: {relative}")
        _require(path.stat().st_size == int(record["bytes"]), f"size drift: {relative}")
        _require(sha256_file(path) == record["sha256"], f"hash drift: {relative}")
        _require(forbidden not in path.read_bytes().lower(), f"retired vocabulary: {relative}")
        expected_files.add(relative)
    _require(forbidden not in (output_directory / "index.json").read_bytes().lower(), "retired vocabulary: index")
    actual_files = {str(path.relative_to(output_directory)) for path in output_directory.rglob("*") if path.is_file()}
    _require(actual_files == expected_files, "unmanifested bundle files")

    for layer in index["layers"].values():
        _require(layer["source_state"] == "frozen_artifact", "layer source state")
        _require(layer["bundle_materialization"] == "derivable_at_export", "layer materialization")
        _require(bool(layer["estimate_label"]), "missing estimate label")

    catalog = _read_json(output_directory / "base/catalog.json")
    _require(len(catalog["tasks"]) == 718, "base task census")
    _require(len(catalog["solver_variants"]) == 18, "variant census")
    observations = _verify_table(output_directory / "base/observations.json", 1728)
    _require({row["observed_outcome"] for row in observations} == {"fail", "success"}, "observation outcomes")
    prediction_rows = sum(len(_read_json(output_directory / row["path"])["rows"]) for row in index["files"] if row["path"].startswith("base/predictions/") and row["path"].endswith(".json"))
    _require(prediction_rows == 25848, "prediction census")
    terminal = _verify_table(output_directory / "base/dmrg_terminal_cells.json", 96)
    _require(sum(row["source_cohort"] == "g50_retained_terminal_intake" for row in terminal) == 66, "retained DMRG count")

    coordinates = _verify_table(output_directory / "layers/instance_space/coordinates.json", 718)
    _require(len({row["task_uuid"] for row in coordinates}) == 718, "coordinate coverage")
    _verify_table(output_directory / "layers/instance_space/projection_features.json", 8)
    _verify_table(output_directory / "layers/instance_space/projection_matrix.json", 16)
    panel_gates = _verify_table(output_directory / "layers/instance_space/pyscf_panel_pythia_gates.json", 6)
    external = _verify_table(output_directory / "layers/instance_space/pyscf_external_validation.json", 5)
    _require(sum(bool(row["gate_passed"]) for row in panel_gates) == 2, "panel gate result")
    _require(sum(bool(row["gate_passed"]) for row in external) == 0, "external gate result")

    _verify_table(output_directory / "layers/difficulty/task_difficulty.json", 96)
    availability = _read_json(output_directory / "layers/difficulty/variant_ability_consistency.json")
    _require(availability["availability"] == "unavailable_from_promoted_scope", "difficulty availability")
    _require(availability["rows"] == [], "unpromoted variant estimates included")

    endpoints = _verify_table(output_directory / "layers/resource_profiles/combined_endpoints.json", 2592)
    endpoint_classes = {str(row["event_type"]) for row in endpoints}
    required_classes = {"solution", "right_censored_ladder_exhaustion", "right_censored_walltime", "competing_risk_crash", "competing_risk_failure", "not_attempted_cost_screened"}
    _require(required_classes <= endpoint_classes, "endpoint taxonomy incomplete")

    multiplicity = _verify_table(output_directory / "layers/group_inference/multiplicity_results.json", 25)
    _require(sum(bool(row["reject_zero_positive_importance"]) for row in multiplicity) == 0, "BH result drift")
    labels = _verify_table(output_directory / "layers/pyscf/labels.json", 3590)
    _require(sum(bool(row["in_gao_extension"]) for row in labels) == 635, "Gao cell census")
    _require({str(row["coverage_class"]) for row in labels} >= {"labeled", "not_attempted_cost_screened"}, "coverage taxonomy")

    definitions = _read_json(output_directory / "definitions.json")
    _require(definitions["definitions_are_normative"] is True, "definitions not normative")
    _require(definitions["metric_distinction"]["binding_selection_columns"] == 191, "191-column disclosure")
    _require(definitions["metric_distinction"]["frontend_feature_columns"] == 193, "193-column disclosure")
    mapping = _read_json(output_directory / "public_name_mapping.json")
    _require(mapping["internal_identifiers_are_displayable"] is False, "name mapping display fence")
    _require(len(mapping["mapping"]) >= 70, "public-name mapping coverage")
    return {
        "artifact_id": ARTIFACT_ID,
        "bundle_bytes": sum(path.stat().st_size for path in output_directory.rglob("*") if path.is_file()),
        "files_verified": len(actual_files),
        "index_sha256": sha256_file(output_directory / "index.json"),
        "status": "pass"
    }


def verify_ml11_archive(bundle_directory: Path, archive_path: Path) -> dict[str, Any]:
    bundle_directory = bundle_directory.resolve()
    archive_path = archive_path.resolve()
    expected = {f"{bundle_directory.name}/{path.relative_to(bundle_directory).as_posix()}": path for path in bundle_directory.rglob("*") if path.is_file()}
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        _require(names == sorted(expected), "archive member ordering or census")
        for info in archive.infolist():
            _require(info.date_time == (1980, 1, 1, 0, 0, 0), "archive timestamp drift")
            _require(archive.read(info.filename) == expected[info.filename].read_bytes(), f"archive byte drift: {info.filename}")
    return {"archive_sha256": sha256_file(archive_path), "members_verified": len(expected), "status": "pass"}


def build_ml11_frontend_run(repository_root: Path, run_directory: Path) -> dict[str, Any]:
    run_directory = run_directory.resolve()
    _require(not run_directory.exists(), f"run exists: {run_directory}")
    run_directory.mkdir(parents=True)
    bundle = run_directory / BUNDLE_NAME
    archive = run_directory / f"{BUNDLE_NAME}.zip"
    report = build_ml11_frontend_bundle(repository_root, bundle)
    write_deterministic_zip(bundle, archive)
    archive_report = verify_ml11_archive(bundle, archive)
    files = []
    for path in sorted(item for item in run_directory.rglob("*") if item.is_file()):
        relative = path.relative_to(run_directory).as_posix()
        files.append({"bytes": path.stat().st_size, "path": relative, "sha256": sha256_file(path)})
    manifest = {
        "artifact_id": "ml11_frontend_bundle_v3_run_manifest_v1",
        "archive_sha256": archive_report["archive_sha256"],
        "bundle_index_sha256": report["index_sha256"],
        "files": files,
        "status": "complete_internal_deterministic_export"
    }
    _write_json(run_directory / "artifact_manifest.json", manifest, pretty=True)
    return {**report, "archive": archive_report, "run_manifest_sha256": sha256_file(run_directory / "artifact_manifest.json")}


def _tree_hashes(directory: Path) -> dict[str, str]:
    return {path.relative_to(directory).as_posix(): sha256_file(path) for path in sorted(item for item in directory.rglob("*") if item.is_file())}


def finalize_ml11_frontend_runs(run_1: Path, run_2: Path, final_directory: Path, identity_path: Path) -> dict[str, Any]:
    run_1, run_2, final_directory, identity_path = map(Path.resolve, (run_1, run_2, final_directory, identity_path))
    _require(not final_directory.exists(), f"final exists: {final_directory}")
    first = _tree_hashes(run_1)
    second = _tree_hashes(run_2)
    _require(first == second, "two export runs differ")
    identity = {
        "artifact_id": "ml11_frontend_bundle_v3_two_run_identity_v1",
        "byte_identical": True,
        "file_count": len(first),
        "file_hashes": first,
        "raw_trees_retained": True,
        "relative_paths": sorted(first),
        "status": "pass"
    }
    _write_json(identity_path, identity, pretty=True)
    shutil.copytree(run_1, final_directory)
    _require(_tree_hashes(final_directory) == first, "promoted tree differs from raw run 1")
    return {"file_count": len(first), "identity_sha256": sha256_file(identity_path), "promoted_tree_identical": True, "status": "pass"}
