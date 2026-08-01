"""Deterministic ML-9B censored resource-to-solution finalization."""

from __future__ import annotations

import json
import math
import platform
from collections import Counter
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)


THRESHOLD_FACTORS = (0.5, 1.0, 2.0)
PROFILE_TRACKS = (
    "g50_dmrg_bond_dimension_v1",
    "g50_shci_orbopt_variational_eps_var_v1",
    "g50_trimci_target_determinants_v1",
    "ipie_single_budget_v1",
)
PREFLIGHT_MANIFEST_SHA256 = (
    "9665fbad2e352b8d06aa606840b67c9f977a90211e9298ec83aa43001ed9d137"
)
SCHEMA_BINDING_SHA256 = (
    "ab1038812a7c66b6721aa218a2fda41a9602bd18a5c6b80775c10c33c1c059fb"
)


@dataclass(frozen=True)
class PreparedResourceData:
    preregistration: dict[str, Any]
    observations: pd.DataFrame
    track_variants: dict[str, list[str]]
    track_metadata: dict[str, dict[str, Any]]
    companion_variants: tuple[str, ...]
    panel_ids: tuple[str, ...]
    input_hashes: dict[str, str]


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


def _true(series: pd.Series) -> pd.Series:  # type: ignore[type-arg]
    return series.astype(str).str.lower().eq("true")


def _effort_multiplier(track_id: str, resource_value: float) -> float:
    if track_id == "g50_dmrg_bond_dimension_v1":
        return resource_value / 256.0
    if track_id == "g50_shci_orbopt_variational_eps_var_v1":
        return 0.0002 / resource_value
    if track_id == "g50_trimci_target_determinants_v1":
        return resource_value / 100000.0
    if track_id == "ipie_single_budget_v1":
        return 1.0
    raise AssertionError(f"unknown ML-9B track: {track_id}")


