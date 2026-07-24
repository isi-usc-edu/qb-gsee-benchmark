"""Pinned G50 solver-family ML inputs and outcome-blind preflight."""

from __future__ import annotations

import csv
import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.core_set import (
    _logical_block,
    _require,
    block_aware_distance,
    build_block_models,
    eligible_feature_columns,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.solver_families import load_solver_family_catalog

PROTOCOL_ID = "ml-g50-solver-families-v1"
G50_LADDERS = (
    "g50_dmrg_bond_dimension_v1",
    "g50_shci_orbopt_variational_eps_var_v1",
    "g50_trimci_target_determinants_v1",
)
TERMINAL_VARIANTS = (
    "SHCI_pt_2e-5_nchunks8",
    "TrimCI_default",
    "ipie_uhf_trial",
)


def _true(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().eq("true")


def load_preregistration(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(
        payload.get("artifact_id") == "ml_g50_solver_families_preregistration_v1",
        "wrong G50 ML preregistration",
    )
    _require(
        payload.get("frozen_before_model_fitting") is True,
        "preregistration is not frozen",
    )
    return payload


def resolve_input_path(root: Path, specification: Mapping[str, Any]) -> Path:
    local = specification.get("path")
    external = specification.get("external_path")
    _require(bool(local) != bool(external), "input must declare exactly one path kind")
    return root / str(local) if local else Path(str(external))


def verify_inputs(root: Path, preregistration: Mapping[str, Any]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path = resolve_input_path(root, specification)
        _require(path.is_file(), f"missing pinned input: {path}")
        digest = sha256_file(path)
        _require(digest == specification["sha256"], f"changed pinned input: {path}")
        hashes[name] = digest
    return hashes


def canonical_family_map(payload: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in payload["tasks"]:
        task_uuid = str(row["task_uuid"])
        _require(task_uuid not in result, f"duplicate canonical task: {task_uuid}")
        result[task_uuid] = str(row["canonical_family_recommended"])
    return result


def derive_feature_policy(
    metadata: pd.DataFrame, identifier_columns: Sequence[str]
) -> dict[str, Any]:
    eligible = set(eligible_feature_columns(metadata))
    identifiers = set(map(str, identifier_columns))
    _require(identifiers <= eligible, "identifier screen contains ineligible columns")
    gauge = set(
        metadata.loc[
            metadata["column"].isin(eligible)
            & _true(metadata["gauge_sensitive_at_degeneracy"]),
            "column",
        ].astype(str)
    )
    _require(not gauge & identifiers, "gauge and identifier exclusions overlap")
    selected = sorted(eligible - gauge - identifiers)
    by_column = metadata.set_index("column").to_dict(orient="index")
    jw = sorted(
        column
        for column in selected
        if _logical_block(column, by_column[column]) == "jw_encoding"
    )
    ipie = sorted(
        column
        for column in selected
        if str(by_column[column]["protocol"]) != "MF-PROTO"
    )
    return {
        "eligible": sorted(eligible),
        "gauge": sorted(gauge),
        "identifiers": sorted(identifiers),
        "selected": selected,
        "jw": jw,
        "solver_family_columns": {
            "dmrg": selected,
            "shci": selected,
            "trimci": selected,
            "ipie_afqmc": ipie,
        },
    }


def g50_variant_rows(catalog_path: Path) -> list[dict[str, Any]]:
    catalog = load_solver_family_catalog(catalog_path)
    rows: list[dict[str, Any]] = []
    for solver_uuid, variant in catalog.variants.items():
        axis = variant.get("resource_axis") or {}
        if (
            axis.get("ladder_id") in G50_LADDERS
            or variant["solver_short_name"] in TERMINAL_VARIANTS
        ):
            family = catalog.families[str(variant["solver_family_id"])]
            rows.append(
                {
                    "solver_uuid": solver_uuid,
                    "solver_short_name": str(variant["solver_short_name"]),
                    "solver_family_id": str(variant["solver_family_id"]),
                    "solver_family_uuid": str(family["solver_family_uuid"]),
                    "solver_variant_id": str(variant["solver_variant_id"]),
                    "result_semantics": str(variant["result_semantics"]),
                    "resource_ladder_id": axis.get("ladder_id"),
                    "resource_axis_name": axis.get("name"),
                    "resource_value": axis.get("value"),
                    "resource_units": axis.get("units"),
                    "resource_rank": axis.get("rank"),
                }
            )
    rows.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["resource_rank"] is None,
            row["resource_rank"] or 0,
            row["solver_short_name"],
        )
    )
    _require(len(rows) == 18, f"expected 18 G50 analysis variants, found {len(rows)}")
    _require(
        Counter(row["solver_family_id"] for row in rows)
        == {"dmrg": 4, "shci": 5, "trimci": 8, "ipie_afqmc": 1},
        "G50 variant family census changed",
    )
    return rows


def _zip_json(archive: Path, member: str) -> Any:
    with zipfile.ZipFile(archive) as handle:
        return json.loads(handle.read(member))


def _zip_csv(archive: Path, member: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(archive) as handle:
        text = handle.read(member).decode("utf-8").splitlines()
    return list(csv.DictReader(text))


def _off_diagonal_bounds(shared: np.ndarray) -> tuple[int, int]:
    indexes = np.triu_indices(len(shared), 1)
    return int(shared[indexes].min()), int(shared[indexes].max())


def run_outcome_blind_preflight(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Verify frozen G50 inputs and feature geometry without reading outcomes."""

    _require(
        not output_directory.exists(), f"preflight output exists: {output_directory}"
    )
    preregistration = load_preregistration(preregistration_path)
    input_hashes = verify_inputs(root, preregistration)

    feature_path = resolve_input_path(root, preregistration["inputs"]["feature_table"])
    metadata_path = resolve_input_path(
        root, preregistration["inputs"]["feature_metadata"]
    )
    taxonomy_path = resolve_input_path(
        root, preregistration["inputs"]["canonical_families"]
    )
    identifier_path = resolve_input_path(
        root, preregistration["inputs"]["identifier_screen"]
    )
    weight_path = resolve_input_path(
        root, preregistration["inputs"]["selection_weights"]
    )
    terminal_archive = resolve_input_path(
        root, preregistration["inputs"]["g50_terminal_intake"]
    )
    recovery_archive = resolve_input_path(
        root, preregistration["inputs"]["g50_trimci_recovery"]
    )
    catalog_path = resolve_input_path(
        root, preregistration["inputs"]["solver_family_catalog"]
    )

    features = pd.read_csv(feature_path, low_memory=False)
    metadata = pd.read_csv(metadata_path)
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    identifiers = json.loads(identifier_path.read_text(encoding="utf-8"))[
        "identifier_columns"
    ]
    weights = pd.read_csv(weight_path)
    _require(features.shape == (718, 580), f"feature shape changed: {features.shape}")
    _require(metadata.shape[0] == 580, "feature metadata row count changed")
    _require(
        set(map(str, metadata["column"])) == set(features.columns),
        "feature metadata/table columns differ",
    )
    _require(features["task_uuid"].is_unique, "feature task UUIDs are not unique")

    canonical = canonical_family_map(taxonomy)
    feature_tasks = set(map(str, features["task_uuid"]))
    _require(set(canonical) == feature_tasks, "taxonomy and feature tasks differ")
    _require(
        len(canonical) == 718 and len(set(canonical.values())) == 40,
        "canonical taxonomy census changed",
    )

    _require(
        len(weights) == 96 and weights["task_uuid"].is_unique,
        "selection weight row count changed",
    )
    _require(
        int(weights["selection_weight"].sum()) == 718,
        "selection weights do not sum to corpus",
    )
    _require(
        set(map(str, weights["task_uuid"])) <= feature_tasks,
        "selected task absent from feature table",
    )

    terminal_manifest = _zip_json(terminal_archive, "BASELINE_MANIFEST.json")
    contract_rows = terminal_manifest["rows"]
    contract_tasks = {str(row["task_uuid"]) for row in contract_rows}
    _require(len(contract_rows) == 384, "G50 terminal contract row count changed")
    _require(len(contract_tasks) == 96, "G50 terminal task count changed")
    _require(
        Counter(str(row["solver"]) for row in contract_rows)
        == {"dmrg": 96, "shci": 96, "trimci": 96, "ipie": 96},
        "G50 terminal solver scope changed",
    )
    _require(
        contract_tasks == set(map(str, weights["task_uuid"])),
        "G50 terminal tasks differ from binding selection",
    )

    recovery_manifest = _zip_json(recovery_archive, "RECOVERY_MANIFEST.json")
    recovery_matrix = _zip_csv(recovery_archive, "UNFOLDED_RUNG_MATRIX.csv")
    _require(
        recovery_manifest["status"] == "held_recovery_not_public_dashboard_input",
        "TrimCI recovery status changed",
    )
    _require(len(recovery_matrix) == 38 * 7, "TrimCI recovery matrix coverage changed")
    _require(
        {str(row["task_uuid"]) for row in recovery_matrix} <= contract_tasks,
        "TrimCI recovery task outside G50 scope",
    )

    policy = derive_feature_policy(metadata, identifiers)
    _require(len(policy["eligible"]) == 241, "eligible feature count changed")
    _require(len(policy["gauge"]) == 37, "gauge exclusion count changed")
    _require(len(policy["identifiers"]) == 11, "identifier exclusion count changed")
    _require(len(policy["selected"]) == 193, "selected feature count changed")
    _require(len(policy["jw"]) == 17, "JW feature count changed")

    geometry: dict[str, Any] = {}
    for solver_family, columns in policy["solver_family_columns"].items():
        geometry[solver_family] = {}
        for arm, arm_columns in (
            ("with_jw", columns),
            ("without_jw", sorted(set(columns) - set(policy["jw"]))),
        ):
            models = build_block_models(
                features,
                metadata,
                arm_columns,
                scaling=str(preregistration["feature_policy"]["scaling"]),
                variance_threshold=float(
                    preregistration["feature_policy"]["pca_variance_threshold"]
                ),
                universal_only=False,
            )
            distance, shared = block_aware_distance(len(features), models)
            minimum_shared, maximum_shared = _off_diagonal_bounds(shared)
            geometry[solver_family][arm] = {
                "input_columns": len(arm_columns),
                "exact_applicability_blocks": len(models),
                "retained_components": int(
                    sum(model.retained_components for model in models)
                ),
                "minimum_shared_blocks": minimum_shared,
                "maximum_shared_blocks": maximum_shared,
                "maximum_distance": float(distance.max()),
            }

    variants = g50_variant_rows(catalog_path)
    by_column = metadata.set_index("column").to_dict(orient="index")
    census_rows = []
    for column in policy["eligible"]:
        decision = "selected"
        if column in policy["gauge"]:
            decision = "excluded_gauge"
        elif column in policy["identifiers"]:
            decision = "excluded_identifier"
        census_rows.append(
            {
                "column": column,
                "logical_block": _logical_block(column, by_column[column]),
                "protocol": str(by_column[column]["protocol"]),
                "gauge_sensitive": column in policy["gauge"],
                "identifier_capable": column in policy["identifiers"],
                "decision": decision,
            }
        )

    report = {
        "artifact_id": "ml_g50_solver_families_outcome_blind_preflight_v1",
        "status": "pass",
        "protocol": PROTOCOL_ID,
        "scientific_outcomes_consumed": False,
        "model_fitted": False,
        "preregistration_sha256": sha256_file(preregistration_path),
        "input_hashes_verified": input_hashes,
        "panel": {
            "corpus_tasks": 718,
            "selected_tasks": 96,
            "canonical_families": 40,
            "terminal_contract_rows": 384,
            "analysis_solver_families": 4,
            "analysis_variants": 18,
        },
        "feature_census": {
            "eligible": len(policy["eligible"]),
            "gauge_excluded": len(policy["gauge"]),
            "identifier_excluded": len(policy["identifiers"]),
            "selected": len(policy["selected"]),
            "jw": len(policy["jw"]),
            "ipie_selected_after_prerequisite_exclusion": len(
                policy["solver_family_columns"]["ipie_afqmc"]
            ),
        },
        "geometry": geometry,
        "checks": {
            "all_input_hashes": True,
            "binding_selection_exact": True,
            "family_never_model_input": True,
            "feature_screen_exact": True,
            "g50_contract_exact": True,
            "no_cross_domain_imputation": True,
            "outcomes_not_consumed": True,
            "solver_family_catalog_exact": True,
            "trimci_censor_matrix_exact": True,
        },
    }

    output_directory.mkdir(parents=True)
    census_path = output_directory / "feature_census.csv"
    variants_path = output_directory / "solver_variants.json"
    report_path = output_directory / "preflight_report.json"
    stable_csv_dump(
        census_rows,
        [
            "column",
            "logical_block",
            "protocol",
            "gauge_sensitive",
            "identifier_capable",
            "decision",
        ],
        census_path,
    )
    stable_json_dump(variants, variants_path)
    stable_json_dump(report, report_path)
    stable_json_dump(
        {
            "artifact_id": "ml_g50_solver_families_preflight_manifest_v1",
            "files": [
                {"path": path.name, "sha256": sha256_file(path)}
                for path in (census_path, report_path, variants_path)
            ],
            "outcomes_consumed": False,
            "status": "pass",
        },
        output_directory / "artifact_manifest.json",
    )
    return report
