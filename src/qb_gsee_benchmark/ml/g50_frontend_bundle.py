"""Deterministic frontend export for the corrected G50 solver-family analysis."""

from __future__ import annotations

import json
import math
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.core_set import sha256_file

ARTIFACT_ID = "g50_solver_family_frontend_v1"
SCHEMA_VERSION = "1.0.0"
SOURCE_MANIFEST_SHA256 = (
    "b182856c3ddf53ab3706fc2bb1a521952b530991b91e9254d8ee2ff51de52a4e"
)
SOURCE_DIRECTORY = Path("analysis/ml_g50_solver_families/final_v4")
PREREGISTRATION_PATH = Path("analysis/ml_g50_solver_families/preregistration.json")
TRIMCI_AMENDMENT_PATH = Path(
    "analysis/ml_g50_solver_families/amendment_trimci_bounded_rung_semantics.json"
)
INDEX_SCHEMA_PATH = Path(
    "analysis/ml_g50_solver_families/frontend_bundle_v1.schema.json"
)

EXPECTED_COUNTS = {
    "corpus_tasks": 718,
    "selected_tasks": 96,
    "canonical_families": 40,
    "solver_families": 4,
    "solver_variants": 18,
    "selected_features": 193,
    "observations": 1728,
    "coverage_rows": 1728,
    "predictions": 25848,
    "prediction_rows_per_variant": 1436,
}

SUMMARY_TABLES = (
    "variant_eligibility",
    "ladder_growth",
    "nestedness",
    "family_balanced_performance",
    "paired_deltas",
)

TABLE_KEYS: dict[str, list[str]] = {
    "observations": ["task_uuid", "solver_uuid"],
    "coverage": ["task_uuid", "solver_uuid"],
    "predictions": ["task_uuid", "solver_uuid", "feature_arm"],
    "variant_eligibility": ["solver_uuid"],
    "ladder_growth": ["solver_uuid"],
    "nestedness": [
        "solver_family_id",
        "resource_ladder_id",
        "earlier_solver_short_name",
        "later_solver_short_name",
    ],
    "family_balanced_performance": [
        "solver_uuid",
        "estimator",
        "feature_arm",
        "metric",
    ],
    "paired_deltas": ["solver_uuid", "comparison", "metric"],
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _json_scalar(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        _require(math.isfinite(number), "frontend data contains a non-finite number")
        return number
    return str(value)


def _json_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _json_scalar(value) for key, value in record.items()}


def _json_bytes(payload: Any, *, pretty: bool = False) -> bytes:
    options: dict[str, Any] = {
        "allow_nan": False,
        "sort_keys": True,
    }
    if pretty:
        options["indent"] = 2
    else:
        options["separators"] = (",", ":")
    return (json.dumps(payload, **options) + "\n").encode("utf-8")


def _write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload, pretty=pretty))


