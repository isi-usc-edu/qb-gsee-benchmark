"""Scoped ML-11b variant-ability promotion and frontend v3.1 addendum."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.core_set import _require, sha256_file
from qb_gsee_benchmark.ml.g50_frontend_bundle import (
    _file_record,
    _write_json,
    write_deterministic_zip,
)
from qb_gsee_benchmark.ml.ml11_frontend_bundle import verify_ml11_archive

ARTIFACT_ID = "ml11b_variant_ability_posterior_v1"
ADDENDUM_ARTIFACT_ID = "ml11b_frontend_ability_addendum_v3_1"
ANALYSIS_DIRECTORY = Path("analysis/ml11b_variant_ability")
PREREGISTRATION = ANALYSIS_DIRECTORY / "preregistration.json"
ADDENDUM_SCHEMA = ANALYSIS_DIRECTORY / "frontend_addendum_v3_1.schema.json"
BASE_BUNDLE = Path("analysis/ml11_frontend_bundle/final_v1/frontend_bundle_v3")
BASE_IDENTITY = Path("analysis/ml11_frontend_bundle/two_run_identity_v1.json")
PROMOTION_IDENTITY = ANALYSIS_DIRECTORY / "two_run_identity_promotion_v1.json"

PROMOTED_COLUMNS = (
    "solver_family_id",
    "solver_variant_id",
    "solver_short_name",
    "model",
    "output_kind",
    "binary_ability_mean",
    "binary_ability_sd",
    "binary_ability_hdi_2_5pct",
    "binary_ability_hdi_97_5pct",
    "consistency_mean",
    "consistency_sd",
    "consistency_hdi_2_5pct",
    "consistency_hdi_97_5pct",
    "consistency_availability",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _forbidden_term() -> bytes:
    return ("lega" + "cy").encode("ascii")


def _verify_manifest(directory: Path, expected_sha256: str) -> Mapping[str, Any]:
    path = directory / "artifact_manifest.json"
    _require(sha256_file(path) == expected_sha256, f"source manifest drift: {directory}")
    manifest = _read_json(path)
    for record in manifest["files"]:
        source = directory / str(record["path"])
        _require(source.is_file(), f"missing source file: {source}")
        _require(source.stat().st_size == int(record["bytes"]), f"source size drift: {source}")
        _require(sha256_file(source) == record["sha256"], f"source hash drift: {source}")
    return manifest


def _source_rows(root: Path, source_directory: Path) -> tuple[list[dict[str, Any]], Mapping[str, Any]]:
    protocol = _read_json(root / PREREGISTRATION)
    _require(protocol["status"] == "frozen_before_extraction", "protocol is not frozen")
    sources = protocol["sources"]
    source_directory = source_directory.resolve()
    permitted = {
        (root / sources["run_1_path"]).resolve(): sources["run_1_manifest_sha256"],
        (root / sources["run_2_path"]).resolve(): sources["run_2_manifest_sha256"],
    }
    _require(source_directory in permitted, "source is outside the frozen retained pair")
    _verify_manifest(source_directory, permitted[source_directory])

    identity_path = root / sources["retained_identity_path"]
    _require(sha256_file(identity_path) == sources["retained_identity_sha256"], "retained identity drift")
    identity = _read_json(identity_path)
    _require(identity.get("byte_identical") is True, "retained source pair differs")
    _require(str(identity.get("status", "")).startswith("pass"), "retained identity failed")

    diagnostics = source_directory / "posterior_diagnostics.csv"
    _require(sha256_file(diagnostics) == sources["posterior_diagnostics_sha256"], "diagnostics drift")
    with diagnostics.open(newline="", encoding="utf-8") as handle:
        diagnostic_rows = list(csv.DictReader(handle))
    binary = [row for row in diagnostic_rows if row["model"] == "binary_rasch"]
    _require(len(binary) == 1, "binary diagnostic row census")
    row = binary[0]
    gate = protocol["diagnostic_gate"]
    _require(int(row["divergences"]) <= gate["divergences_max"], "binary divergences")
    _require(float(row["maximum_rhat"]) <= gate["maximum_rhat_max"], "binary R-hat")
    _require(float(row["minimum_bulk_ess"]) >= gate["minimum_bulk_ess_min"], "binary bulk ESS")
    _require(float(row["minimum_tail_ess"]) >= gate["minimum_tail_ess_min"], "binary tail ESS")
    _require(row["passed"].lower() == "true", "binary posterior diagnostic failed")

    source = source_directory / "variant_parameters.csv"
    _require(sha256_file(source) == sources["variant_parameters_sha256"], "variant table drift")
    with source.open(newline="", encoding="utf-8") as handle:
        retained = list(csv.DictReader(handle))
    allowed = protocol["authorized_fields"]
    projection = [{field: source_row[field] for field in allowed} for source_row in retained]
    canonical = (json.dumps(projection, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    _require(hashlib.sha256(canonical).hexdigest() == protocol["binary_projection"]["canonical_json_sha256_across_all_six_retained_runs"], "binary projection drift")
    _require(len(projection) == protocol["binary_projection"]["expected_rows"], "variant row census")

    rows = []
    for retained_row in retained:
        rows.append({
            "solver_family_id": retained_row["solver_family_id"],
            "solver_variant_id": retained_row["solver_variant_id"],
            "solver_short_name": retained_row["solver_short_name"],
            "model": protocol["binary_projection"]["model"],
            "output_kind": "frozen_posterior_estimate",
            "binary_ability_mean": float(retained_row["binary_ability_mean"]),
            "binary_ability_sd": float(retained_row["binary_ability_sd"]),
            "binary_ability_hdi_2_5pct": float(retained_row["binary_ability_hdi_2_5pct"]),
            "binary_ability_hdi_97_5pct": float(retained_row["binary_ability_hdi_97_5pct"]),
            "consistency_mean": None,
            "consistency_sd": None,
            "consistency_hdi_2_5pct": None,
            "consistency_hdi_97_5pct": None,
            "consistency_availability": protocol["no_gate_decision"]["consistency_availability"],
        })
    _require(len({row["solver_variant_id"] for row in rows}) == 18, "duplicate variant")
    return rows, protocol


def _table_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "artifact_id": f"{ARTIFACT_ID}_table",
        "bundle_materialization": "derivable_at_export",
        "columns": list(PROMOTED_COLUMNS),
        "encoding": "row_array_table_v1",
        "estimate_label": "frozen binary-Rasch posterior estimate; continuous-model consistency excluded",
        "layer": "difficulty",
        "primary_key": ["solver_variant_id"],
        "rows": [[row[column] for column in PROMOTED_COLUMNS] for row in rows],
        "source_state": "frozen_artifact",
        "table_name": "variant_ability_consistency",
    }


def _manifest_directory(directory: Path, artifact_id: str, status: str) -> Mapping[str, Any]:
    files = []
    for path in sorted(item for item in directory.rglob("*") if item.is_file() and item.name != "artifact_manifest.json"):
        files.append({
            "bytes": path.stat().st_size,
            "path": path.relative_to(directory).as_posix(),
            "sha256": sha256_file(path),
        })
    manifest = {"artifact_id": artifact_id, "files": files, "status": status}
    _write_json(directory / "artifact_manifest.json", manifest, pretty=True)
    return manifest


def build_scoped_variant_ability(root: Path, source_directory: Path, output_directory: Path) -> Mapping[str, Any]:
    root, output_directory = root.resolve(), output_directory.resolve()
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    rows, protocol = _source_rows(root, source_directory)
    output_directory.mkdir(parents=True)
    _write_json(output_directory / "variant_ability_consistency.json", _table_payload(rows))
    report = {
        "artifact_id": f"{ARTIFACT_ID}_report",
        "consistency_availability": protocol["no_gate_decision"]["consistency_availability"],
        "continuous_model_quantities_included": False,
        "factor_model_quantities_included": False,
        "model": protocol["binary_projection"]["model"],
        "new_sampling": False,
        "output_kind": "frozen_posterior_estimate",
        "status": "complete_internal_scoped_promotion",
        "variant_rows": len(rows),
    }
    _write_json(output_directory / "report.json", report, pretty=True)
    (output_directory / "README.md").write_text(
        "# Scoped solver ability posterior\n\n"
        "This internal artifact contains the 18 per-variant ability posteriors "
        "from the accepted binary Rasch fit. Consistency values are explicit "
        "nulls because that estimand belongs to the excluded continuous model.\n",
        encoding="utf-8",
    )
    _manifest_directory(output_directory, f"{ARTIFACT_ID}_manifest", "complete_internal_scoped_promotion")
    return verify_scoped_variant_ability(output_directory)


def verify_scoped_variant_ability(directory: Path) -> Mapping[str, Any]:
    directory = directory.resolve()
    manifest = _read_json(directory / "artifact_manifest.json")
    _require(manifest["artifact_id"] == f"{ARTIFACT_ID}_manifest", "wrong promotion manifest")
    expected = {"artifact_manifest.json"}
    forbidden = _forbidden_term()
    for record in manifest["files"]:
        path = directory / record["path"]
        _require(path.is_file(), f"missing promotion file: {path}")
        _require(path.stat().st_size == record["bytes"], f"promotion size drift: {path}")
        _require(sha256_file(path) == record["sha256"], f"promotion hash drift: {path}")
        _require(forbidden not in path.read_bytes().lower(), f"retired vocabulary: {path}")
        expected.add(record["path"])
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    _require(actual == expected, "unmanifested promotion files")
    table = _read_json(directory / "variant_ability_consistency.json")
    _require(table["columns"] == list(PROMOTED_COLUMNS), "promotion columns")
    _require(len(table["rows"]) == 18, "promotion row count")
    records = [dict(zip(table["columns"], row)) for row in table["rows"]]
    _require(len({row["solver_variant_id"] for row in records}) == 18, "promotion key")
    _require(all(row["model"] == "family_aware_binary_rasch" for row in records), "model drift")
    _require(all(row["consistency_availability"] == "excluded_continuous_model_quantity" for row in records), "consistency scope")
    consistency = ("consistency_mean", "consistency_sd", "consistency_hdi_2_5pct", "consistency_hdi_97_5pct")
    _require(all(row[column] is None for row in records for column in consistency), "continuous consistency included")
    report = _read_json(directory / "report.json")
    _require(report["continuous_model_quantities_included"] is False, "continuous model inclusion")
    return {"manifest_sha256": sha256_file(directory / "artifact_manifest.json"), "rows_verified": 18, "status": "pass"}


def _tree_hashes(directory: Path) -> dict[str, str]:
    return {path.relative_to(directory).as_posix(): sha256_file(path) for path in sorted(item for item in directory.rglob("*") if item.is_file())}


def finalize_identical_runs(run_1: Path, run_2: Path, final_directory: Path, identity_path: Path, artifact_id: str) -> Mapping[str, Any]:
    run_1, run_2, final_directory, identity_path = map(Path.resolve, (run_1, run_2, final_directory, identity_path))
    _require(not final_directory.exists(), f"final exists: {final_directory}")
    first, second = _tree_hashes(run_1), _tree_hashes(run_2)
    _require(first == second, "two runs differ")
    identity = {
        "artifact_id": artifact_id,
        "byte_identical": True,
        "file_count": len(first),
        "file_hashes": first,
        "raw_trees_retained": True,
        "relative_paths": sorted(first),
        "status": "pass",
    }
    _write_json(identity_path, identity, pretty=True)
    shutil.copytree(run_1, final_directory)
    _require(_tree_hashes(final_directory) == first, "promoted tree differs")
    return {"file_count": len(first), "identity_sha256": sha256_file(identity_path), "status": "pass"}


def _addendum_definitions(protocol: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "artifact_id": f"{ADDENDUM_ARTIFACT_ID}_definitions",
        "definitions_are_normative": True,
        "layer": {
            "bundle_materialization": "derivable_at_export",
            "estimate_label": "frozen binary-Rasch posterior estimate",
            "source_state": "frozen_artifact",
        },
        "model_provenance": {
            "ability": "family-aware binary Rasch posterior",
            "consistency": "excluded because the available estimand is a continuous Beta precision transform",
            "consistency_availability": protocol["no_gate_decision"]["consistency_availability"],
        },
        "replacement_semantics": "Replace the base v3 zero-row availability payload at the same layer path with this 18-row table; do not modify other v3 files.",
        "release": {"public_deployment_authorized": False, "validated_predictor_claim": False},
    }


def build_addendum_bundle(root: Path, promotion_directory: Path, output_directory: Path) -> Mapping[str, Any]:
    root, promotion_directory, output_directory = root.resolve(), promotion_directory.resolve(), output_directory.resolve()
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    protocol = _read_json(root / PREREGISTRATION)
    promotion_report = verify_scoped_variant_ability(promotion_directory)
    identity_path = root / PROMOTION_IDENTITY
    identity = _read_json(identity_path)
    _require(identity["status"] == "pass" and identity["byte_identical"] is True, "promotion identity failed")

    base = protocol["frontend_addendum"]
    base_bundle = root / BASE_BUNDLE
    base_identity = root / BASE_IDENTITY
    _require(sha256_file(base_bundle / "index.json") == base["base_index_sha256"], "base index drift")
    _require(sha256_file(base_bundle / "definitions.json") == base["base_definitions_sha256"], "base definitions drift")
    _require(sha256_file(base_bundle / "public_name_mapping.json") == base["base_public_name_mapping_sha256"], "base mapping drift")
    _require(sha256_file(base_bundle / "layers/difficulty/variant_ability_consistency.json") == base["base_zero_row_payload_sha256"], "base replacement payload drift")
    _require(sha256_file(base_identity) == base["base_two_run_identity_sha256"], "base identity drift")

    output_directory.mkdir(parents=True)
    layer_path = Path("layers/difficulty/variant_ability_consistency.json")
    layer_destination = output_directory / layer_path
    layer_destination.parent.mkdir(parents=True)
    shutil.copyfile(promotion_directory / "variant_ability_consistency.json", layer_destination)
    _write_json(output_directory / "definitions.json", _addendum_definitions(protocol), pretty=True)
    shutil.copyfile(base_bundle / "public_name_mapping.json", output_directory / "public_name_mapping.json")
    schema_destination = output_directory / "schema/index.schema.json"
    schema_destination.parent.mkdir(parents=True)
    shutil.copyfile(root / ADDENDUM_SCHEMA, schema_destination)
    (output_directory / "README.md").write_text(
        "# Solver-ability frontend addendum v3.1\n\n"
        "Apply this internal single-layer addendum to the accepted v3 bundle. "
        "It replaces only the difficulty-layer variant availability payload. "
        "All other v3 files and release fences remain unchanged.\n",
        encoding="utf-8",
    )
    files = [
        _file_record(output_directory, "README.md", role="documentation"),
        _file_record(output_directory, "definitions.json", role="normative_definitions"),
        _file_record(output_directory, layer_path.as_posix(), role="frontend_layer", row_count=18),
        _file_record(output_directory, "public_name_mapping.json", role="public_name_mapping"),
        _file_record(output_directory, "schema/index.schema.json", role="schema"),
    ]
    files.sort(key=lambda row: row["path"])
    index = {
        "$schema": "schema/index.schema.json",
        "applies_to": {
            "base_artifact_id": "ml11_frontend_bundle_v3",
            "base_index_sha256": base["base_index_sha256"],
            "replaces_path": layer_path.as_posix(),
            "replaces_sha256": base["base_zero_row_payload_sha256"],
        },
        "artifact_id": ADDENDUM_ARTIFACT_ID,
        "entrypoints": {
            "definitions": "definitions.json",
            "public_name_mapping": "public_name_mapping.json",
            "variant_ability_consistency": layer_path.as_posix(),
        },
        "files": files,
        "layer": {
            "bundle_materialization": "derivable_at_export",
            "estimate_label": "frozen binary-Rasch posterior estimate",
            "row_count": 18,
            "source_state": "frozen_artifact",
        },
        "release_scope": {"public_deployment_authorized": False, "validated_predictor_claim": False},
        "schema_version": "3.1.0",
        "source": {
            "promotion_identity_sha256": sha256_file(identity_path),
            "promotion_manifest_sha256": promotion_report["manifest_sha256"],
        },
        "status": "complete_internal_single_layer_addendum",
    }
    _write_json(output_directory / "index.json", index, pretty=True)
    return verify_addendum_bundle(output_directory)


def verify_addendum_bundle(directory: Path) -> Mapping[str, Any]:
    directory = directory.resolve()
    index = _read_json(directory / "index.json")
    schema = _read_json(directory / index["$schema"])
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(index)
    _require(index["artifact_id"] == ADDENDUM_ARTIFACT_ID, "wrong addendum artifact")
    _require(index["release_scope"]["public_deployment_authorized"] is False, "release drift")
    _require(index["release_scope"]["validated_predictor_claim"] is False, "predictor claim drift")
    expected = {"index.json"}
    forbidden = _forbidden_term()
    for record in index["files"]:
        path = directory / record["path"]
        _require(path.is_file(), f"missing addendum file: {path}")
        _require(path.stat().st_size == record["bytes"], f"addendum size drift: {path}")
        _require(sha256_file(path) == record["sha256"], f"addendum hash drift: {path}")
        _require(forbidden not in path.read_bytes().lower(), f"retired vocabulary: {path}")
        expected.add(record["path"])
    _require(forbidden not in (directory / "index.json").read_bytes().lower(), "retired vocabulary: index")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    _require(actual == expected, "unmanifested addendum files")
    table = _read_json(directory / index["entrypoints"]["variant_ability_consistency"])
    _require(len(table["rows"]) == 18, "addendum row count")
    records = [dict(zip(table["columns"], row)) for row in table["rows"]]
    mapping = _read_json(directory / "public_name_mapping.json")
    identifiers = {row["internal_identifier"] for row in mapping["mapping"]}
    _require({row["solver_variant_id"] for row in records} <= identifiers, "public-name mapping gap")
    definitions = _read_json(directory / "definitions.json")
    _require(definitions["definitions_are_normative"] is True, "definitions not normative")
    _require(definitions["layer"]["source_state"] == "frozen_artifact", "source state")
    return {"files_verified": len(actual), "index_sha256": sha256_file(directory / "index.json"), "rows_verified": 18, "status": "pass"}


def build_addendum_run(root: Path, promotion_directory: Path, run_directory: Path) -> Mapping[str, Any]:
    run_directory = run_directory.resolve()
    _require(not run_directory.exists(), f"run exists: {run_directory}")
    run_directory.mkdir(parents=True)
    bundle = run_directory / "frontend_ability_addendum_v3_1"
    archive = run_directory / "frontend_ability_addendum_v3_1.zip"
    report = build_addendum_bundle(root, promotion_directory, bundle)
    write_deterministic_zip(bundle, archive)
    archive_report = verify_ml11_archive(bundle, archive)
    _manifest_directory(run_directory, "ml11b_frontend_addendum_run_manifest_v1", "complete_internal_deterministic_export")
    return {**report, "archive": archive_report, "run_manifest_sha256": sha256_file(run_directory / "artifact_manifest.json")}
