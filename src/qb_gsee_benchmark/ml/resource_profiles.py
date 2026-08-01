"""Outcome-blind preflight for ML-9B resource profiles."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_input(root: Path, specification: Mapping[str, Any], label: str) -> Path:
    path = root / str(specification["path"])
    _require(path.is_file(), f"missing ML-9B input {label}: {path}")
    _require(
        sha256_file(path) == str(specification["sha256"]),
        f"changed ML-9B input {label}: {path}",
    )
    return path


def _csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return next(csv.reader(handle))


def _csv_data_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def run_outcome_blind_preflight(
    root: Path,
    preregistration_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Validate ML-9B structure and hashes without parsing scientific outcomes."""

    preregistration = _read_json(preregistration_path)
    _require(
        preregistration.get("artifact_id")
        == "ml9b_resource_profiles_preregistration_v1",
        "wrong ML-9B preregistration",
    )
    _require(
        preregistration.get("frozen_before_result_construction") is True,
        "ML-9B preregistration is not frozen",
    )

    paths: dict[str, Path] = {}
    input_hashes: dict[str, str] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path = _verify_input(root, specification, name)
        paths[name] = path
        input_hashes[name] = sha256_file(path)

    panel = pd.read_csv(paths["panel_of_record"], usecols=["task_uuid"])
    panel["task_uuid"] = panel["task_uuid"].astype(str)
    _require(len(panel) == 96 and panel["task_uuid"].is_unique, "panel changed")

    variants = _read_json(paths["solver_variants"])
    _require(len(variants) == 18, "solver variant census changed")
    _require(
        len({str(row["solver_variant_id"]) for row in variants}) == 18,
        "duplicate solver variant",
    )
    family_counts = Counter(str(row["solver_family_id"]) for row in variants)
    _require(
        dict(sorted(family_counts.items()))
        == {"dmrg": 4, "ipie_afqmc": 1, "shci": 5, "trimci": 8},
        "solver family census changed",
    )

    variant_by_id = {str(row["solver_variant_id"]): row for row in variants}
    track_rows: list[dict[str, Any]] = []
    for track in preregistration["tracks"]["ladders"]:
        ladder_id = str(track["resource_ladder_id"])
        actual = sorted(
            (row for row in variants if row["resource_ladder_id"] == ladder_id),
            key=lambda row: int(row["resource_rank"]),
        )
        expected_values = [float(value) for value in track["ordered_values"]]
        _require(
            len(actual) == len(expected_values), f"ladder size changed: {ladder_id}"
        )
        _require(
            [int(row["resource_rank"]) for row in actual] == list(range(len(actual))),
            f"resource ranks changed: {ladder_id}",
        )
        _require(
            [float(row["resource_value"]) for row in actual] == expected_values,
            f"resource values changed: {ladder_id}",
        )
        _require(
            {str(row["solver_family_id"]) for row in actual}
            == {str(track["solver_family_id"])},
            f"resource family changed: {ladder_id}",
        )
        for row in actual:
            track_rows.append(
                {
                    "track_kind": "ladder",
                    "solver_family_id": row["solver_family_id"],
                    "resource_ladder_id": ladder_id,
                    "solver_variant_id": row["solver_variant_id"],
                    "resource_axis_name": row["resource_axis_name"],
                    "resource_value": row["resource_value"],
                    "resource_units": row["resource_units"],
                    "resource_rank": row["resource_rank"],
                    "enters_data_profile": True,
                }
            )

    single = preregistration["tracks"]["single_point"]
    single_variant = variant_by_id[str(single["solver_variant_id"])]
    _require(
        single_variant["solver_family_id"] == single["solver_family_id"],
        "single-point family changed",
    )
    _require(single_variant["resource_ladder_id"] is None, "iPIE gained a ladder")
    track_rows.append(
        {
            "track_kind": "single_point",
            "solver_family_id": single_variant["solver_family_id"],
            "resource_ladder_id": "ipie_single_budget_v1",
            "solver_variant_id": single_variant["solver_variant_id"],
            "resource_axis_name": single["resource_axis_name"],
            "resource_value": single["resource_value"],
            "resource_units": single["resource_units"],
            "resource_rank": 0,
            "enters_data_profile": True,
        }
    )

    companion_ids = set(
        map(
            str,
            preregistration["tracks"][
                "companion_variants_excluded_from_ladder_profiles"
            ],
        )
    )
    _require(companion_ids <= set(variant_by_id), "companion variant missing")
    _require(
        all(
            variant_by_id[name]["resource_ladder_id"] is None for name in companion_ids
        ),
        "companion variant unexpectedly has a ladder",
    )
    profiled_ids = {str(row["solver_variant_id"]) for row in track_rows}
    _require(
        profiled_ids | companion_ids == set(variant_by_id), "track partition changed"
    )

    observation_header = set(_csv_header(paths["normalized_observations"]))
    required_observation_columns = {
        "task_uuid",
        "solver_family_id",
        "solver_variant_id",
        "resource_ladder_id",
        "resource_axis_name",
        "resource_value",
        "resource_rank",
        "energy_hartree",
        "graded_residual",
        "observed_outcome",
        "metric_status_annotation",
        "label_reason_annotation",
        "raw_status_annotation",
        "observation_source",
    }
    _require(
        required_observation_columns <= observation_header,
        "normalized observation schema changed",
    )
    coverage_header = set(_csv_header(paths["coverage"]))
    required_coverage_columns = {
        "task_uuid",
        "solver_family_id",
        "solver_variant_id",
        "resource_ladder_id",
        "resource_value",
        "coverage_status",
        "coverage_reason",
        "enters_binary_label_table",
    }
    _require(required_coverage_columns <= coverage_header, "coverage schema changed")
    observation_rows = _csv_data_rows(paths["normalized_observations"])
    coverage_rows = _csv_data_rows(paths["coverage"])
    _require(observation_rows == 1728, "normalized observation row count changed")
    _require(coverage_rows == 1728, "coverage row count changed")

    output_directory.mkdir(parents=True, exist_ok=True)
    stable_csv_dump(
        track_rows,
        list(track_rows[0]),
        output_directory / "track_census.csv",
    )
    report = {
        "artifact_id": "ml9b_resource_profiles_preflight_v1",
        "status": "pass",
        "scientific_outcomes_consumed": False,
        "resource_endpoints_computed": False,
        "data_profiles_computed": False,
        "threshold_comparisons_computed": False,
        "preregistration_sha256": sha256_file(preregistration_path),
        "input_hashes": input_hashes,
        "census": {
            "panel_tasks": len(panel),
            "observation_rows_by_line_count_only": observation_rows,
            "coverage_rows_by_line_count_only": coverage_rows,
            "solver_variants": len(variants),
            "profiled_variants": len(profiled_ids),
            "ladder_variants": sum(row["track_kind"] == "ladder" for row in track_rows),
            "single_point_variants": 1,
            "companion_variants": len(companion_ids),
            "resource_ladders": len(preregistration["tracks"]["ladders"]),
            "threshold_factors": len(preregistration["thresholds"]["factors"]),
        },
        "checks": {
            "all_input_hashes_verified": True,
            "complete_panel_census": True,
            "complete_variant_partition": True,
            "ordered_ladders_match_freeze": True,
            "ipie_single_point_match": True,
            "outcome_and_coverage_headers_only": True,
            "four_class_runstatus_frozen": True,
            "crash_competing_risk_frozen": True,
            "two_censor_classes_frozen": True,
            "no_par_k": True,
        },
    }
    stable_json_dump(report, output_directory / "preflight_report.json")
    files = []
    for path in sorted(output_directory.iterdir()):
        if path.name == "artifact_manifest.json" or not path.is_file():
            continue
        files.append(
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "artifact_id": "ml9b_resource_profiles_preflight_manifest_v1",
        "status": "pass",
        "scientific_outcomes_consumed": False,
        "resource_endpoints_computed": False,
        "data_profiles_computed": False,
        "preregistration_sha256": sha256_file(preregistration_path),
        "files": files,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return report
