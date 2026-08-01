"""Outcome-blind contracts and deterministic tooling for ML-9A ISA."""

from __future__ import annotations

import json
from collections import Counter
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.core_set import (
    _logical_block,
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.g50_solver_families import derive_feature_policy


EXPECTED_FAMILY_VARIANTS = {
    "dmrg": 4,
    "ipie_afqmc": 1,
    "shci": 5,
    "trimci": 8,
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(root: Path, specification: Mapping[str, Any]) -> Path:
    local = specification.get("path")
    external = specification.get("external_path")
    _require(bool(local) != bool(external), "input must declare one path kind")
    return root / str(local) if local else Path(str(external))


def _verify_specification(
    root: Path, specification: Mapping[str, Any], label: str
) -> tuple[Path, str]:
    path = _resolve(root, specification)
    _require(path.is_file(), f"missing {label}: {path}")
    digest = sha256_file(path)
    _require(digest == str(specification["sha256"]), f"changed {label}: {path}")
    return path, digest


def _true(series: pd.Series) -> pd.Series:  # type: ignore[type-arg]
    return series.astype(str).str.lower().eq("true")


def _positive_or_nan(values: pd.Series) -> pd.Series:  # type: ignore[type-arg]
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.where(np.isfinite(numeric) & (numeric > 0))


def coordinate_preprocessing(
    panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Fit the frozen outcome-blind coordinate completion and scaling rule."""

    medians = panel.median(axis=0, skipna=True)
    _require(bool(medians.notna().all()), "a projection feature has no panel value")
    completed = panel.fillna(medians)
    q25 = completed.quantile(0.25, axis=0, interpolation="linear")
    q75 = completed.quantile(0.75, axis=0, interpolation="linear")
    iqr = q75 - q25
    mad = (completed - medians).abs().median(axis=0) * 1.4826
    standard_deviation = completed.std(axis=0, ddof=1)

    scales = _positive_or_nan(iqr)
    scale_source = pd.Series("iqr", index=panel.columns, dtype=object)
    use_mad = scales.isna() & _positive_or_nan(mad).notna()
    scales.loc[use_mad] = mad.loc[use_mad]
    scale_source.loc[use_mad] = "mad_x_1.4826"
    use_std = scales.isna() & _positive_or_nan(standard_deviation).notna()
    scales.loc[use_std] = standard_deviation.loc[use_std]
    scale_source.loc[use_std] = "sample_standard_deviation"
    use_unit = scales.isna()
    scales.loc[use_unit] = 1.0
    scale_source.loc[use_unit] = "unit_constant_fallback"

    transformed = ((completed - medians) / scales).clip(lower=-5.0, upper=5.0)
    _require(bool(np.isfinite(transformed.to_numpy()).all()), "non-finite transform")
    parameters = pd.DataFrame(
        {
            "median": medians,
            "q25_after_completion": q25,
            "q75_after_completion": q75,
            "iqr_after_completion": iqr,
            "mad_x_1_4826_after_completion": mad,
            "sample_standard_deviation_after_completion": standard_deviation,
            "scale": scales,
            "scale_source": scale_source,
            "constant_after_completion": completed.nunique(dropna=True).le(1),
        }
    )
    parameters.index.name = "column"
    return transformed, parameters


def apply_coordinate_preprocessing(
    values: pd.DataFrame, parameters: pd.DataFrame
) -> pd.DataFrame:
    """Apply a fitted ML-9A coordinate transform to arbitrary corpus rows."""

    columns = list(parameters.index)
    _require(columns == list(values.columns), "coordinate column order changed")
    completed = values.fillna(parameters["median"])
    transformed = ((completed - parameters["median"]) / parameters["scale"]).clip(
        lower=-5.0, upper=5.0
    )
    _require(
        bool(np.isfinite(transformed.to_numpy()).all()), "non-finite corpus transform"
    )
    return transformed


def _toolkit_lock(preregistration: Mapping[str, Any]) -> dict[str, Any]:
    specification = preregistration["toolkit"]
    versions = {
        name: importlib_metadata.version(name)
        for name in sorted(specification["runtime_dependencies"])
    }
    versions["instancespace"] = importlib_metadata.version("instancespace")
    expected = dict(specification["runtime_dependencies"])
    expected["instancespace"] = str(specification["version"])
    _require(versions == expected, "ML-9A runtime dependency versions changed")

    # Importing the top-level module exercises SciPy's compiled spatial stack.
    import instancespace  # noqa: PLC0415

    _require(Path(instancespace.__file__).is_file(), "instancespace import is invalid")
    return {
        "artifact_id": "ml9a_instancespace_toolkit_lock_v1",
        "distribution": "instancespace",
        "version": versions["instancespace"],
        "wheel_filename": specification["wheel_filename"],
        "wheel_sha256": specification["wheel_sha256"],
        "wheel_hash_verified_before_preregistration": True,
        "versions": versions,
        "import_path": str(Path(instancespace.__file__).resolve()),
        "status": "pass",
    }


def run_outcome_blind_preflight(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Verify ML-9A inputs without parsing the outcome table."""

    preregistration = _read_json(preregistration_path)
    _require(
        preregistration.get("artifact_id") == "ml9a_instance_space_preregistration_v1",
        "wrong ML-9A preregistration",
    )
    _require(
        preregistration.get("frozen_before_benchmark_fit") is True,
        "ML-9A preregistration is not frozen",
    )
    _require(
        preregistration["prior_exposure"]["ml9_benchmark_model_fitted"] is False,
        "ML-9A fit preceded the freeze",
    )

    order = preregistration["order"]
    order_hashes: dict[str, str] = {}
    for name, path_key, hash_key in (
        ("ml_goals", "ml_goals_external_path", "ml_goals_sha256"),
        (
            "pi_literature_memo",
            "pi_literature_memo_external_path",
            "pi_literature_memo_sha256",
        ),
    ):
        path = Path(order[path_key])
        _require(path.is_file(), f"missing binding order source: {path}")
        digest = sha256_file(path)
        _require(digest == order[hash_key], f"binding order source changed: {path}")
        order_hashes[name] = digest

    input_paths: dict[str, Path] = {}
    input_hashes: dict[str, str] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path, digest = _verify_specification(root, specification, name)
        input_paths[name] = path
        input_hashes[name] = digest

    # The outcome CSV is deliberately only byte-hashed above. Do not parse it here.
    metadata = pd.read_csv(input_paths["feature_metadata"])
    identifiers = _read_json(input_paths["identifier_screen"])["identifier_columns"]
    policy = derive_feature_policy(metadata, identifiers)
    selected = list(policy["selected"])
    _require(len(selected) == 193, "modeling feature count changed")
    _require(len(policy["gauge"]) == 37, "gauge exclusion count changed")
    _require(len(policy["identifiers"]) == 11, "identifier exclusion count changed")
    _require(len(policy["jw"]) == 17, "JW feature count changed")

    features = pd.read_csv(input_paths["feature_table"], low_memory=False)
    _require(len(features) == 718, "feature-table task count changed")
    _require(features["task_uuid"].is_unique, "duplicate feature-table task")
    _require(set(selected) <= set(features.columns), "selected feature is missing")
    feature_tasks = set(features["task_uuid"].astype(str))

    selection_manifest = _read_json(input_paths["selection_of_record_manifest"])
    _require(
        selection_manifest.get("binding_selection") is True, "selection not binding"
    )
    _require(selection_manifest.get("chosen_k") == 96, "selection size changed")
    panel = pd.read_csv(input_paths["panel_of_record"])
    _require(len(panel) == 96 and panel["task_uuid"].is_unique, "panel changed")
    _require(set(panel["task_uuid"]) <= feature_tasks, "panel task lacks features")
    _require(int(panel["selection_weight_609"].sum()) == 609, "panel weights changed")

    canonical_payload = _read_json(input_paths["canonical_families"])
    canonical = {
        str(row["task_uuid"]): str(row["canonical_family_recommended"])
        for row in canonical_payload["tasks"]
    }
    _require(len(canonical) == 718, "canonical-family task count changed")
    _require(set(canonical) == feature_tasks, "canonical-family coverage changed")
    _require(
        len(set(canonical.values())) == 40, "corpus canonical-family count changed"
    )
    _require(
        len({canonical[task] for task in panel["task_uuid"]}) == 23,
        "panel canonical-family count changed",
    )

    gradeability = pd.read_csv(input_paths["gradeability_census"])
    _require(
        len(gradeability) == 718 and gradeability["task_uuid"].is_unique,
        "gradeability census changed",
    )
    _require(
        set(gradeability["task_uuid"]) == feature_tasks, "gradeability coverage changed"
    )
    gradeable = _true(gradeability["gradeable_for_campaign_scoring"])
    _require(int((~gradeable).sum()) == 109, "non-gradeable census changed")

    variants = _read_json(input_paths["solver_variants"])
    _require(len(variants) == 18, "solver-variant count changed")
    _require(
        len({str(row["solver_variant_id"]) for row in variants}) == 18,
        "duplicate solver variant",
    )
    family_counts = Counter(str(row["solver_family_id"]) for row in variants)
    _require(
        dict(sorted(family_counts.items())) == EXPECTED_FAMILY_VARIANTS,
        "solver-family variant census changed",
    )

    feature_frame = features.set_index(features["task_uuid"].astype(str))[selected]
    feature_frame = feature_frame.apply(pd.to_numeric, errors="coerce")
    panel_ids = list(panel["task_uuid"].astype(str))
    panel_features = feature_frame.reindex(panel_ids)
    _require(panel_features.shape == (96, 193), "panel feature shape changed")
    missing_fraction = panel_features.isna().mean(axis=0)
    _, parameters = coordinate_preprocessing(panel_features)
    transformed_corpus = apply_coordinate_preprocessing(feature_frame, parameters)

    observed_panel = panel_features.notna().sum(axis=1)
    observed_corpus = feature_frame.notna().sum(axis=1)
    frozen_census = preregistration["feature_space"][
        "outcome_blind_census_frozen_before_fit"
    ]
    observed_census = {
        "panel_complete_columns": int((missing_fraction == 0).sum()),
        "panel_columns_below_20_percent_missing": int((missing_fraction < 0.2).sum()),
        "panel_columns_at_least_20_percent_missing": int(
            (missing_fraction >= 0.2).sum()
        ),
        "panel_all_missing_columns": int((missing_fraction == 1).sum()),
        "constant_after_completion": int(parameters["constant_after_completion"].sum()),
        "nonconstant_after_completion": int(
            (~parameters["constant_after_completion"]).sum()
        ),
        "minimum_observed_features_per_panel_task": int(observed_panel.min()),
        "minimum_observed_features_per_corpus_task": int(observed_corpus.min()),
    }
    _require(observed_census == frozen_census, "outcome-blind feature census changed")
    _require(transformed_corpus.shape == (718, 193), "corpus transform shape changed")

    metadata_rows = metadata.set_index("column").to_dict(orient="index")
    feature_rows: list[dict[str, Any]] = []
    for column in selected:
        row = metadata_rows[column]
        feature_rows.append(
            {
                "column": column,
                "logical_block": _logical_block(column, row),
                "protocol": str(row["protocol"]),
                "jw_feature": column in policy["jw"],
                "panel_observed": int(panel_features[column].notna().sum()),
                "panel_missing_fraction": float(missing_fraction[column]),
                "completion_median": float(parameters.loc[column, "median"]),
                "scale": float(parameters.loc[column, "scale"]),
                "scale_source": str(parameters.loc[column, "scale_source"]),
                "constant_after_completion": bool(
                    parameters.loc[column, "constant_after_completion"]
                ),
                "projection_candidate": True,
                "later_feature_eligible": True,
            }
        )

    toolkit = _toolkit_lock(preregistration)
    checks = {
        "binding_order_hashes": True,
        "all_input_hashes": True,
        "outcome_table_hash_only_not_parsed": True,
        "binding_panel_exact": True,
        "corpus_718_exact": True,
        "panel_96_exact": True,
        "corpus_canonical_families_40_exact": True,
        "panel_canonical_families_23_exact": True,
        "variants_18_exact": True,
        "solver_families_4_exact": True,
        "gradeability_609_109_exact": True,
        "modeling_features_193_exact": True,
        "jw_features_17_eligible": True,
        "feature_only_census_exact": True,
        "coordinate_transform_finite": True,
        "toolkit_version_and_import": True,
        "model_not_fitted": True,
    }
    report = {
        "artifact_id": "ml9a_outcome_blind_preflight_v1",
        "status": "pass",
        "protocol": "ml9a-instance-space-v1",
        "preregistration_sha256": sha256_file(preregistration_path),
        "order_hashes": order_hashes,
        "input_hashes_verified": input_hashes,
        "checks": checks,
        "census": {
            "corpus_tasks": 718,
            "labeled_panel_tasks": 96,
            "corpus_canonical_task_families": 40,
            "panel_canonical_task_families": 23,
            "gradeable_tasks": int(gradeable.sum()),
            "non_gradeable_coverage_points": int((~gradeable).sum()),
            "observed_variants": 18,
            "solver_families": 4,
            "selection_weight_sum": 609,
            "modeling_features": 193,
            "jw_features": 17,
            **observed_census,
        },
        "toolkit": toolkit,
        "scientific_outcomes_consumed": False,
        "model_fitted": False,
    }

    output_directory.mkdir(parents=True, exist_ok=True)
    stable_csv_dump(
        feature_rows,
        [
            "column",
            "logical_block",
            "protocol",
            "jw_feature",
            "panel_observed",
            "panel_missing_fraction",
            "completion_median",
            "scale",
            "scale_source",
            "constant_after_completion",
            "projection_candidate",
            "later_feature_eligible",
        ],
        output_directory / "feature_census.csv",
    )
    stable_json_dump(toolkit, output_directory / "toolkit_lock.json")
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
        "artifact_id": "ml9a_outcome_blind_preflight_manifest_v1",
        "status": "pass",
        "preregistration_sha256": report["preregistration_sha256"],
        "scientific_outcomes_consumed": False,
        "model_fitted": False,
        "files": files,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return report