def prepare_resource_data(
    root: Path,
    preregistration_path: Path,
    schema_binding_path: Path,
) -> PreparedResourceData:
    """Load accepted ML-9B observations and enforce all frozen bindings."""

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
    preflight_path = (
        root / "analysis/ml9_resource_profiles/preflight_v1/artifact_manifest.json"
    )
    _require(
        sha256_file(preflight_path) == PREFLIGHT_MANIFEST_SHA256, "preflight changed"
    )
    preflight = _read_json(preflight_path)
    _require(preflight.get("status") == "pass", "ML-9B preflight did not pass")
    _require(
        preflight.get("scientific_outcomes_consumed") is False,
        "ML-9B preflight consumed outcomes",
    )
    _require(
        preflight["preregistration_sha256"] == sha256_file(preregistration_path),
        "ML-9B preregistration/preflight binding changed",
    )
    _require(
        sha256_file(schema_binding_path) == SCHEMA_BINDING_SHA256,
        "ML-9B raw-failure schema binding changed",
    )
    schema_binding = _read_json(schema_binding_path)
    _require(
        schema_binding.get("frozen_before_result_construction") is True,
        "ML-9B raw-failure binding is not frozen",
    )
    _require(
        schema_binding["parent_preregistration"]["sha256"]
        == sha256_file(preregistration_path),
        "ML-9B raw-failure/preregistration binding changed",
    )

    paths: dict[str, Path] = {}
    input_hashes: dict[str, str] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        path = _verify_input(root, specification, name)
        paths[name] = path
        input_hashes[name] = sha256_file(path)

    panel = pd.read_csv(paths["panel_of_record"], usecols=["task_uuid"])
    panel_ids = tuple(panel["task_uuid"].astype(str))
    _require(len(panel_ids) == 96 and len(set(panel_ids)) == 96, "panel changed")
    variants = _read_json(paths["solver_variants"])
    variant_by_id = {str(row["solver_variant_id"]): row for row in variants}
    _require(len(variant_by_id) == 18, "variant census changed")

    track_variants: dict[str, list[str]] = {}
    track_metadata: dict[str, dict[str, Any]] = {}
    for track in preregistration["tracks"]["ladders"]:
        track_id = str(track["resource_ladder_id"])
        members = sorted(
            (row for row in variants if row["resource_ladder_id"] == track_id),
            key=lambda row: int(row["resource_rank"]),
        )
        track_variants[track_id] = [str(row["solver_variant_id"]) for row in members]
        track_metadata[track_id] = {
            "track_kind": "ladder",
            "solver_family_id": str(track["solver_family_id"]),
            "resource_axis_name": str(track["resource_axis_name"]),
            "resource_units": str(track["resource_units"]),
        }
    single = preregistration["tracks"]["single_point"]
    single_id = str(single["solver_variant_id"])
    track_variants["ipie_single_budget_v1"] = [single_id]
    track_metadata["ipie_single_budget_v1"] = {
        "track_kind": "single_point",
        "solver_family_id": str(single["solver_family_id"]),
        "resource_axis_name": str(single["resource_axis_name"]),
        "resource_units": str(single["resource_units"]),
    }
    companion_variants = tuple(
        map(
            str,
            preregistration["tracks"][
                "companion_variants_excluded_from_ladder_profiles"
            ],
        )
    )

    observations = pd.read_csv(paths["normalized_observations"], low_memory=False)
    coverage = pd.read_csv(paths["coverage"], low_memory=False)
    for frame in (observations, coverage):
        frame["task_uuid"] = frame["task_uuid"].astype(str)
        frame["solver_variant_id"] = frame["solver_variant_id"].astype(str)
    _require(len(observations) == len(coverage) == 1728, "accepted cell census changed")
    _require(
        not observations.duplicated(["task_uuid", "solver_variant_id"]).any(),
        "duplicate normalized observation",
    )
    _require(
        not coverage.duplicated(["task_uuid", "solver_variant_id"]).any(),
        "duplicate coverage row",
    )
    observations = observations.merge(
        coverage[
            [
                "task_uuid",
                "solver_variant_id",
                "coverage_status",
                "coverage_reason",
                "enters_binary_label_table",
            ]
        ],
        on=["task_uuid", "solver_variant_id"],
        how="left",
        validate="one_to_one",
    )
    _require(
        bool(observations["coverage_status"].notna().all()), "coverage join changed"
    )
    _require(
        bool(_true(observations["enters_binary_label_table"]).all()),
        "label table changed",
    )
    _require(
        set(observations["task_uuid"]) == set(panel_ids), "observation panel changed"
    )
    _require(
        set(observations["solver_variant_id"]) == set(variant_by_id),
        "observation variants changed",
    )

    observations["energy_numeric"] = pd.to_numeric(
        observations["energy_hartree"], errors="coerce"
    )
    observations["residual_numeric"] = pd.to_numeric(
        observations["graded_residual"], errors="coerce"
    )
    observations["finite_result"] = np.isfinite(
        observations["energy_numeric"]
    ) & np.isfinite(observations["residual_numeric"])
    raw_status = (
        observations["raw_status_annotation"].fillna("").astype(str).str.lower()
    )
    observations["terminal_status"] = np.where(
        (~observations["finite_result"]) & raw_status.eq("failed"),
        "crash",
        np.where(
            (~observations["finite_result"]) & raw_status.eq("timeout"),
            "timeout",
            None,
        ),
    )
    observations["attempted"] = (
        observations["finite_result"] | observations["terminal_status"].notna()
    )
    _require(
        not observations.loc[observations["attempted"], "raw_status_annotation"]
        .isna()
        .any(),
        "attempted row lacks accepted raw status",
    )

    variant_to_track = {
        variant: track_id
        for track_id, members in track_variants.items()
        for variant in members
    }
    observations["profile_track_id"] = observations["solver_variant_id"].map(
        variant_to_track
    )
    observations["track_kind"] = np.where(
        observations["profile_track_id"].notna(),
        observations["profile_track_id"].map(
            {
                track_id: metadata["track_kind"]
                for track_id, metadata in track_metadata.items()
            }
        ),
        "companion",
    )
    _require(
        set(
            observations.loc[
                observations["track_kind"] == "companion", "solver_variant_id"
            ]
        )
        == set(companion_variants),
        "companion partition changed",
    )
    observations["profile_resource_rank"] = pd.to_numeric(
        observations["resource_rank"], errors="coerce"
    )
    observations.loc[
        observations["profile_track_id"].eq("ipie_single_budget_v1"),
        "profile_resource_rank",
    ] = 0
    observations["profile_resource_value"] = pd.to_numeric(
        observations["resource_value"], errors="coerce"
    )
    observations.loc[
        observations["profile_track_id"].eq("ipie_single_budget_v1"),
        "profile_resource_value",
    ] = 1.0
    observations["effort_multiplier"] = np.nan
    for track_id in PROFILE_TRACKS:
        mask = observations["profile_track_id"].eq(track_id)
        observations.loc[mask, "effort_multiplier"] = observations.loc[
            mask, "profile_resource_value"
        ].map(lambda value: _effort_multiplier(track_id, float(value)))
    _require(
        bool(
            np.isfinite(
                observations.loc[
                    observations["profile_track_id"].notna(), "effort_multiplier"
                ]
            ).all()
        ),
        "non-finite resource effort",
    )

    return PreparedResourceData(
        preregistration=preregistration,
        observations=observations,
        track_variants=track_variants,
        track_metadata=track_metadata,
        companion_variants=companion_variants,
        panel_ids=panel_ids,
        input_hashes=input_hashes,
    )