def _table_payload(
    frame: pd.DataFrame,
    table_name: str,
    *,
    source_path: str,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    columns = list(map(str, frame.columns))
    rows = [
        [_json_scalar(value) for value in row]
        for row in frame.itertuples(index=False, name=None)
    ]
    payload: dict[str, Any] = {
        "artifact_id": f"{ARTIFACT_ID}_{table_name}",
        "encoding": "row_array_table_v1",
        "table_name": table_name,
        "source_path": source_path,
        "primary_key": TABLE_KEYS[table_name],
        "columns": columns,
        "rows": rows,
    }
    if metadata:
        payload["metadata"] = dict(metadata)
    return payload


def _table_records(payload: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    columns = payload["columns"]
    for row in payload["rows"]:
        yield dict(zip(columns, row))


def _verify_source_manifest(source_directory: Path) -> tuple[dict[str, Any], str]:
    manifest_path = source_directory / "artifact_manifest.json"
    _require(manifest_path.is_file(), f"missing source manifest: {manifest_path}")
    digest = sha256_file(manifest_path)
    _require(
        digest == SOURCE_MANIFEST_SHA256,
        f"corrected G50 source manifest changed: {digest}",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(
        manifest.get("status") == "complete_internal_descriptive_no_gate",
        "source G50 status changed",
    )
    for record in manifest["files"]:
        path = source_directory / str(record["path"])
        _require(path.is_file(), f"missing source payload: {path}")
        _require(path.stat().st_size == record["bytes"], f"changed size: {path}")
        _require(sha256_file(path) == record["sha256"], f"changed hash: {path}")
    return manifest, digest


def _resolve_local_input(root: Path, specification: Mapping[str, Any]) -> Path:
    relative = specification.get("path")
    _require(bool(relative), "frontend source input must be repository-local")
    path = root / str(relative)
    _require(path.is_file(), f"missing pinned frontend source: {path}")
    _require(
        sha256_file(path) == specification["sha256"],
        f"changed pinned frontend source: {path}",
    )
    return path


def _load_sources(root: Path) -> dict[str, Any]:
    source_directory = root / SOURCE_DIRECTORY
    source_manifest, source_manifest_sha256 = _verify_source_manifest(source_directory)
    preregistration_path = root / PREREGISTRATION_PATH
    _require(
        sha256_file(preregistration_path) == source_manifest["preregistration_sha256"],
        "source preregistration changed",
    )
    preregistration = json.loads(preregistration_path.read_text(encoding="utf-8"))
    inputs = preregistration["inputs"]
    paths = {
        name: _resolve_local_input(root, inputs[name])
        for name in (
            "canonical_families",
            "feature_metadata",
            "feature_table",
            "selection_weights",
            "solver_family_catalog",
        )
    }
    amendment_path = root / TRIMCI_AMENDMENT_PATH
    _require(
        sha256_file(amendment_path)
        == source_manifest["trimci_bounded_rung_amendment_sha256"],
        "TrimCI bounded-rung amendment changed",
    )

    report = json.loads((source_directory / "report.json").read_text(encoding="utf-8"))
    _require(
        report.get("status") == "complete_internal_descriptive_no_gate",
        "source report is not complete",
    )
    _require(
        report.get("public_or_dashboard_bundle") is False,
        "source report release status changed",
    )
    _require(
        report.get("validated_predictor_claim") is False,
        "source report predictor status changed",
    )
    return {
        "source_directory": source_directory,
        "source_manifest": source_manifest,
        "source_manifest_sha256": source_manifest_sha256,
        "preregistration_path": preregistration_path,
        "preregistration": preregistration,
        "amendment_path": amendment_path,
        "paths": paths,
        "report": report,
    }


def _build_task_and_feature_catalog(
    sources: Mapping[str, Any], prediction_paths: Mapping[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = sources["paths"]
    source_directory = sources["source_directory"]
    taxonomy = json.loads(paths["canonical_families"].read_text(encoding="utf-8"))
    feature_metadata = pd.read_csv(paths["feature_metadata"])
    features = pd.read_csv(paths["feature_table"], low_memory=False)
    weights = pd.read_csv(paths["selection_weights"])
    census = pd.read_csv(source_directory / "preflight/feature_census.csv")
    variants = json.loads(
        (source_directory / "preflight/solver_variants.json").read_text(
            encoding="utf-8"
        )
    )
    eligibility = pd.read_csv(source_directory / "variant_eligibility.csv")
    solver_catalog = json.loads(
        paths["solver_family_catalog"].read_text(encoding="utf-8")
    )

    _require(features["task_uuid"].is_unique, "feature task UUIDs are not unique")
    taxonomy_by_task = {str(row["task_uuid"]): row for row in taxonomy["tasks"]}
    _require(len(taxonomy_by_task) == EXPECTED_COUNTS["corpus_tasks"], "task drift")
    task_order = sorted(taxonomy_by_task)
    features = features.set_index("task_uuid").loc[task_order]
    weight_by_task = {
        str(row.task_uuid): int(row.selection_weight)
        for row in weights.itertuples(index=False)
    }
    _require(len(weight_by_task) == EXPECTED_COUNTS["selected_tasks"], "weight drift")

    task_records = []
    for task_uuid in task_order:
        taxonomy_row = taxonomy_by_task[task_uuid]
        feature_row = features.loc[task_uuid]
        task_records.append(
            {
                "task_uuid": task_uuid,
                "problem_instance_uuid": taxonomy_row["problem_instance_uuid"],
                "problem_instance_short_name": taxonomy_row[
                    "problem_instance_short_name"
                ],
                "problem_instance_path": taxonomy_row["problem_instance_path"],
                "canonical_family": taxonomy_row["canonical_family_recommended"],
                "canonical_subfamily": taxonomy_row["canonical_subfamily"],
                "archive_class": taxonomy_row["archive_class"],
                "orbital_representation": _json_scalar(
                    feature_row.get("orbital_representation")
                ),
                "num_orbitals": _json_scalar(feature_row.get("num_orbitals")),
                "num_electrons": _json_scalar(feature_row.get("num_electrons")),
                "ms2": _json_scalar(feature_row.get("ms2")),
                "log_fci_dim": _json_scalar(feature_row.get("log_fci_dim")),
                "selected_for_g50": task_uuid in weight_by_task,
                "selection_weight": weight_by_task.get(task_uuid),
            }
        )

    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_records:
        by_family[row["canonical_family"]].append(row)
    family_records = [
        {
            "canonical_family": family,
            "task_count": len(rows),
            "selected_task_count": sum(row["selected_for_g50"] for row in rows),
            "archive_classes": sorted({row["archive_class"] for row in rows}),
        }
        for family, rows in sorted(by_family.items())
    ]

    selected_columns = list(
        census.loc[census["decision"].eq("selected"), "column"].astype(str)
    )
    _require(
        len(selected_columns) == EXPECTED_COUNTS["selected_features"],
        "selected feature count drift",
    )
    metadata_by_column = feature_metadata.set_index("column").to_dict(orient="index")
    census_by_column = census.set_index("column").to_dict(orient="index")
    feature_records = []
    feature_values: dict[str, list[Any]] = {}
    for column in sorted(selected_columns):
        metadata = metadata_by_column[column]
        logical_block = str(census_by_column[column]["logical_block"])
        protocol = str(metadata["protocol"])
        feature_records.append(
            {
                "column": column,
                "logical_block": logical_block,
                "protocol": protocol,
                "provenance_tier": str(metadata["provenance_tier"]),
                "representation": str(metadata["representation"]),
                "role": str(metadata["role"]),
                "scaling": str(metadata["scaling"]),
                "cost_class": str(metadata["cost_class"]),
                "definition": str(metadata["definition"]),
                "available_to_solver_families": [
                    family
                    for family in ("dmrg", "ipie_afqmc", "shci", "trimci")
                    if family != "ipie_afqmc" or protocol != "MF-PROTO"
                ],
                "included_in_without_jw_arm": logical_block != "jw_encoding",
            }
        )
        feature_values[column] = [
            _json_scalar(value) for value in features[column].tolist()
        ]

    variant_by_uuid = {
        str(row["solver_uuid"]): row for row in solver_catalog["variants"]
    }
    family_ids = {str(row["solver_family_id"]) for row in variants}
    solver_families = [
        _json_record(row)
        for row in solver_catalog["families"]
        if str(row["solver_family_id"]) in family_ids
    ]
    eligibility_by_uuid = eligibility.set_index("solver_uuid").to_dict(orient="index")
    variant_records = []
    for row in variants:
        solver_uuid = str(row["solver_uuid"])
        source_variant = variant_by_uuid[solver_uuid]
        merged = {
            **_json_record(row),
            "display_name": source_variant["display_name"],
            "implementation_id": source_variant["implementation_id"],
            "catalog_status": source_variant["catalog_status"],
            "prediction_file": prediction_paths[solver_uuid],
            "model_eligibility": _json_record(eligibility_by_uuid[solver_uuid]),
        }
        variant_records.append(merged)

    catalog = {
        "artifact_id": f"{ARTIFACT_ID}_catalog",
        "task_order_contract": "tasks and feature arrays share this task order",
        "tasks": task_records,
        "canonical_families": family_records,
        "solver_families": solver_families,
        "solver_variants": variant_records,
        "feature_columns": feature_records,
    }
    feature_payload = {
        "artifact_id": f"{ARTIFACT_ID}_features",
        "encoding": "columnar_feature_matrix_v1",
        "task_uuid": task_order,
        "features": feature_values,
        "null_semantics": (
            "null means the feature is not applicable or unavailable; the ML protocol "
            "uses exact-applicability blocks and no cross-domain imputation"
        ),
    }
    return catalog, feature_payload


def _prediction_chunk_paths(variants: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    paths = {}
    for index, row in enumerate(variants, start=1):
        short_name = str(row["solver_short_name"])
        safe_name = "".join(
            character.lower() if character.isalnum() else "_"
            for character in short_name
        ).strip("_")
        while "__" in safe_name:
            safe_name = safe_name.replace("__", "_")
        paths[str(row["solver_uuid"])] = f"predictions/{index:02d}_{safe_name}.json"
    return paths


def _source_evidence_files(sources: Mapping[str, Any]) -> list[tuple[Path, str]]:
    source_directory = sources["source_directory"]
    files = [
        (
            source_directory / record["path"],
            f"source_evidence/final_v4/{record['path']}",
        )
        for record in sources["source_manifest"]["files"]
    ]
    files.extend(
        [
            (
                source_directory / "artifact_manifest.json",
                "source_evidence/final_v4/artifact_manifest.json",
            ),
            (
                sources["preregistration_path"],
                "source_evidence/protocol/preregistration.json",
            ),
            (
                sources["amendment_path"],
                "source_evidence/protocol/trimci_bounded_rung_amendment.json",
            ),
        ]
    )
    return files


def _readme() -> str:
    return """# G50 solver-family frontend bundle

Load `index.json` first. `catalog.json` contains task, family, variant, and
feature metadata. `features.json` is columnar and uses the same task order as
the catalog. Observations and coverage cover the 96 selected tasks across all
18 variants. Predictions are split by variant so a frontend can lazy-load one
solver curve at a time. `summaries.json` contains eligibility, ladder growth,
nestedness, performance, paired-ablation, and machine-report data.

Observed and predicted data are intentionally separate. A TrimCI cap that was
not reached has no energy and an indeterminate metric annotation, but is a
binary bounded-run failure. Do not infer monotonicity: the source analysis
records lost-success transitions instead of repairing them.

This package is for internal descriptive visualization. The models are not
validated out-of-family predictors, and predicted values must be labeled as
estimates rather than observed benchmark outcomes. `source_evidence/` retains
the byte-exact corrected final_v4 evidence used to build the frontend tables.
"""


def _file_record(
    output_directory: Path,
    relative_path: str,
    *,
    role: str,
    row_count: int | None = None,
) -> dict[str, Any]:
    path = output_directory / relative_path
    record: dict[str, Any] = {
        "path": relative_path,
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if row_count is not None:
        record["row_count"] = row_count
    return record


def _copy_source_evidence(
    output_directory: Path, sources: Mapping[str, Any]
) -> list[str]:
    copied = []
    for source, relative in _source_evidence_files(sources):
        destination = output_directory / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied.append(relative)
    return copied


def build_frontend_bundle(
    repository_root: Path,
    output_directory: Path,
    *,
    archive_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Build and verify one self-contained frontend handoff directory."""

    repository_root = repository_root.resolve()
    output_directory = output_directory.resolve()
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    sources = _load_sources(repository_root)
    source_directory = sources["source_directory"]

    variants = json.loads(
        (source_directory / "preflight/solver_variants.json").read_text(
            encoding="utf-8"
        )
    )
    prediction_paths = _prediction_chunk_paths(variants)
    catalog, feature_payload = _build_task_and_feature_catalog(
        sources, prediction_paths
    )

    output_directory.mkdir(parents=True)
    _write_json(output_directory / "catalog.json", catalog)
    _write_json(output_directory / "features.json", feature_payload)

    observations = pd.read_csv(source_directory / "normalized_observations.csv")
    coverage = pd.read_csv(source_directory / "coverage.csv")
    observation_payload = _table_payload(
        observations,
        "observations",
        source_path="analysis/ml_g50_solver_families/final_v4/normalized_observations.csv",
        metadata={
            "outcome_semantics": "binary bounded-run label",
            "energy_null_semantics": (
                "null energy may still be a binary fail when the bounded resource "
                "target was not reached"
            ),
        },
    )
    coverage_payload = _table_payload(
        coverage,
        "coverage",
        source_path="analysis/ml_g50_solver_families/final_v4/coverage.csv",
    )
    _write_json(output_directory / "observations.json", observation_payload)
    _write_json(output_directory / "coverage.json", coverage_payload)

    predictions = pd.read_csv(source_directory / "predictions.csv")
    prediction_records = []
    for variant in variants:
        solver_uuid = str(variant["solver_uuid"])
        frame = predictions.loc[predictions["solver_uuid"].eq(solver_uuid)]
        payload = _table_payload(
            frame,
            "predictions",
            source_path="analysis/ml_g50_solver_families/final_v4/predictions.csv",
            metadata={
                "solver_uuid": solver_uuid,
                "solver_short_name": variant["solver_short_name"],
                "solver_family_id": variant["solver_family_id"],
            },
        )
        relative = prediction_paths[solver_uuid]
        _write_json(output_directory / relative, payload)
        prediction_records.append(
            {
                "solver_uuid": solver_uuid,
                "solver_short_name": variant["solver_short_name"],
                "solver_family_id": variant["solver_family_id"],
                "path": relative,
                "row_count": len(frame),
            }
        )

    summary_payload = {
        "artifact_id": f"{ARTIFACT_ID}_summaries",
        "report": sources["report"],
        "tables": {},
    }
    summary_counts = {}
    for table_name in SUMMARY_TABLES:
        frame = pd.read_csv(source_directory / f"{table_name}.csv")
        summary_payload["tables"][table_name] = _table_payload(
            frame,
            table_name,
            source_path=f"analysis/ml_g50_solver_families/final_v4/{table_name}.csv",
        )
        summary_counts[table_name] = len(frame)
    _write_json(output_directory / "summaries.json", summary_payload)

    (output_directory / "README.md").write_text(_readme(), encoding="utf-8")
    selected_schema = schema_path or repository_root / INDEX_SCHEMA_PATH
    schema_destination = output_directory / "schema/index.schema.json"
    schema_destination.parent.mkdir(parents=True)
    shutil.copyfile(selected_schema, schema_destination)
    copied_evidence = _copy_source_evidence(output_directory, sources)

    files = [
        _file_record(output_directory, "README.md", role="documentation"),
        _file_record(output_directory, "catalog.json", role="frontend_catalog"),
        _file_record(
            output_directory,
            "coverage.json",
            role="frontend_table",
            row_count=len(coverage),
        ),
        _file_record(output_directory, "features.json", role="frontend_features"),
        _file_record(
            output_directory,
            "observations.json",
            role="frontend_table",
            row_count=len(observations),
        ),
        _file_record(output_directory, "schema/index.schema.json", role="schema"),
        _file_record(
            output_directory,
            "summaries.json",
            role="frontend_summaries",
            row_count=sum(summary_counts.values()),
        ),
    ]
    for record in prediction_records:
        files.append(
            _file_record(
                output_directory,
                record["path"],
                role="frontend_prediction_chunk",
                row_count=record["row_count"],
            )
        )
    for relative in copied_evidence:
        files.append(_file_record(output_directory, relative, role="audit_source"))
    files.sort(key=lambda row: row["path"])

    index = {
        "$schema": "schema/index.schema.json",
        "artifact_id": ARTIFACT_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "complete_internal_descriptive_visualization_bundle",
        "entrypoints": {
            "catalog": "catalog.json",
            "features": "features.json",
            "observations": "observations.json",
            "coverage": "coverage.json",
            "summaries": "summaries.json",
        },
        "release_scope": {
            "intended_use": "internal interactive descriptive visualization",
            "public_dashboard_release_authorized": False,
            "validated_predictor_claim": False,
            "prediction_display_label": "estimated solvability",
            "observation_display_label": "observed bounded-run outcome",
        },
        "semantics": {
            "binary_outcomes": ["fail", "success"],
            "feature_arms": ["with_jw", "without_jw"],
            "trimci_unreached_cap": (
                "energy is null and metric annotation is indeterminate; binary "
                "bounded-run outcome is fail"
            ),
            "monotonic_repair_applied": False,
            "canonical_family_model_input": False,
        },
        "counts": {
            **EXPECTED_COUNTS,
            "prediction_chunks": len(prediction_records),
            "summary_rows": summary_counts,
            "feature_values": sum(
                len(values) for values in feature_payload["features"].values()
            ),
            "feature_null_values": sum(
                value is None
                for values in feature_payload["features"].values()
                for value in values
            ),
        },
        "source": {
            "analysis_protocol": sources["source_manifest"]["protocol"],
            "analysis_directory": str(SOURCE_DIRECTORY),
            "analysis_manifest_sha256": sources["source_manifest_sha256"],
            "preregistration_sha256": sources["source_manifest"][
                "preregistration_sha256"
            ],
            "trimci_bounded_rung_amendment_sha256": sources["source_manifest"][
                "trimci_bounded_rung_amendment_sha256"
            ],
            "feature_table_sha256": sources["preregistration"]["inputs"][
                "feature_table"
            ]["sha256"],
            "canonical_families_sha256": sources["preregistration"]["inputs"][
                "canonical_families"
            ]["sha256"],
            "solver_family_catalog_sha256": sources["preregistration"]["inputs"][
                "solver_family_catalog"
            ]["sha256"],
        },
        "prediction_chunks": prediction_records,
        "files": files,
    }
    _write_json(output_directory / "index.json", index, pretty=True)
    report = verify_frontend_bundle(output_directory)
    if archive_path is not None:
        write_deterministic_zip(output_directory, archive_path)
        report["archive"] = verify_frontend_archive(output_directory, archive_path)
    return report


def _verify_table(
    payload: Mapping[str, Any], table_name: str, expected_rows: int
) -> list[dict[str, Any]]:
    _require(payload.get("encoding") == "row_array_table_v1", "wrong table encoding")
    _require(payload.get("table_name") == table_name, f"wrong {table_name} name")
    columns = payload.get("columns")
    rows = payload.get("rows")
    _require(isinstance(columns, list) and len(columns) == len(set(columns)), "columns")
    _require(
        isinstance(rows, list) and len(rows) == expected_rows, f"{table_name} rows"
    )
    _require(
        all(isinstance(row, list) and len(row) == len(columns) for row in rows),
        f"{table_name} row width",
    )
    keys = payload.get("primary_key")
    _require(keys == TABLE_KEYS[table_name], f"wrong {table_name} primary key")
    records = list(_table_records(payload))
    key_values = [tuple(row[column] for column in keys) for row in records]
    _require(len(key_values) == len(set(key_values)), f"duplicate {table_name} key")
    return records


def verify_frontend_bundle(output_directory: Path) -> dict[str, Any]:
    """Fail closed on hashes, joins, counts, and frontend semantics."""

    output_directory = output_directory.resolve()
    index_path = output_directory / "index.json"
    _require(index_path.is_file(), "missing frontend index")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    schema = json.loads(
        (output_directory / "schema/index.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(index)
    _require(index.get("artifact_id") == ARTIFACT_ID, "wrong frontend artifact")
    _require(index.get("schema_version") == SCHEMA_VERSION, "wrong frontend schema")
    _require(index.get("counts", {}).get("corpus_tasks") == 718, "wrong task count")
    _require(
        index.get("release_scope", {}).get("validated_predictor_claim") is False,
        "frontend bundle makes a validated predictor claim",
    )
    _require(
        index.get("release_scope", {}).get("public_dashboard_release_authorized")
        is False,
        "frontend bundle claims public release authorization",
    )
    _require(
        index.get("source", {}).get("analysis_manifest_sha256")
        == SOURCE_MANIFEST_SHA256,
        "frontend source manifest drift",
    )

    expected_files = {"index.json"}
    for record in index["files"]:
        relative = str(record["path"])
        path = output_directory / relative
        _require(
            path.resolve().is_relative_to(output_directory),
            f"unsafe frontend path: {relative}",
        )
        _require(path.is_file(), f"missing frontend file: {relative}")
        _require(path.stat().st_size == record["bytes"], f"size drift: {relative}")
        _require(sha256_file(path) == record["sha256"], f"hash drift: {relative}")
        expected_files.add(relative)
    actual_files = {
        str(path.relative_to(output_directory))
        for path in output_directory.rglob("*")
        if path.is_file()
    }
    _require(actual_files == expected_files, "unmanifested frontend files")

    catalog = json.loads((output_directory / "catalog.json").read_text())
    features = json.loads((output_directory / "features.json").read_text())
    tasks = catalog["tasks"]
    _require(len(tasks) == EXPECTED_COUNTS["corpus_tasks"], "catalog task count")
    task_uuids = [row["task_uuid"] for row in tasks]
    _require(len(task_uuids) == len(set(task_uuids)), "duplicate catalog task")
    selected_tasks = {row["task_uuid"] for row in tasks if row["selected_for_g50"]}
    _require(len(selected_tasks) == EXPECTED_COUNTS["selected_tasks"], "selection")
    _require(
        sum(row["selection_weight"] or 0 for row in tasks) == 718,
        "selection weights",
    )
    _require(
        len(catalog["canonical_families"]) == EXPECTED_COUNTS["canonical_families"],
        "canonical family count",
    )
    _require(
        len(catalog["solver_families"]) == EXPECTED_COUNTS["solver_families"],
        "solver family count",
    )
    variants = catalog["solver_variants"]
    _require(len(variants) == EXPECTED_COUNTS["solver_variants"], "variant count")
    variant_uuids = {row["solver_uuid"] for row in variants}
    _require(len(variant_uuids) == len(variants), "duplicate solver variant")
    _require(
        len(catalog["feature_columns"]) == EXPECTED_COUNTS["selected_features"],
        "feature metadata count",
    )
    _require(features["task_uuid"] == task_uuids, "feature task order mismatch")
    feature_names = {row["column"] for row in catalog["feature_columns"]}
    _require(set(features["features"]) == feature_names, "feature columns mismatch")
    for column, values in features["features"].items():
        _require(len(values) == len(tasks), f"feature length: {column}")
        _require(
            all(
                value is None
                or (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                )
                for value in values
            ),
            f"invalid feature value: {column}",
        )

    observations = _verify_table(
        json.loads((output_directory / "observations.json").read_text()),
        "observations",
        EXPECTED_COUNTS["observations"],
    )
    coverage = _verify_table(
        json.loads((output_directory / "coverage.json").read_text()),
        "coverage",
        EXPECTED_COUNTS["coverage_rows"],
    )
    observation_keys = {(row["task_uuid"], row["solver_uuid"]) for row in observations}
    coverage_keys = {(row["task_uuid"], row["solver_uuid"]) for row in coverage}
    _require(observation_keys == coverage_keys, "observation/coverage key mismatch")
    _require(
        {row["task_uuid"] for row in observations} == selected_tasks,
        "observation task scope",
    )
    _require(
        {row["solver_uuid"] for row in observations} == variant_uuids,
        "observation solver scope",
    )
    _require(
        {row["observed_outcome"] for row in observations} == {"fail", "success"},
        "observation outcome semantics",
    )
    _require(
        all(row["enters_binary_label_table"] is True for row in coverage),
        "coverage labels are incomplete",
    )

    prediction_keys = set()
    total_predictions = 0
    chunks = index["prediction_chunks"]
    _require(len(chunks) == EXPECTED_COUNTS["solver_variants"], "chunk count")
    for chunk in chunks:
        solver_uuid = chunk["solver_uuid"]
        _require(solver_uuid in variant_uuids, "unknown prediction solver")
        payload = json.loads((output_directory / chunk["path"]).read_text())
        records = _verify_table(
            payload,
            "predictions",
            EXPECTED_COUNTS["prediction_rows_per_variant"],
        )
        _require(
            {row["solver_uuid"] for row in records} == {solver_uuid},
            "mixed prediction chunk",
        )
        _require(
            Counter(row["feature_arm"] for row in records)
            == {"with_jw": 718, "without_jw": 718},
            "prediction arm coverage",
        )
        _require(
            {row["task_uuid"] for row in records} == set(task_uuids),
            "prediction task coverage",
        )
        for row in records:
            fail = row["probability_fail"]
            success = row["probability_success"]
            probability = row["predicted_probability"]
            _require(0.0 <= fail <= 1.0 and 0.0 <= success <= 1.0, "probability")
            _require(abs(fail + success - 1.0) <= 1e-12, "probability sum")
            expected_probability = (
                success if row["predicted_outcome"] == "success" else fail
            )
            _require(abs(probability - expected_probability) <= 1e-12, "argmax value")
            key = (row["task_uuid"], solver_uuid, row["feature_arm"])
            _require(key not in prediction_keys, "duplicate prediction across chunks")
            prediction_keys.add(key)
        total_predictions += len(records)
    _require(total_predictions == EXPECTED_COUNTS["predictions"], "prediction total")

    summaries = json.loads((output_directory / "summaries.json").read_text())
    expected_summary_counts = index["counts"]["summary_rows"]
    for table_name in SUMMARY_TABLES:
        _verify_table(
            summaries["tables"][table_name],
            table_name,
            expected_summary_counts[table_name],
        )
    report = summaries["report"]
    _require(report["panel"]["normalized_labels"] == len(observations), "report labels")
    _require(
        report["panel"]["prediction_rows"] == total_predictions, "report predictions"
    )
    _require(report["validated_predictor_claim"] is False, "summary predictor claim")
    _require(report["public_or_dashboard_bundle"] is False, "summary release claim")

    return {
        "status": "pass",
        "artifact_id": ARTIFACT_ID,
        "files_verified": len(index["files"]),
        "tasks_verified": len(tasks),
        "features_verified": len(feature_names),
        "observations_verified": len(observations),
        "predictions_verified": total_predictions,
        "prediction_chunks_verified": len(chunks),
        "bundle_bytes": sum(record["bytes"] for record in index["files"])
        + index_path.stat().st_size,
        "index_sha256": sha256_file(index_path),
    }


def write_deterministic_zip(output_directory: Path, archive_path: Path) -> None:
    """Write a sorted, fixed-metadata ZIP containing the bundle directory."""

    output_directory = output_directory.resolve()
    archive_path = archive_path.resolve()
    _require(not archive_path.exists(), f"archive exists: {archive_path}")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    prefix = output_directory.name
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(
            item for item in output_directory.rglob("*") if item.is_file()
        ):
            relative = path.relative_to(output_directory).as_posix()
            info = zipfile.ZipInfo(
                f"{prefix}/{relative}", date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED
            )
    sidecar = archive_path.with_suffix(archive_path.suffix + ".sha256")
    sidecar.write_text(
        f"{sha256_file(archive_path)}  {archive_path.name}\n", encoding="ascii"
    )


def verify_frontend_archive(
    output_directory: Path, archive_path: Path
) -> dict[str, Any]:
    """Verify that a ZIP is an exact, duplicate-free image of the directory."""

    output_directory = output_directory.resolve()
    archive_path = archive_path.resolve()
    prefix = f"{output_directory.name}/"
    expected = {
        f"{prefix}{path.relative_to(output_directory).as_posix()}": path.read_bytes()
        for path in output_directory.rglob("*")
        if path.is_file()
    }
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        _require(len(names) == len(set(names)), "duplicate ZIP members")
        _require(set(names) == set(expected), "ZIP member set differs")
        for name, content in expected.items():
            _require(archive.read(name) == content, f"ZIP content differs: {name}")
    return {
        "status": "pass",
        "archive_path": str(archive_path),
        "archive_sha256": sha256_file(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "members_verified": len(expected),
    }
