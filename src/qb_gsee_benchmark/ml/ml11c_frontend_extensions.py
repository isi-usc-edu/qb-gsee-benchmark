"""Deterministic ML-11c per-rung geometry and combined frontend addendum."""

from __future__ import annotations

import json
import shutil
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.core_set import _require, sha256_file
from qb_gsee_benchmark.ml.g50_frontend_bundle import (
    _file_record,
    _json_scalar,
    _write_json,
    write_deterministic_zip,
)
from qb_gsee_benchmark.ml.instance_space_run import (
    _footprint_metrics,
    _geometry_payload,
)
from qb_gsee_benchmark.ml.ml11_frontend_bundle import (
    verify_ml11_archive,
    verify_ml11_frontend_bundle,
)
from qb_gsee_benchmark.ml.ml11b_variant_ability import (
    _manifest_directory,
    _verify_manifest,
    finalize_identical_runs,
    verify_scoped_variant_ability,
)
from qb_gsee_benchmark.ml.pyscf_instance_space_run import _single_trace

ARTIFACT_ID = "ml11c_frontend_combined_addendum_v3_1"
ANALYSIS_DIRECTORY = Path("analysis/ml11c_frontend_extensions")
PREREGISTRATION = ANALYSIS_DIRECTORY / "preregistration.json"
SCHEMA = ANALYSIS_DIRECTORY / "combined_addendum_v3_1.schema.json"
BASE_BUNDLE = Path("analysis/ml11_frontend_bundle/final_v1/frontend_bundle_v3")
ML11B_PROMOTION = Path("analysis/ml11b_variant_ability/final_v1")
ML11B_IDENTITY = Path("analysis/ml11b_variant_ability/two_run_identity_promotion_v1.json")

