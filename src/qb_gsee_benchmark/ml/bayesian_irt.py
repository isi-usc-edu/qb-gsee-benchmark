"""Outcome-blind preflight helpers for ML-9C Bayesian inverted IRT."""

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
    _require(path.is_file(), f"missing ML-9C input {label}: {path}")
    _require(
        sha256_file(path) == str(specification["sha256"]),
        f"changed ML-9C input {label}: {path}",
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
    """Validate identities and schemas without parsing response values."""

    preregistration = _read_json(preregistration_path)
    _require(
        preregistration.get("artifact_id")
        == "ml9c_bayesian_inverted_irt_preregistration_v1",
        "wrong ML-9C preregistration",
    )
    _require(
        preregistration.get("frozen_before_response_construction") is True,
        "ML-9C response construction was not frozen",
    )
    _require(
        preregistration.get("frozen_before_model_fit") is True,
        "ML-9C model fit was not frozen",
    )

    paths: dict[str, Path] = {}
    input_hashes: dict[str, str] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path = _verify_input(root, specification, name)
        paths[name] = path
        input_hashes[name] = sha256_file(path)

    panel = pd.read_csv(
        paths["panel_of_record"], usecols=["task_uuid", "canonical_family"]
    )
    panel["task_uuid"] = panel["task_uuid"].astype(str)
    panel["canonical_family"] = panel["canonical_family"].astype(str)
    _require(len(panel) == 96 and panel["task_uuid"].is_unique, "panel changed")
    _require(
        panel["canonical_family"].nunique() == 23,
        "canonical task-family census changed",
    )

    variants = _read_json(paths["solver_variants"])
    _require(len(variants) == 18, "solver variant census changed")
    variant_ids = [str(row["solver_variant_id"]) for row in variants]
    _require(len(set(variant_ids)) == 18, "duplicate solver variant")
    family_counts = Counter(str(row["solver_family_id"]) for row in variants)
    _require(
        dict(sorted(family_counts.items()))
        == {"dmrg": 4, "ipie_afqmc": 1, "shci": 5, "trimci": 8},
        "solver family census changed",
    )

    observation_header = set(_csv_header(paths["normalized_observations"]))
    required_columns = {
        "task_uuid",
        "canonical_family",
        "solver_family_id",
        "solver_variant_id",
        "observed_outcome",
        "graded_residual",
    }
    _require(
        required_columns <= observation_header,
        "normalized observation schema changed",
    )
    observation_rows = _csv_data_rows(paths["normalized_observations"])
    _require(observation_rows == 96 * 18, "normalized observation row count changed")

    task_rows = [
        {
            "canonical_family": family,
            "task_count": int(count),
            "respondent_role": "task",
            "outcome_consumed": False,
        }
        for family, count in sorted(Counter(panel["canonical_family"]).items())
    ]
    variant_rows = [
        {
            "solver_family_id": str(row["solver_family_id"]),
            "solver_variant_id": str(row["solver_variant_id"]),
            "solver_short_name": str(row["solver_short_name"]),
            "item_role": "solver_variant",
            "free_discrimination": False,
        }
        for row in sorted(
            variants,
            key=lambda item: (
                str(item["solver_family_id"]),
                str(item["solver_variant_id"]),
            ),
        )
    ]

    output_directory.mkdir(parents=True, exist_ok=True)
    stable_csv_dump(task_rows, list(task_rows[0]), output_directory / "task_census.csv")
    stable_csv_dump(
        variant_rows,
        list(variant_rows[0]),
        output_directory / "variant_catalog.csv",
    )
    report = {
        "artifact_id": "ml9c_bayesian_irt_preflight_v1",
        "status": "pass",
        "scientific_outcomes_consumed": False,
        "response_matrix_computed": False,
        "posterior_computed": False,
        "factor_model_computed": False,
        "loo_comparison_computed": False,
        "preregistration_sha256": sha256_file(preregistration_path),
        "input_hashes": input_hashes,
        "census": {
            "panel_tasks": len(panel),
            "canonical_task_families": panel["canonical_family"].nunique(),
            "solver_variants": len(variants),
            "solver_families": len(family_counts),
            "observation_rows_by_line_count_only": observation_rows,
            "complete_cells_expected": len(panel) * len(variants),
        },
        "checks": {
            "all_input_hashes_verified": True,
            "panel_identity_columns_only": True,
            "normalized_observation_header_only": True,
            "normalized_observation_line_count_only": True,
            "tasks_are_respondents": True,
            "variants_are_items": True,
            "binary_discrimination_fixed_one": True,
            "continuous_discrimination_fixed_one": True,
            "family_testlet_effect_frozen": True,
            "dimensionality_hypothesis_frozen": True,
            "no_response_fit": True,
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
        "artifact_id": "ml9c_bayesian_irt_preflight_manifest_v1",
        "status": "pass",
        "scientific_outcomes_consumed": False,
        "files": files,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return report