def build_attempt_coverage(data: PreparedResourceData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in data.observations.sort_values(
        ["task_uuid", "solver_variant_id"]
    ).itertuples():
        rows.append(
            {
                "task_uuid": row.task_uuid,
                "canonical_family": row.canonical_family,
                "solver_family_id": row.solver_family_id,
                "solver_variant_id": row.solver_variant_id,
                "profile_track_id": row.profile_track_id,
                "track_kind": row.track_kind,
                "resource_axis_name": row.resource_axis_name,
                "resource_value": row.profile_resource_value,
                "resource_units": row.resource_units,
                "resource_rank": row.profile_resource_rank,
                "effort_multiplier": row.effort_multiplier,
                "finite_result": bool(row.finite_result),
                "accepted_raw_status": row.raw_status_annotation,
                "terminal_status_if_no_result": row.terminal_status,
                "attempted": bool(row.attempted),
                "attempt_evidence": (
                    "finite_result"
                    if row.finite_result
                    else ("terminal_no_result" if row.attempted else "not_observed")
                ),
                "coverage_status": row.coverage_status,
                "coverage_reason": row.coverage_reason,
                "label_of_record_mutated": False,
                "output_kind": "descriptive",
            }
        )
    return rows


def build_runstatus(data: PreparedResourceData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ordered = data.observations.sort_values(["task_uuid", "solver_variant_id"])
    for factor in THRESHOLD_FACTORS:
        for row in ordered.itertuples():
            if not row.attempted:
                continue
            if row.finite_result:
                status = (
                    "ok" if float(row.residual_numeric) <= factor else "accuracy_miss"
                )
            else:
                status = str(row.terminal_status)
            _require(
                status in {"ok", "accuracy_miss", "timeout", "crash"},
                "runstatus vocabulary changed",
            )
            rows.append(
                {
                    "task_uuid": row.task_uuid,
                    "canonical_family": row.canonical_family,
                    "solver_family_id": row.solver_family_id,
                    "solver_variant_id": row.solver_variant_id,
                    "profile_track_id": row.profile_track_id,
                    "track_kind": row.track_kind,
                    "threshold_factor": factor,
                    "runstatus": status,
                    "graded_residual": row.residual_numeric,
                    "accepted_raw_status": row.raw_status_annotation,
                    "coverage_status": row.coverage_status,
                    "coverage_reason": row.coverage_reason,
                    "crash_is_competing_risk": status == "crash",
                    "label_of_record_mutated": False,
                    "output_kind": "descriptive",
                }
            )
    return rows


def _status_for_factor(group: pd.DataFrame, factor: float) -> pd.Series:  # type: ignore[type-arg]
    status = pd.Series(index=group.index, dtype=object)
    finite = group["finite_result"].astype(bool)
    status.loc[finite] = np.where(
        group.loc[finite, "residual_numeric"].to_numpy(dtype=float) <= factor,
        "ok",
        "accuracy_miss",
    )
    status.loc[~finite & group["terminal_status"].eq("timeout")] = "timeout"
    status.loc[~finite & group["terminal_status"].eq("crash")] = "crash"
    return status


def build_resource_endpoints(data: PreparedResourceData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    observations = data.observations.loc[
        data.observations["profile_track_id"].notna()
    ].copy()
    for factor in THRESHOLD_FACTORS:
        for track_id in PROFILE_TRACKS:
            metadata = data.track_metadata[track_id]
            track = observations.loc[observations["profile_track_id"].eq(track_id)]
            for task_uuid in data.panel_ids:
                group = track.loc[track["task_uuid"].eq(task_uuid)].sort_values(
                    "profile_resource_rank"
                )
                _require(
                    len(group) == len(data.track_variants[track_id]),
                    "track row missing",
                )
                status = _status_for_factor(group, factor)
                solution = group.loc[status.eq("ok")]
                attempted = group.loc[group["attempted"]]
                resource_evidenced = group.loc[
                    group["finite_result"]
                    | group["coverage_status"].isin(
                        {
                            "observed_rung",
                            "missing_attempted_rung",
                            "observed_checkpoint",
                            "observed_parent_completed_below_cap",
                            "observed_terminal",
                            "terminal_contract",
                        }
                    )
                ]
                first_solution = solution.iloc[0] if len(solution) else None
                terminal = attempted.iloc[-1] if len(attempted) else None
                last_resource = (
                    resource_evidenced.iloc[-1] if len(resource_evidenced) else None
                )
                if first_solution is not None:
                    event_type = "solution"
                    endpoint = first_solution
                elif terminal is None:
                    event_type = "no_attempt_evidence"
                    endpoint = None
                elif str(terminal["raw_status_annotation"]).lower() == "failed":
                    event_type = "competing_risk_crash"
                    endpoint = last_resource
                elif str(terminal["raw_status_annotation"]).lower() == "timeout":
                    event_type = "right_censored_walltime"
                    endpoint = last_resource
                else:
                    event_type = "right_censored_ladder_exhaustion"
                    endpoint = last_resource
                canonical_family = str(group.iloc[0]["canonical_family"])
                rows.append(
                    {
                        "task_uuid": task_uuid,
                        "canonical_family": canonical_family,
                        "solver_family_id": metadata["solver_family_id"],
                        "profile_track_id": track_id,
                        "track_kind": metadata["track_kind"],
                        "resource_axis_name": metadata["resource_axis_name"],
                        "resource_units": metadata["resource_units"],
                        "threshold_factor": factor,
                        "event_type": event_type,
                        "solution_observed": event_type == "solution",
                        "crash_competing_risk": event_type == "competing_risk_crash",
                        "right_censored": event_type.startswith("right_censored"),
                        "censor_class": (
                            event_type
                            if event_type.startswith("right_censored")
                            else None
                        ),
                        "endpoint_resource_rank": (
                            int(endpoint["profile_resource_rank"])
                            if endpoint is not None
                            else None
                        ),
                        "endpoint_resource_value": (
                            float(endpoint["profile_resource_value"])
                            if endpoint is not None
                            else None
                        ),
                        "endpoint_effort_multiplier": (
                            float(endpoint["effort_multiplier"])
                            if endpoint is not None
                            else None
                        ),
                        "terminal_attempt_resource_rank": (
                            int(terminal["profile_resource_rank"])
                            if terminal is not None
                            else None
                        ),
                        "terminal_accepted_raw_status": (
                            terminal["raw_status_annotation"]
                            if terminal is not None
                            else None
                        ),
                        "terminal_coverage_reason": (
                            terminal["coverage_reason"]
                            if terminal is not None
                            else None
                        ),
                        "terminal_observation_source": (
                            terminal["observation_source"]
                            if terminal is not None
                            else None
                        ),
                        "attempted_variant_count": int(group["attempted"].sum()),
                        "finite_result_count": int(group["finite_result"].sum()),
                        "monotonic_repair_applied": False,
                        "label_of_record_mutated": False,
                        "output_kind": "descriptive",
                    }
                )
    return rows


def build_data_profiles(
    data: PreparedResourceData,
    endpoints: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    endpoint_frame = pd.DataFrame(endpoints)
    rows: list[dict[str, Any]] = []
    denominator = len(data.panel_ids)
    for factor in THRESHOLD_FACTORS:
        for track_id in PROFILE_TRACKS:
            track_endpoints = endpoint_frame.loc[
                endpoint_frame["threshold_factor"].eq(factor)
                & endpoint_frame["profile_track_id"].eq(track_id)
            ]
            variants = data.track_variants[track_id]
            for rank, variant_id in enumerate(variants):
                variant = data.observations.loc[
                    data.observations["solver_variant_id"].eq(variant_id)
                ].iloc[0]
                solved = track_endpoints["solution_observed"] & track_endpoints[
                    "endpoint_resource_rank"
                ].le(rank)
                rows.append(
                    {
                        "solver_family_id": data.track_metadata[track_id][
                            "solver_family_id"
                        ],
                        "profile_track_id": track_id,
                        "track_kind": data.track_metadata[track_id]["track_kind"],
                        "threshold_factor": factor,
                        "resource_axis_name": data.track_metadata[track_id][
                            "resource_axis_name"
                        ],
                        "resource_units": data.track_metadata[track_id][
                            "resource_units"
                        ],
                        "resource_rank": rank,
                        "resource_value": float(variant["profile_resource_value"]),
                        "effort_multiplier": float(variant["effort_multiplier"]),
                        "tasks_solved_cumulative": int(solved.sum()),
                        "panel_tasks": denominator,
                        "fraction_solved_cumulative": float(solved.sum() / denominator),
                        "selection_weighted": False,
                        "monotonic_repair_applied": False,
                        "output_kind": "descriptive",
                    }
                )
    return rows


def build_threshold_stability(
    profiles: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    frame = pd.DataFrame(profiles)
    endpoint = (
        frame.sort_values("resource_rank")
        .groupby(["threshold_factor", "profile_track_id"], sort=True)
        .tail(1)
    )
    primary = endpoint.loc[endpoint["threshold_factor"].eq(1.0)].set_index(
        "profile_track_id"
    )["fraction_solved_cumulative"]
    rows: list[dict[str, Any]] = []
    for factor in (0.5, 2.0):
        comparison = endpoint.loc[endpoint["threshold_factor"].eq(factor)].set_index(
            "profile_track_id"
        )["fraction_solved_cumulative"]
        correlation = spearmanr(
            [float(primary[track]) for track in PROFILE_TRACKS],
            [float(comparison[track]) for track in PROFILE_TRACKS],
        ).statistic
        rank_status = (
            "estimated" if math.isfinite(float(correlation)) else "undefined_ties"
        )
        for track_id in PROFILE_TRACKS:
            reference_profile = frame.loc[
                frame["threshold_factor"].eq(1.0)
                & frame["profile_track_id"].eq(track_id)
            ].sort_values("resource_rank")
            comparison_profile = frame.loc[
                frame["threshold_factor"].eq(factor)
                & frame["profile_track_id"].eq(track_id)
            ].sort_values("resource_rank")
            difference = comparison_profile["fraction_solved_cumulative"].to_numpy(
                dtype=float
            ) - reference_profile["fraction_solved_cumulative"].to_numpy(dtype=float)
            rows.append(
                {
                    "profile_track_id": track_id,
                    "solver_family_id": comparison_profile.iloc[0]["solver_family_id"],
                    "comparison_threshold_factor": factor,
                    "reference_threshold_factor": 1.0,
                    "endpoint_fraction_comparison": float(comparison[track_id]),
                    "endpoint_fraction_reference": float(primary[track_id]),
                    "endpoint_fraction_difference": float(
                        comparison[track_id] - primary[track_id]
                    ),
                    "maximum_absolute_profile_difference": float(
                        np.max(np.abs(difference))
                    ),
                    "endpoint_rank_spearman_with_primary": (
                        float(correlation)
                        if math.isfinite(float(correlation))
                        else None
                    ),
                    "endpoint_rank_concordance_status": rank_status,
                    "label_of_record_mutated": False,
                    "output_kind": "descriptive",
                }
            )
    return rows


def build_conditional_quantiles(
    endpoints: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    frame = pd.DataFrame(endpoints)
    rows: list[dict[str, Any]] = []
    for (factor, track_id), group in frame.groupby(
        ["threshold_factor", "profile_track_id"], sort=True
    ):
        solved = group.loc[group["event_type"].eq("solution")]
        resource = solved["endpoint_resource_value"].to_numpy(dtype=float)
        effort = solved["endpoint_effort_multiplier"].to_numpy(dtype=float)

        def quantile(values: np.ndarray, probability: float) -> float | None:
            return float(np.quantile(values, probability)) if len(values) else None

        counts = Counter(group["event_type"])
        rows.append(
            {
                "threshold_factor": factor,
                "profile_track_id": track_id,
                "solver_family_id": group.iloc[0]["solver_family_id"],
                "panel_tasks": len(group),
                "solution_events": counts["solution"],
                "competing_risk_crashes": counts["competing_risk_crash"],
                "right_censored_walltime": counts["right_censored_walltime"],
                "right_censored_ladder_exhaustion": counts[
                    "right_censored_ladder_exhaustion"
                ],
                "no_attempt_evidence": counts["no_attempt_evidence"],
                "resource_value_q25_success_conditional": quantile(resource, 0.25),
                "resource_value_median_success_conditional": quantile(resource, 0.50),
                "resource_value_q75_success_conditional": quantile(resource, 0.75),
                "effort_q25_success_conditional": quantile(effort, 0.25),
                "effort_median_success_conditional": quantile(effort, 0.50),
                "effort_q75_success_conditional": quantile(effort, 0.75),
                "mean_reported": False,
                "par_k_reported": False,
                "summary_scope": "successful_events_only_conditional",
                "output_kind": "descriptive",
            }
        )
    return rows


def _write_report(
    output_directory: Path,
    attempt_rows: Sequence[Mapping[str, Any]],
    runstatus_rows: Sequence[Mapping[str, Any]],
    endpoints: Sequence[Mapping[str, Any]],
    profiles: Sequence[Mapping[str, Any]],
    stability: Sequence[Mapping[str, Any]],
) -> None:
    attempt_frame = pd.DataFrame(attempt_rows)
    status_frame = pd.DataFrame(runstatus_rows)
    endpoint_frame = pd.DataFrame(endpoints)
    profile_frame = pd.DataFrame(profiles)
    primary_status = status_frame.loc[status_frame["threshold_factor"].eq(1.0)]
    primary_endpoints = endpoint_frame.loc[endpoint_frame["threshold_factor"].eq(1.0)]
    primary_profile = (
        profile_frame.loc[profile_frame["threshold_factor"].eq(1.0)]
        .sort_values("resource_rank")
        .groupby("profile_track_id", sort=True)
        .tail(1)
    )
    primary_counts = Counter(primary_status["runstatus"])
    endpoint_counts = Counter(primary_endpoints["event_type"])
    primary_shci = primary_endpoints.loc[
        primary_endpoints["solver_family_id"].eq("shci")
    ]
    g59_shci_crashes = int(
        (
            primary_shci["event_type"].eq("competing_risk_crash")
            & primary_shci["terminal_coverage_reason"].eq("g59_parent:failed")
        ).sum()
    )
    shci_walltime_censors = int(
        primary_shci["event_type"].eq("right_censored_walltime").sum()
    )
    max_sensitivity = max(
        float(row["maximum_absolute_profile_difference"]) for row in stability
    )
    report = {
        "artifact_id": "ml9b_resource_profiles_report_v1",
        "status": "complete_internal_descriptive",
        "output_kind": "descriptive",
        "internal_only": True,
        "new_solver_runs": False,
        "label_changes": False,
        "task_reselection": False,
        "crashes_pooled_with_censoring": False,
        "panel_tasks": 96,
        "variant_cells": len(attempt_frame),
        "attempted_cells": int(attempt_frame["attempted"].sum()),
        "not_observed_cells": int((~attempt_frame["attempted"]).sum()),
        "primary_runstatus_counts": dict(sorted(primary_counts.items())),
        "primary_endpoint_counts": dict(sorted(endpoint_counts.items())),
        "g59_shci_parent_crash_endpoints": g59_shci_crashes,
        "shci_walltime_censored_endpoints": shci_walltime_censors,
        "g59_shci_crashes_pooled_with_walltime": False,
        "primary_endpoint_fraction_solved": {
            row.profile_track_id: float(row.fraction_solved_cumulative)
            for row in primary_profile.itertuples()
        },
        "maximum_threshold_profile_difference": max_sensitivity,
        "ipie_single_point": True,
        "conditional_quantiles_only": True,
        "par_k_reported": False,
        "design_based_ratio": "unchanged_ratio_of_record",
    }
    stable_json_dump(report, output_directory / "report.json")
    text = f"""# ML-9B censored resource-to-solution records and data profiles

Status: complete internal descriptive artifact from accepted G50-retained plus
G59-harvest data only. No solver run, label change, task reselection, population
weighting, or public/dashboard placement occurred.

At the primary threshold, the four-class attempted-cell census is
`{dict(sorted(primary_counts.items()))}`. The 96-task by track endpoint census
is `{dict(sorted(endpoint_counts.items()))}`. Crashes remain competing-risk
events and are not included in either right-censor class.

In particular, the three G59 SHCI parent-crash endpoints are retained as
competing risks and remain distinct from the 20 SHCI walltime-censored
endpoints. The larger all-source SHCI crash count also retains accepted failed
attempts from the G50-retained portion and is reported by the endpoint table.

The primary endpoint fractions solved are
`{report['primary_endpoint_fraction_solved']}`. iPIE/AFQMC is a documented
single-budget point. The SHCI terminal perturbative and TrimCI default composite
variants retain runstatus views but do not enter an incompatible ladder axis.

Across the 0.5x and 2x sensitivity layers, the largest absolute change from the
1x data profile is {max_sensitivity:.6f}. Stored labels are untouched. Resource
summaries report successful-event conditional quartiles and medians only; no
mean or PAR-k scalar is emitted. Heavy-tailed resource observations and censoring
must be interpreted from the endpoint/status counts alongside those quantiles.
"""
    (output_directory / "REPORT.md").write_text(text, encoding="utf-8")


def run_finalization(
    root: Path,
    preregistration_path: Path,
    schema_binding_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Run and serialize one complete deterministic ML-9B finalization."""

    data = prepare_resource_data(root, preregistration_path, schema_binding_path)
    attempt_rows = build_attempt_coverage(data)
    runstatus_rows = build_runstatus(data)
    endpoints = build_resource_endpoints(data)
    profiles = build_data_profiles(data, endpoints)
    stability = build_threshold_stability(profiles)
    quantiles = build_conditional_quantiles(endpoints)
    companion_rows = [
        row
        for row in runstatus_rows
        if row["solver_variant_id"] in data.companion_variants
    ]

    _require(len(attempt_rows) == 1728, "attempt coverage census changed")
    _require(
        len(endpoints) == 96 * len(PROFILE_TRACKS) * len(THRESHOLD_FACTORS),
        "endpoint census changed",
    )
    _require(
        not any(
            row["crash_is_competing_risk"] and row["runstatus"] != "crash"
            for row in runstatus_rows
        ),
        "crash/runstatus binding changed",
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    outputs = (
        ("attempt_coverage.csv", attempt_rows),
        ("runstatus.csv", runstatus_rows),
        ("resource_to_solution.csv", endpoints),
        ("data_profiles.csv", profiles),
        ("threshold_stability.csv", stability),
        ("conditional_resource_quantiles.csv", quantiles),
        ("companion_variants.csv", companion_rows),
    )
    for name, rows in outputs:
        _require(bool(rows), f"empty ML-9B output {name}")
        stable_csv_dump(rows, list(rows[0]), output_directory / name)

    environment = {
        "artifact_id": "ml9b_runtime_environment_v1",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            name: importlib_metadata.version(name)
            for name in ("numpy", "pandas", "scipy")
        },
        "python_hash_seed": 0,
        "output_kind": "environment_record",
    }
    stable_json_dump(environment, output_directory / "environment.json")
    _write_report(
        output_directory,
        attempt_rows,
        runstatus_rows,
        endpoints,
        profiles,
        stability,
    )

    required = set(data.preregistration["outputs"]["required_files"])
    produced_before_manifest = {
        path.name for path in output_directory.iterdir() if path.is_file()
    }
    _require(
        required - {"artifact_manifest.json"} <= produced_before_manifest,
        "missing required ML-9B output",
    )
    files = [
        {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(output_directory.iterdir())
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    report = _read_json(output_directory / "report.json")
    manifest = {
        "artifact_id": "ml9b_resource_profiles_manifest_v1",
        "status": "complete_internal_descriptive",
        "output_kind": "descriptive",
        "internal_only": True,
        "new_solver_runs": False,
        "task_reselection": False,
        "label_changes": False,
        "crashes_pooled_with_censoring": False,
        "par_k_reported": False,
        "preregistration_sha256": sha256_file(preregistration_path),
        "preflight_manifest_sha256": PREFLIGHT_MANIFEST_SHA256,
        "schema_binding_sha256": SCHEMA_BINDING_SHA256,
        "input_hashes": data.input_hashes,
        "census": {
            "panel_tasks": 96,
            "variant_cells": len(attempt_rows),
            "attempted_cells": report["attempted_cells"],
            "not_observed_cells": report["not_observed_cells"],
            "runstatus_rows": len(runstatus_rows),
            "resource_endpoint_rows": len(endpoints),
            "data_profile_rows": len(profiles),
            "threshold_stability_rows": len(stability),
            "conditional_quantile_rows": len(quantiles),
            "companion_runstatus_rows": len(companion_rows),
        },
        "files": files,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    _require(
        {path.name for path in output_directory.iterdir() if path.is_file()}
        == required,
        "ML-9B output member set differs from preregistration",
    )
    return manifest