PER_RUNG_COLUMNS = (
    "solver_family_id",
    "profile_track_id",
    "threshold_factor",
    "resource_axis_name",
    "resource_units",
    "resource_rank",
    "resource_value",
    "effort_multiplier",
    "panel_tasks",
    "solved_tasks_cumulative",
    "footprint_kind",
    "area",
    "area_normalized",
    "density",
    "density_normalized",
    "purity",
    "elements",
    "good_elements",
    "geometry_status",
    "projection_refit",
    "output_kind",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_term() -> bytes:
    return ("lega" + "cy").encode("ascii")


def _verify_identity(path: Path, expected_sha256: str) -> Mapping[str, Any]:
    _require(sha256_file(path) == expected_sha256, f"identity drift: {path}")
    identity = _read_json(path)
    _require(identity.get("byte_identical") is True, f"identity mismatch: {path}")
    _require(str(identity.get("status", "")).startswith("pass"), f"identity failed: {path}")
    return identity


def _verify_sources(root: Path, protocol: Mapping[str, Any]) -> None:
    source = protocol["sources"]
    resource = root / "analysis/ml9_resource_profiles/final_v1"
    instance = root / "analysis/ml9_instance_space/final_v1"
    _verify_manifest(resource, source["resource_manifest_sha256"])
    _verify_identity(
        root / "analysis/ml9_resource_profiles/two_run_identity_v1.json",
        source["resource_identity_sha256"],
    )
    _verify_manifest(instance, source["instance_space_manifest_sha256"])
    _verify_identity(
        root / "analysis/ml9_instance_space/two_run_identity_v1.json",
        source["instance_space_identity_sha256"],
    )
    _require(sha256_file(resource / "resource_to_solution.csv") == source["resource_to_solution_sha256"], "resource endpoint drift")
    _require(sha256_file(resource / "data_profiles.csv") == source["resource_profiles_sha256"], "resource profile drift")
    _require(sha256_file(instance / "panel_coordinates.csv") == source["panel_coordinates_sha256"], "panel coordinate drift")
    _require(sha256_file(root / "analysis/ml9_instance_space/preregistration.json") == source["instance_space_preregistration_sha256"], "instance-space protocol drift")

    promotion = root / ML11B_PROMOTION
    promotion_report = verify_scoped_variant_ability(promotion)
    _require(promotion_report["manifest_sha256"] == source["ml11b_promotion_manifest_sha256"], "ML-11b promotion drift")
    _verify_identity(root / ML11B_IDENTITY, source["ml11b_promotion_identity_sha256"])
    base = root / BASE_BUNDLE
    verify_ml11_frontend_bundle(base)
    _require(sha256_file(base / "contract/CONTRACT.md") == source["base_contract_sha256"], "base contract drift")
    _require(sha256_file(base / "public_name_mapping.json") == source["base_public_name_mapping_sha256"], "base mapping drift")


def _close_ring(ring: Iterable[Iterable[float]]) -> list[list[float]]:
    points = [[float(value) for value in point] for point in ring]
    _require(bool(points), "empty non-null geometry ring")
    if points[0] != points[-1]:
        points.append(list(points[0]))
    return points


def _normalize_geometry(geometry: Mapping[str, Any] | None) -> tuple[str, Mapping[str, Any] | None]:
    if geometry is None:
        return "empty", None
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates", [])
    if kind == "Polygon":
        polygons = [coordinates]
    elif kind == "MultiPolygon":
        polygons = coordinates
    else:
        raise ValueError(f"unsupported geometry type: {kind}")
    if not polygons:
        return "empty", None
    normalized = []
    for polygon in polygons:
        rings = [_close_ring(ring) for ring in polygon]
        _require(bool(rings), "polygon without rings")
        normalized.append(rings)
    return "estimated", {"coordinates": normalized, "type": "MultiPolygon"}


def _geometry_registry(payload: Any, source_path: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    def visit(value: Any, pointer: str, geometry_context: bool = False) -> None:
        if isinstance(value, dict) and value.get("type") in {"Polygon", "MultiPolygon"}:
            status, geometry = _normalize_geometry(value)
            entries.append({"geometry": geometry, "geometry_pointer": pointer, "geometry_status": status, "source_path": source_path})
            return
        if value is None and geometry_context:
            entries.append({"geometry": None, "geometry_pointer": pointer, "geometry_status": "empty", "source_path": source_path})
            return
        if isinstance(value, dict):
            for key in sorted(value):
                child_context = geometry_context or key in {"best", "empirical_space", "good"}
                visit(value[key], f"{pointer}/{key}", child_context)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{pointer}/{index}", geometry_context)

    visit(payload, "")
    entries.sort(key=lambda row: (row["source_path"], row["geometry_pointer"]))
    return entries


def _per_rung_geometry(root: Path, protocol: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    resource = root / "analysis/ml9_resource_profiles/final_v1"
    instance = root / "analysis/ml9_instance_space/final_v1"
    coordinates = pd.read_csv(instance / "panel_coordinates.csv").sort_values("task_uuid").reset_index(drop=True)
    _require(len(coordinates) == 96 and coordinates["task_uuid"].is_unique, "panel coordinate census")
    endpoints = pd.read_csv(resource / "resource_to_solution.csv", low_memory=False)
    profiles = pd.read_csv(resource / "data_profiles.csv")
    threshold = float(protocol["geometry"]["threshold_factor"])
    endpoints = endpoints.loc[endpoints["threshold_factor"].eq(threshold)].copy()
    profiles = profiles.loc[profiles["threshold_factor"].eq(threshold)].copy()
    _require(len(profiles) == protocol["geometry"]["expected_objects"], "rung census")
    observed = dict(profiles.groupby("profile_track_id").size())
    _require(observed == protocol["geometry"]["profile_rungs"], "profile rung census")

    metrics_rows: list[dict[str, Any]] = []
    polygon_rows: list[dict[str, Any]] = []
    z = coordinates[["z1", "z2"]].to_numpy(dtype=float)
    task_order = list(coordinates["task_uuid"].astype(str))
    for rung in profiles.sort_values(["solver_family_id", "profile_track_id", "resource_rank"]).to_dict(orient="records"):
        track = str(rung["profile_track_id"])
        rank = int(rung["resource_rank"])
        track_endpoints = endpoints.loc[endpoints["profile_track_id"].eq(track)].set_index("task_uuid")
        _require(set(track_endpoints.index.astype(str)) == set(task_order), f"endpoint coverage: {track}")
        track_endpoints.index = track_endpoints.index.astype(str)
        track_endpoints = track_endpoints.loc[task_order]
        solved = track_endpoints["solution_observed"].astype(bool) & track_endpoints["endpoint_resource_rank"].le(rank)
        solved_count = int(solved.sum())
        if solved_count == 0:
            metrics = {"area": 0.0, "area_normalized": 0.0, "density": 0.0, "density_normalized": 0.0, "purity": 0.0, "elements": 0, "good_elements": 0}
            geometry_status, geometry = "empty", None
        else:
            trace = _single_trace(z, solved.to_numpy(dtype=bool))
            footprint = trace.good[0]
            metrics = _footprint_metrics(footprint, trace.space)
            raw_geometry = _geometry_payload(footprint)
            normalized_status, geometry = _normalize_geometry(raw_geometry)
            geometry_status = normalized_status if geometry is not None else "degenerate"
        common = {
            "solver_family_id": str(rung["solver_family_id"]),
            "profile_track_id": track,
            "threshold_factor": threshold,
            "resource_axis_name": str(rung["resource_axis_name"]),
            "resource_units": str(rung["resource_units"]),
            "resource_rank": rank,
            "resource_value": _json_scalar(rung["resource_value"]),
            "effort_multiplier": _json_scalar(rung["effort_multiplier"]),
        }
        metrics_rows.append({
            **common,
            "panel_tasks": 96,
            "solved_tasks_cumulative": solved_count,
            "footprint_kind": "good",
            **metrics,
            "geometry_status": geometry_status,
            "projection_refit": False,
            "output_kind": "descriptive_geometry_estimate",
        })
        polygon_rows.append({**common, "geometry": geometry, "geometry_status": geometry_status})

    metrics_payload = {
        "artifact_id": "ml11c_per_rung_footprints_v1",
        "bundle_materialization": "derivable_at_export",
        "columns": list(PER_RUNG_COLUMNS),
        "encoding": "row_array_table_v1",
        "estimate_label": "descriptive geometry on frozen projection and observed cumulative rung labels",
        "layer": "instance_space",
        "primary_key": ["profile_track_id", "resource_rank"],
        "rows": [[row[column] for column in PER_RUNG_COLUMNS] for row in metrics_rows],
        "source_state": "frozen_artifact",
        "table_name": "per_rung_footprints",
    }
    polygons_payload = {
        "artifact_id": "ml11c_per_rung_polygons_v1",
        "bundle_materialization": "derivable_at_export",
        "estimate_label": "normalized descriptive geometry",
        "geometry_contract": {"nonempty_type": "MultiPolygon", "rings_closed": True},
        "layer": "instance_space",
        "rows": polygon_rows,
        "source_state": "frozen_artifact",
    }
    return metrics_payload, polygons_payload


def _mapping_entries() -> list[dict[str, Any]]:
    values: dict[str, dict[str, str]] = {
        "endpoint_class": {
            "solution": "Solution",
            "right_censored_ladder_exhaustion": "Ladder exhausted",
            "right_censored_walltime": "Wall-time limit",
            "competing_risk_crash": "Competing-risk crash",
            "competing_risk_failure": "Competing-risk failure",
            "not_attempted_cost_screened": "Not attempted after cost screen",
            "no_attempt_evidence": "No attempt evidence",
            "no_coverage": "No accepted coverage",
        },
        "coverage_class": {
            "labeled": "Accepted labeled result",
            "failed": "Attempted without accepted result",
            "not_attempted_cost_screened": "Not attempted after cost screen",
            "no_coverage": "No accepted coverage",
        },
        "coverage_role": {
            "labeled_panel": "Labeled panel task",
            "prediction_target_or_coverage": "Projection-only coverage task",
            "unlabeled_gradeable": "Unlabeled gradeable task",
        },
        "state_value": {
            "ok": "Completed with finite result",
            "accuracy_miss": "Completed outside target accuracy",
            "crash": "Execution failure",
            "timeout": "Wall-time limit reached",
            "success": "Observed success",
            "fail": "Observed bounded-run failure",
            "estimated": "Estimated geometry",
            "degenerate": "Degenerate geometry",
            "empty": "Empty geometry",
        },
        "gate_reason": {
            "pass": "Feature-adequacy gate passed",
            "feature_adequacy_gate_failed": "Feature-adequacy gate failed; display geometry with caveat",
        },
        "validation_reason": {
            "raw >= max(0.70, majority + 0.05) and balanced >= 0.60": "External validation requires raw accuracy above both 0.70 and the majority baseline by 0.05, with balanced accuracy at least 0.60",
        },
        "portfolio_object": {
            "portfolio_union": "Four-family ladder portfolio",
            "18_item_ladder_union": "Eighteen-item ladder union",
            "five_method_pyscf_union": "Five-method electronic-structure union",
            "ladder_plus_pyscf_union": "Combined ladder and electronic-structure union",
            "ladder_plus_pyscf_portfolio": "Combined ladder and electronic-structure portfolio",
            "pyscf_five_method_union": "Five-method electronic-structure union",
        },
    }
    entries = []
    for kind, mapping in values.items():
        for internal, public in mapping.items():
            entries.append({
                "identifier_kind": kind,
                "internal_identifier": internal,
                "public_description": public,
                "public_name": public,
            })
    return sorted(entries, key=lambda row: (row["identifier_kind"], row["internal_identifier"]))


def _extended_mapping(
    base: Mapping[str, Any],
    required_identifiers: Iterable[tuple[str, str]] = (),
) -> Mapping[str, Any]:
    entries = list(base["mapping"])
    keys = {(row["identifier_kind"], row["internal_identifier"]) for row in entries}
    additions = _mapping_entries()
    for row in additions:
        key = (row["identifier_kind"], row["internal_identifier"])
        _require(key not in keys, f"mapping collision: {key}")
        entries.append(row)
        keys.add(key)
    for kind, internal_identifier in sorted(set(required_identifiers)):
        key = (kind, internal_identifier)
        if key in keys:
            continue
        entries.append({
            "identifier_kind": kind,
            "internal_identifier": internal_identifier,
            "public_description": None,
            "public_name": None,
        })
        keys.add(key)
        warnings.warn(
            f"names.json stub requires public copy: {kind}/{internal_identifier}",
            stacklevel=2,
        )
    entries.sort(key=lambda row: (row["identifier_kind"], row["internal_identifier"]))
    return {
        "artifact_id": "ml11c_public_name_mapping_v3_1",
        "fallback_public_name": "Unmapped internal identifier",
        "governance": {
            "build_warning_until_filled": True,
            "required_stub_fields": ["identifier_kind", "internal_identifier", "public_name", "public_description"],
            "stub_action": "append names.json row with null public fields",
            "ui_fallback": "Unmapped internal identifier",
        },
        "internal_identifiers_are_displayable": False,
        "mapping": entries,
        "status": "normative_translation_boundary",
    }


def _contract(base_text: str) -> str:
    return base_text.rstrip() + """

## Cloner names.json governance

The exporter maintains `names.json` as the normative identifier-to-paper-copy
table. On an unknown identifier it appends a deterministic stub containing the
identifier kind and machine identifier with null `public_name` and
`public_description`, then emits a build warning until both public fields are
filled. The UI never renders the machine identifier as fallback copy; it uses
`Unmapped internal identifier` while the warning remains active. Filled rows
are sorted by identifier kind and machine identifier before serialization.
"""


def _definitions(protocol: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "artifact_id": f"{ARTIFACT_ID}_definitions",
        "assertions": protocol["index_assertions"],
        "definitions_are_normative": True,
        "geometry": {
            "cumulative_label": "solution_observed and first-solution resource rank <= displayed resource rank",
            "nonempty_type": "MultiPolygon",
            "purity": protocol["geometry"]["purity"],
            "rings_closed": True,
            "threshold_factor": protocol["geometry"]["threshold_factor"],
        },
        "layers": {
            "difficulty": {"bundle_materialization": "derivable_at_export", "source_state": "frozen_artifact"},
            "instance_space": {"bundle_materialization": "derivable_at_export", "source_state": "frozen_artifact"},
        },
        "mapping_governance": protocol["mapping_extension"]["unknown_identifier_policy"],
        "release": {"public_deployment_authorized": False, "validated_predictor_claim": False},
    }


def _normalized_base_geometry(root: Path) -> list[dict[str, Any]]:
    base = root / BASE_BUNDLE
    paths = (
        "layers/instance_space/pyscf_corpus_polygons.json",
        "layers/instance_space/pyscf_panel_polygons.json",
        "layers/instance_space/solver_family_polygons.json",
    )
    entries: list[dict[str, Any]] = []
    for relative in paths:
        entries.extend(_geometry_registry(_read_json(base / relative), relative))
    entries.sort(key=lambda row: (row["source_path"], row["geometry_pointer"]))
    return entries


def build_combined_addendum(root: Path, output_directory: Path) -> Mapping[str, Any]:
    root, output_directory = root.resolve(), output_directory.resolve()
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    protocol = _read_json(root / PREREGISTRATION)
    _require(protocol["status"] == "frozen_before_geometry_derivation", "protocol not frozen")
    _verify_sources(root, protocol)
    metrics, polygons = _per_rung_geometry(root, protocol)
    normalized_base = _normalized_base_geometry(root)

    output_directory.mkdir(parents=True)
    ability_path = Path("layers/difficulty/variant_ability_consistency.json")
    ability_destination = output_directory / ability_path
    ability_destination.parent.mkdir(parents=True)
    shutil.copyfile(root / ML11B_PROMOTION / "variant_ability_consistency.json", ability_destination)
    metrics_path = Path("layers/instance_space/per_rung_footprints.json")
    polygons_path = Path("layers/instance_space/per_rung_polygons.json")
    registry_path = Path("layers/instance_space/normalized_base_geometry.json")
    _write_json(output_directory / metrics_path, metrics)
    _write_json(output_directory / polygons_path, polygons)
    _write_json(output_directory / registry_path, {
        "artifact_id": "ml11c_normalized_base_geometry_v1",
        "geometry_contract": {"nonempty_type": "MultiPolygon", "rings_closed": True},
        "rows": normalized_base,
    })

    base_mapping = _read_json(root / BASE_BUNDLE / "public_name_mapping.json")
    ability_records = _table_records(_read_json(ability_destination))
    footprint_records = _table_records(metrics)
    required_names = {
        ("solver_variant", str(row["solver_variant_id"]))
        for row in ability_records
    } | {
        ("solver_family", str(row["solver_family_id"]))
        for row in footprint_records
    }
    mapping = _extended_mapping(base_mapping, required_names)
    _write_json(output_directory / "public_name_mapping.json", mapping, pretty=True)
    _write_json(output_directory / "names.json", mapping, pretty=True)
    _write_json(output_directory / "definitions.json", _definitions(protocol), pretty=True)
    contract_destination = output_directory / "contract/CONTRACT.md"
    contract_destination.parent.mkdir(parents=True)
    contract_destination.write_text(
        _contract((root / BASE_BUNDLE / "contract/CONTRACT.md").read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    schema_destination = output_directory / "schema/index.schema.json"
    schema_destination.parent.mkdir(parents=True)
    shutil.copyfile(root / SCHEMA, schema_destination)
    (output_directory / "README.md").write_text(
        "# Combined frontend addendum v3.1\n\n"
        "Apply this internal additive recut to the unchanged accepted v3 bundle. "
        "It supplies solver ability, per-rung geometry, normalized geometry, "
        "expanded display names, assertion scalars, and naming governance.\n",
        encoding="utf-8",
    )

    file_specs = (
        ("README.md", "documentation", None),
        ("contract/CONTRACT.md", "contract", None),
        ("definitions.json", "normative_definitions", None),
        (ability_path.as_posix(), "frontend_layer", 18),
        (metrics_path.as_posix(), "frontend_layer", 16),
        (polygons_path.as_posix(), "frontend_geometry", 16),
        (registry_path.as_posix(), "frontend_geometry", len(normalized_base)),
        ("names.json", "names_governance", len(mapping["mapping"])),
        ("public_name_mapping.json", "public_name_mapping", len(mapping["mapping"])),
        ("schema/index.schema.json", "schema", None),
    )
    files = [_file_record(output_directory, path, role=role, row_count=rows) for path, role, rows in file_specs]
    files.sort(key=lambda row: row["path"])
    base_index = sha256_file(root / BASE_BUNDLE / "index.json")
    index = {
        "$schema": "schema/index.schema.json",
        "applies_to": {
            "base_artifact_id": "ml11_frontend_bundle_v3",
            "base_index_sha256": base_index,
            "prior_addendum_retained": True,
        },
        "artifact_id": ARTIFACT_ID,
        "assertions": protocol["index_assertions"],
        "entrypoints": {
            "contract": "contract/CONTRACT.md",
            "definitions": "definitions.json",
            "names": "names.json",
            "normalized_base_geometry": registry_path.as_posix(),
            "per_rung_footprints": metrics_path.as_posix(),
            "per_rung_polygons": polygons_path.as_posix(),
            "public_name_mapping": "public_name_mapping.json",
            "variant_ability_consistency": ability_path.as_posix(),
        },
        "files": files,
        "layers": {
            "difficulty": {"bundle_materialization": "derivable_at_export", "estimate_label": "frozen binary-Rasch posterior estimate", "row_count": 18, "source_state": "frozen_artifact"},
            "instance_space": {"bundle_materialization": "derivable_at_export", "estimate_label": "descriptive geometry on frozen projection", "row_count": 16, "source_state": "frozen_artifact"},
        },
        "release_scope": {"public_deployment_authorized": False, "validated_predictor_claim": False},
        "schema_version": "3.1.0",
        "source": {
            "instance_space_manifest_sha256": protocol["sources"]["instance_space_manifest_sha256"],
            "ml11b_promotion_manifest_sha256": protocol["sources"]["ml11b_promotion_manifest_sha256"],
            "resource_manifest_sha256": protocol["sources"]["resource_manifest_sha256"],
        },
        "status": "complete_internal_combined_addendum",
    }
    _write_json(output_directory / "index.json", index, pretty=True)
    return verify_combined_addendum(output_directory)


def _table_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(zip(payload["columns"], row)) for row in payload["rows"]]


def _verify_geometry_row(row: Mapping[str, Any]) -> None:
    geometry = row["geometry"]
    status = row["geometry_status"]
    if geometry is None:
        _require(status in {"empty", "degenerate"}, "null geometry status")
        return
    _require(status == "estimated", "nonempty geometry status")
    _require(geometry["type"] == "MultiPolygon", "geometry type")
    _require(bool(geometry["coordinates"]), "empty multipolygon")
    for polygon in geometry["coordinates"]:
        for ring in polygon:
            _require(ring[0] == ring[-1], "open geometry ring")


def verify_combined_addendum(directory: Path) -> Mapping[str, Any]:
    directory = directory.resolve()
    index = _read_json(directory / "index.json")
    schema = _read_json(directory / index["$schema"])
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(index)
    _require(index["artifact_id"] == ARTIFACT_ID, "wrong combined addendum")
    _require(index["assertions"] == {"gradeable_population": 609, "no_reference_population": 109}, "assertion drift")
    _require(index["release_scope"]["public_deployment_authorized"] is False, "release drift")
    _require(index["release_scope"]["validated_predictor_claim"] is False, "predictor claim drift")
    expected = {"index.json"}
    forbidden = _forbidden_term()
    for record in index["files"]:
        path = directory / record["path"]
        _require(path.is_file(), f"missing file: {path}")
        _require(path.stat().st_size == record["bytes"], f"size drift: {path}")
        _require(sha256_file(path) == record["sha256"], f"hash drift: {path}")
        _require(forbidden not in path.read_bytes().lower(), f"retired vocabulary: {path}")
        expected.add(record["path"])
    _require(forbidden not in (directory / "index.json").read_bytes().lower(), "retired vocabulary: index")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    _require(actual == expected, "unmanifested combined addendum files")

    ability = _read_json(directory / index["entrypoints"]["variant_ability_consistency"])
    _require(len(ability["rows"]) == 18, "ability row count")
    footprints = _table_records(_read_json(directory / index["entrypoints"]["per_rung_footprints"]))
    _require(len(footprints) == 16, "footprint rung count")
    _require(Counter(row["solver_family_id"] for row in footprints) == {"dmrg": 4, "ipie_afqmc": 1, "shci": 4, "trimci": 7}, "footprint family census")
    _require(all(row["threshold_factor"] == 1.0 for row in footprints), "footprint threshold")
    _require(all(row["projection_refit"] is False for row in footprints), "projection refit")
    polygons = _read_json(directory / index["entrypoints"]["per_rung_polygons"])["rows"]
    _require(len(polygons) == 16, "polygon rung count")
    for row in polygons:
        _verify_geometry_row(row)
    registry = _read_json(directory / index["entrypoints"]["normalized_base_geometry"])["rows"]
    for row in registry:
        _verify_geometry_row(row)
    corpus = [row for row in registry if row["source_path"].endswith("pyscf_corpus_polygons.json")]
    _require(len(corpus) == 10, "corpus geometry census")
    _require(all(row["geometry"] is None or row["geometry"]["type"] == "MultiPolygon" for row in corpus), "corpus geometry normalization")

    mapping = _read_json(directory / "names.json")
    categories = {row["identifier_kind"] for row in mapping["mapping"]}
    _require(set(("coverage_class", "coverage_role", "endpoint_class", "gate_reason", "portfolio_object", "state_value", "validation_reason")) <= categories, "mapping categories")
    _require(mapping["governance"]["build_warning_until_filled"] is True, "names warning rule")
    _require(all(row["public_name"] and row["public_description"] for row in mapping["mapping"]), "unfilled committed mapping")
    contract = (directory / "contract/CONTRACT.md").read_text(encoding="utf-8")
    _require("Cloner names.json governance" in contract and "build warning" in contract, "names governance contract")
    return {
        "files_verified": len(actual),
        "geometry_rows_verified": len(registry) + len(polygons),
        "index_sha256": sha256_file(directory / "index.json"),
        "mapping_entries_verified": len(mapping["mapping"]),
        "rungs_verified": len(footprints),
        "status": "pass",
    }


def build_combined_addendum_run(root: Path, run_directory: Path) -> Mapping[str, Any]:
    run_directory = run_directory.resolve()
    _require(not run_directory.exists(), f"run exists: {run_directory}")
    run_directory.mkdir(parents=True)
    bundle = run_directory / "frontend_combined_addendum_v3_1"
    archive = run_directory / "frontend_combined_addendum_v3_1.zip"
    report = build_combined_addendum(root, bundle)
    write_deterministic_zip(bundle, archive)
    archive_report = verify_ml11_archive(bundle, archive)
    _manifest_directory(run_directory, "ml11c_combined_addendum_run_manifest_v1", "complete_internal_deterministic_export")
    return {**report, "archive": archive_report, "run_manifest_sha256": sha256_file(run_directory / "artifact_manifest.json")}
