"""Deterministic ML-10 PySCF resource-profile and desk finalizations."""

from __future__ import annotations

import csv
import io
import json
import os
import platform
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.pyscf_hardness_labels import (
    DISPLAY_BY_ITEM,
    FAILURE_CAP,
    METHOD_ORDER,
    PreparedPyscfData,
    label_records,
    prepare_pyscf_data,
)


THRESHOLD_FACTORS = (0.5, 1.0, 2.0)
LABEL_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "method",
    "item_id",
    "in_panel",
    "coverage_class",
    "attempted",
    "gradeable_for_campaign_scoring",
    "energy_hartree",
    "reference_energy_hartree",
    "threshold_hartree",
    "absolute_error_hartree",
    "graded_residual",
    "response_observed",
    "solvable",
    "continuous_quality",
    "label_reason",
    "epistemic_flags",
    "pending_reference_recompute",
]


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def _csv_value(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".17g")
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if isinstance(value, (int, np.integer)):
        return int(value)
    return value


def _append_rows_exact(
    base: Path,
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
    destination: Path,
) -> None:
    header = base.read_text(encoding="utf-8").splitlines()[0].split(",")
    _require(header == list(columns), f"base schema changed: {base}")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
    for row in rows:
        writer.writerow({column: _csv_value(row.get(column)) for column in columns})
    base_text = base.read_text(encoding="utf-8")
    _require(base_text.endswith("\n"), f"base CSV lacks final newline: {base}")
    destination.write_text(base_text + stream.getvalue(), encoding="utf-8")


def _environment(artifact_id: str) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "0"),
        "thread_limits": {
            name: os.environ.get(name, "1")
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
            )
        },
        "output_kind": "environment_record",
    }


def _write_manifest(
    output_directory: Path,
    artifact_id: str,
    preregistration_path: Path,
    input_hashes: Mapping[str, str],
) -> dict[str, Any]:
    files = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(output_directory.iterdir())
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    manifest = {
        "artifact_id": artifact_id,
        "status": "complete_internal_descriptive",
        "preregistration_sha256": sha256_file(preregistration_path),
        "input_hashes": dict(sorted(input_hashes.items())),
        "new_solver_runs": False,
        "task_reselection": False,
        "source_labels_mutated": False,
        "internal_only": True,
        "files": files,
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return manifest


def _resource_rows(data: PreparedPyscfData) -> dict[str, list[dict[str, Any]]]:
    panel = data.labels.loc[data.labels["in_panel"]].copy()
    panel = panel.sort_values(
        ["task_uuid", "item_id"],
        key=lambda values: (
            values.map({item: index for index, item in enumerate(METHOD_ORDER)})
            if values.name == "item_id"
            else values
        ),
        kind="mergesort",
    )
    attempt_rows: list[dict[str, Any]] = []
    runstatus_rows: list[dict[str, Any]] = []
    endpoint_rows: list[dict[str, Any]] = []
    profile_rows: list[dict[str, Any]] = []
    conditional_profile_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    quantile_rows: list[dict[str, Any]] = []

    for row in panel.to_dict(orient="records"):
        item = str(row["item_id"])
        track = f"{item}_single_budget_v1"
        finite = bool(np.isfinite(row["energy_hartree"]))
        coverage_class = str(row["coverage_class"])
        attempted = bool(row["attempted"])
        accepted_status = str(row["result_status"]) if attempted else ""
        terminal = ""
        if attempted and not finite:
            terminal = (
                "timeout"
                if "timeout" in str(row.get("failure_stage") or "").lower()
                else "crash"
            )
        attempt_rows.append(
            {
                "task_uuid": row["task_uuid"],
                "canonical_family": row["canonical_family"],
                "solver_family_id": item,
                "solver_variant_id": item,
                "profile_track_id": track,
                "track_kind": "single_point",
                "resource_axis_name": "single_budget",
                "resource_value": 1,
                "resource_units": "accepted_configuration",
                "resource_rank": 0,
                "effort_multiplier": 1,
                "finite_result": finite,
                "accepted_raw_status": accepted_status,
                "terminal_status_if_no_result": terminal,
                "attempted": attempted,
                "attempt_evidence": (
                    "finite_result"
                    if finite
                    else "accepted_failed_attempt" if attempted else coverage_class
                ),
                "coverage_status": (
                    "terminal_contract" if attempted else coverage_class
                ),
                "coverage_reason": str(row["label_reason"]),
                "label_of_record_mutated": False,
                "output_kind": "descriptive",
            }
        )
        for factor in THRESHOLD_FACTORS:
            solved = bool(
                row["response_observed"]
                and finite
                and float(row["graded_residual"]) <= factor
            )
            if attempted:
                runstatus = "ok" if solved else "accuracy_miss" if finite else terminal
                runstatus_rows.append(
                    {
                        "task_uuid": row["task_uuid"],
                        "canonical_family": row["canonical_family"],
                        "solver_family_id": item,
                        "solver_variant_id": item,
                        "profile_track_id": track,
                        "track_kind": "single_point",
                        "threshold_factor": factor,
                        "runstatus": runstatus,
                        "graded_residual": row["graded_residual"] if finite else None,
                        "accepted_raw_status": accepted_status,
                        "coverage_status": "terminal_contract",
                        "coverage_reason": str(row["label_reason"]),
                        "crash_is_competing_risk": runstatus == "crash",
                        "label_of_record_mutated": False,
                        "output_kind": "descriptive",
                    }
                )
            if solved:
                event_type = "solution"
            elif attempted and finite:
                event_type = "right_censored_ladder_exhaustion"
            elif attempted and terminal == "timeout":
                event_type = "right_censored_walltime"
            elif attempted:
                event_type = "competing_risk_failure"
            else:
                event_type = coverage_class
            right_censored = event_type in {
                "right_censored_ladder_exhaustion",
                "right_censored_walltime",
            }
            endpoint_rows.append(
                {
                    "task_uuid": row["task_uuid"],
                    "canonical_family": row["canonical_family"],
                    "solver_family_id": item,
                    "profile_track_id": track,
                    "track_kind": "single_point",
                    "resource_axis_name": "single_budget",
                    "resource_units": "accepted_configuration",
                    "threshold_factor": factor,
                    "event_type": event_type,
                    "solution_observed": solved,
                    "crash_competing_risk": event_type == "competing_risk_failure",
                    "right_censored": right_censored,
                    "censor_class": event_type if right_censored else "",
                    "endpoint_resource_rank": 0 if attempted else None,
                    "endpoint_resource_value": 1 if attempted else None,
                    "endpoint_effort_multiplier": 1 if attempted else None,
                    "terminal_attempt_resource_rank": 0 if attempted else None,
                    "terminal_accepted_raw_status": accepted_status,
                    "terminal_coverage_reason": str(row["label_reason"]),
                    "terminal_observation_source": "accepted_g48_campaign",
                    "attempted_variant_count": int(attempted),
                    "finite_result_count": int(finite),
                    "monotonic_repair_applied": False,
                    "label_of_record_mutated": False,
                    "output_kind": "descriptive",
                }
            )

    endpoints = pd.DataFrame(endpoint_rows)
    for item in METHOD_ORDER:
        item_panel = panel.loc[panel["item_id"].eq(item)]
        for factor in THRESHOLD_FACTORS:
            subset = endpoints.loc[
                endpoints["solver_family_id"].eq(item)
                & endpoints["threshold_factor"].eq(factor)
            ]
            solved = int(subset["solution_observed"].sum())
            attempted = int(item_panel["attempted"].sum())
            cost_screened = int(
                item_panel["coverage_class"].eq("not_attempted_cost_screened").sum()
            )
            no_coverage = int(
                item_panel["coverage_class"].eq("no_pyscf_coverage").sum()
            )
            track = f"{item}_single_budget_v1"
            profile_rows.append(
                {
                    "solver_family_id": item,
                    "profile_track_id": track,
                    "track_kind": "single_point",
                    "threshold_factor": factor,
                    "resource_axis_name": "single_budget",
                    "resource_units": "accepted_configuration",
                    "resource_rank": 0,
                    "resource_value": 1,
                    "effort_multiplier": 1,
                    "tasks_solved_cumulative": solved,
                    "panel_tasks": 96,
                    "fraction_solved_cumulative": solved / 96,
                    "selection_weighted": False,
                    "monotonic_repair_applied": False,
                    "output_kind": "descriptive",
                }
            )
            conditional_profile_rows.append(
                {
                    "solver_family_id": item,
                    "method": DISPLAY_BY_ITEM[item],
                    "profile_track_id": track,
                    "threshold_factor": factor,
                    "panel_tasks": 96,
                    "attempted_covered_tasks": attempted,
                    "cost_screened_tasks": cost_screened,
                    "no_coverage_tasks": no_coverage,
                    "tasks_solved": solved,
                    "all_panel_lower_bound_fraction": solved / 96,
                    "attempted_coverage_conditional_fraction": solved / attempted,
                    "partial_identification_upper_fraction": (
                        solved + cost_screened + no_coverage
                    )
                    / 96,
                    "missing_imputed": False,
                    "output_kind": "estimate",
                }
            )
            counts = Counter(subset["event_type"])
            quantile_rows.append(
                {
                    "threshold_factor": factor,
                    "profile_track_id": track,
                    "solver_family_id": item,
                    "panel_tasks": 96,
                    "solution_events": counts["solution"],
                    "competing_risk_crashes": counts["competing_risk_failure"],
                    "right_censored_walltime": counts["right_censored_walltime"],
                    "right_censored_ladder_exhaustion": counts[
                        "right_censored_ladder_exhaustion"
                    ],
                    "no_attempt_evidence": counts["not_attempted_cost_screened"]
                    + counts["no_pyscf_coverage"],
                    "resource_value_q25_success_conditional": 1 if solved else None,
                    "resource_value_median_success_conditional": 1 if solved else None,
                    "resource_value_q75_success_conditional": 1 if solved else None,
                    "effort_q25_success_conditional": 1 if solved else None,
                    "effort_median_success_conditional": 1 if solved else None,
                    "effort_q75_success_conditional": 1 if solved else None,
                    "mean_reported": False,
                    "par_k_reported": False,
                    "summary_scope": "successful_events_only_conditional",
                    "output_kind": "descriptive",
                }
            )
        primary = next(
            row
            for row in conditional_profile_rows
            if row["solver_family_id"] == item and row["threshold_factor"] == 1.0
        )
        for factor in (0.5, 2.0):
            comparison = next(
                row
                for row in conditional_profile_rows
                if row["solver_family_id"] == item and row["threshold_factor"] == factor
            )
            difference = float(comparison["all_panel_lower_bound_fraction"]) - float(
                primary["all_panel_lower_bound_fraction"]
            )
            stability_rows.append(
                {
                    "profile_track_id": f"{item}_single_budget_v1",
                    "solver_family_id": item,
                    "comparison_threshold_factor": factor,
                    "reference_threshold_factor": 1.0,
                    "endpoint_fraction_comparison": comparison[
                        "all_panel_lower_bound_fraction"
                    ],
                    "endpoint_fraction_reference": primary[
                        "all_panel_lower_bound_fraction"
                    ],
                    "endpoint_fraction_difference": difference,
                    "maximum_absolute_profile_difference": abs(difference),
                    "endpoint_rank_spearman_with_primary": None,
                    "endpoint_rank_concordance_status": "not_applicable_single_point",
                    "label_of_record_mutated": False,
                    "output_kind": "descriptive",
                }
            )

    return {
        "attempt_coverage": attempt_rows,
        "runstatus": runstatus_rows,
        "resource_to_solution": endpoint_rows,
        "data_profiles": profile_rows,
        "pyscf_single_budget_profiles": conditional_profile_rows,
        "threshold_stability": stability_rows,
        "conditional_resource_quantiles": quantile_rows,
    }


def run_resource_finalization(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Create ML-10B final_v2 while retaining every ML-9B table row."""

    _require(
        not output_directory.exists(), f"output already exists: {output_directory}"
    )
    data = prepare_pyscf_data(root, preregistration_path)
    rows = _resource_rows(data)
    base = root / "analysis/ml9_resource_profiles/final_v1"
    base_manifest = json.loads((base / "artifact_manifest.json").read_text())
    _require(
        base_manifest.get("status") == "complete_internal_descriptive",
        "ML-9B base is not complete",
    )
    for item in base_manifest["files"]:
        _require(
            sha256_file(base / item["path"]) == item["sha256"],
            "ML-9B base file changed",
        )

    output_directory.mkdir(parents=True)
    for name in (
        "attempt_coverage",
        "runstatus",
        "resource_to_solution",
        "data_profiles",
        "threshold_stability",
        "conditional_resource_quantiles",
    ):
        base_path = base / f"{name}.csv"
        columns = base_path.read_text(encoding="utf-8").splitlines()[0].split(",")
        _append_rows_exact(
            base_path, rows[name], columns, output_directory / f"{name}.csv"
        )
    shutil.copyfile(
        base / "companion_variants.csv", output_directory / "companion_variants.csv"
    )
    stable_csv_dump(
        rows["pyscf_single_budget_profiles"],
        list(rows["pyscf_single_budget_profiles"][0]),
        output_directory / "pyscf_single_budget_profiles.csv",
    )
    stable_csv_dump(
        label_records(data), LABEL_COLUMNS, output_directory / "pyscf_labels.csv"
    )

    primary_runstatus = [
        row for row in rows["runstatus"] if row["threshold_factor"] == 1.0
    ]
    primary_endpoints = [
        row for row in rows["resource_to_solution"] if row["threshold_factor"] == 1.0
    ]
    base_report = json.loads((base / "report.json").read_text(encoding="utf-8"))
    new_status = Counter(str(row["runstatus"]) for row in primary_runstatus)
    combined_status = Counter(base_report["primary_runstatus_counts"])
    combined_status.update(new_status)
    new_endpoints = Counter(str(row["event_type"]) for row in primary_endpoints)
    combined_endpoints = Counter(base_report["primary_endpoint_counts"])
    combined_endpoints.update(new_endpoints)
    report = {
        "artifact_id": "ml10b_resource_profiles_report_v2",
        "status": "complete_internal_descriptive",
        "output_kind": "descriptive",
        "panel_tasks": 96,
        "base_solver_variants": 18,
        "pyscf_single_budget_tracks": 5,
        "combined_items": 23,
        "pyscf_panel_attempted_cells": int(
            data.labels.loc[data.labels["in_panel"], "attempted"].sum()
        ),
        "pyscf_panel_cost_screened_cells": int(
            (
                data.labels["in_panel"]
                & data.labels["coverage_class"].eq("not_attempted_cost_screened")
            ).sum()
        ),
        "pyscf_panel_no_coverage_cells": int(
            (
                data.labels["in_panel"]
                & data.labels["coverage_class"].eq("no_pyscf_coverage")
            ).sum()
        ),
        "pyscf_primary_runstatus_counts": dict(sorted(new_status.items())),
        "pyscf_primary_endpoint_counts": dict(sorted(new_endpoints.items())),
        "combined_primary_runstatus_counts": dict(sorted(combined_status.items())),
        "combined_primary_endpoint_counts": dict(sorted(combined_endpoints.items())),
        "cost_screened_endpoint_distinct": True,
        "no_coverage_endpoint_distinct": True,
        "missing_imputed": False,
        "single_budget_ladder_invented": False,
        "conditional_quantiles_only": True,
        "par_k_reported": False,
        "new_solver_runs": False,
        "task_reselection": False,
        "source_labels_mutated": False,
        "internal_only": True,
    }
    stable_json_dump(report, output_directory / "report.json")
    stable_json_dump(
        _environment("ml10b_runtime_environment_v2"),
        output_directory / "environment.json",
    )
    text = f"""# ML-10B censored resource profiles — internal final v2

Status: complete internal descriptive artifact. The accepted ML-9B rows are
retained and five PySCF methods are appended as one-point single-budget tracks;
no ladder axis is invented.

The panel contains {report['pyscf_panel_attempted_cells']} attempted PySCF
cells, {report['pyscf_panel_cost_screened_cells']} cost-screened cells, and
{report['pyscf_panel_no_coverage_cells']} no-coverage cells. Cost-screened and
uncovered cells receive explicit endpoint classes and no four-class runstatus.
The profile table reports both the all-panel lower bound and the conditional
attempted-coverage fraction, with missingness bounds and no imputation.

Primary PySCF runstatus counts are {dict(sorted(new_status.items()))}. Primary
PySCF endpoint counts are {dict(sorted(new_endpoints.items()))}. Every output
is descriptive and internal; no solver run, selection change, source-label
mutation, PAR-k summary, or public placement occurred.
"""
    (output_directory / "REPORT.md").write_text(text, encoding="utf-8")
    _write_manifest(
        output_directory,
        "ml10b_resource_profiles_manifest_v2",
        preregistration_path,
        data.input_hashes,
    )
    return report


def _panel_desk_rows(
    data: PreparedPyscfData,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    panel = data.labels.loc[data.labels["in_panel"]].copy()
    panel = panel.merge(
        data.ladder_panel[["task_uuid", "solvable_1x_portfolio_union"]],
        on="task_uuid",
        how="left",
        validate="many_to_one",
    )
    union_rows: list[dict[str, Any]] = []
    for item in METHOD_ORDER:
        subset = panel.loc[panel["item_id"].eq(item)].copy()
        observed = subset["response_observed"].astype(bool)
        success = subset["solvable"].eq(True)
        ladder = subset["solvable_1x_portfolio_union"].astype(bool)
        union_rows.append(
            {
                "scope": "panel",
                "target": item,
                "method": DISPLAY_BY_ITEM[item],
                "panel_tasks": 96,
                "observed_attempted_tasks": int(observed.sum()),
                "missing_tasks": int((~observed).sum()),
                "known_successes": int(success.sum()),
                "unique_additions_beyond_ladder_union": int((success & ~ladder).sum()),
                "shared_successes_with_ladder_union": int((success & ladder).sum()),
                "ladder_successes_not_reproduced_among_observed": int(
                    (observed & ~success & ladder).sum()
                ),
                "neither_succeeds_among_observed": int(
                    (observed & ~success & ~ladder).sum()
                ),
                "missing_imputed": False,
                "output_kind": "estimate",
            }
        )

    by_task = panel.pivot(index="task_uuid", columns="item_id", values="solvable")
    observed_by_task = panel.pivot(
        index="task_uuid", columns="item_id", values="response_observed"
    ).astype(bool)
    known_success = by_task.eq(True).any(axis=1)
    ladder_map = data.ladder_panel.set_index("task_uuid")[
        "solvable_1x_portfolio_union"
    ].astype(bool)
    ladder = ladder_map.reindex(by_task.index)
    union_rows.append(
        {
            "scope": "panel",
            "target": "pyscf_five_method_union",
            "method": "five-method union",
            "panel_tasks": 96,
            "observed_attempted_tasks": int(observed_by_task.any(axis=1).sum()),
            "missing_tasks": int((~observed_by_task.all(axis=1)).sum()),
            "known_successes": int(known_success.sum()),
            "unique_additions_beyond_ladder_union": int(
                (known_success & ~ladder).sum()
            ),
            "shared_successes_with_ladder_union": int((known_success & ladder).sum()),
            "ladder_successes_not_reproduced_among_observed": int(
                (~known_success & ladder).sum()
            ),
            "neither_succeeds_among_observed": int((~known_success & ~ladder).sum()),
            "missing_imputed": False,
            "output_kind": "estimate",
        }
    )

    panel_weights = data.panel.set_index("task_uuid")["selection_weight_609"].astype(
        int
    )
    ratio_rows: list[dict[str, Any]] = []
    for item in METHOD_ORDER:
        subset = panel.loc[panel["item_id"].eq(item)].set_index("task_uuid")
        weights = panel_weights.reindex(subset.index)
        observed = subset["response_observed"].astype(bool)
        success = subset["solvable"].eq(True)
        success_weight = int(weights[success].sum())
        observed_weight = int(weights[observed].sum())
        missing_weight = int(weights[~observed].sum())
        ratio_rows.append(
            {
                "method": DISPLAY_BY_ITEM[item],
                "item_id": item,
                "selection_weight_total": 609,
                "known_success_weight": success_weight,
                "observed_attempted_weight": observed_weight,
                "missing_weight": missing_weight,
                "design_lower_bound": success_weight / 609,
                "design_upper_bound": (success_weight + missing_weight) / 609,
                "attempted_coverage_conditional_ratio": success_weight
                / observed_weight,
                "missing_imputed": False,
                "output_kind": "estimate",
            }
        )
    return union_rows, ratio_rows


def _frontier_rows(data: PreparedPyscfData) -> list[dict[str, Any]]:
    labels = data.labels.copy()
    rows: list[dict[str, Any]] = []
    order = {item: index for index, item in enumerate(METHOD_ORDER)}
    for task_uuid, group in labels.groupby("task_uuid", sort=True):
        group = group.sort_values("item_id", key=lambda values: values.map(order))
        observed_items = list(group.loc[group["response_observed"], "item_id"])
        success_items = list(group.loc[group["solvable"].eq(True), "item_id"])
        rows.append(
            {
                "task_uuid": task_uuid,
                "canonical_family": str(group["canonical_family"].iloc[0]),
                "in_panel": bool(group["in_panel"].iloc[0]),
                "gradeable_for_campaign_scoring": bool(
                    group["gradeable_for_campaign_scoring"].iloc[0]
                ),
                "observed_method_count": len(observed_items),
                "known_success_method_count": len(success_items),
                "first_sufficient_method": success_items[0] if success_items else "",
                "highest_observed_method": observed_items[-1] if observed_items else "",
                "success_methods": ";".join(success_items),
                "cost_screened_method_count": int(
                    group["coverage_class"].eq("not_attempted_cost_screened").sum()
                ),
                "no_coverage_method_count": int(
                    group["coverage_class"].eq("no_pyscf_coverage").sum()
                ),
                "frontier_complete": len(observed_items) == 5,
                "missing_imputed": False,
                "output_kind": "estimate",
            }
        )
    return rows


def _corpus_rate_rows(data: PreparedPyscfData) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in METHOD_ORDER:
        subset = data.labels.loc[
            data.labels["item_id"].eq(item)
            & data.labels["in_campaign_baseline"]
            & data.labels["gradeable_for_campaign_scoring"]
        ]
        observed = subset["response_observed"].astype(bool)
        success = subset["solvable"].eq(True)
        missing = ~observed
        _require(len(subset) == 486, "gradeable G48 coverage changed")
        rows.append(
            {
                "method": DISPLAY_BY_ITEM[item],
                "item_id": item,
                "gradeable_covered_tasks": len(subset),
                "observed_attempted_tasks": int(observed.sum()),
                "known_successes": int(success.sum()),
                "cost_screened_missing_tasks": int(missing.sum()),
                "observed_attempted_solvability_rate": float(
                    success.sum() / observed.sum()
                ),
                "near_census_lower_bound": float(success.sum() / len(subset)),
                "near_census_upper_bound": float(
                    (success.sum() + missing.sum()) / len(subset)
                ),
                "missing_imputed": False,
                "output_kind": "near_census_observed_descriptive_estimate",
            }
        )
    return rows


def run_desk_finalization(
    root: Path, preregistration_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Create ML-10D unions, method frontiers, and missingness-bounded ratios."""

    _require(
        not output_directory.exists(), f"output already exists: {output_directory}"
    )
    data = prepare_pyscf_data(root, preregistration_path)
    union_rows, ratio_rows = _panel_desk_rows(data)
    frontier_rows = _frontier_rows(data)
    corpus_rows = _corpus_rate_rows(data)
    output_directory.mkdir(parents=True)
    stable_csv_dump(
        union_rows, list(union_rows[0]), output_directory / "panel_unions.csv"
    )
    stable_csv_dump(
        ratio_rows, list(ratio_rows[0]), output_directory / "design_based_ratios.csv"
    )
    stable_csv_dump(
        frontier_rows, list(frontier_rows[0]), output_directory / "method_frontiers.csv"
    )
    stable_csv_dump(
        corpus_rows,
        list(corpus_rows[0]),
        output_directory / "corpus_near_census_rates.csv",
    )
    stable_csv_dump(
        label_records(data), LABEL_COLUMNS, output_directory / "pyscf_labels.csv"
    )
    union = next(
        row for row in union_rows if row["target"] == "pyscf_five_method_union"
    )
    report = {
        "artifact_id": "ml10d_pyscf_desk_report_v1",
        "status": "complete_internal_descriptive",
        "output_kind": "estimate",
        "panel_tasks": 96,
        "pyscf_known_union_successes": union["known_successes"],
        "pyscf_union_unique_additions_beyond_ladder": union[
            "unique_additions_beyond_ladder_union"
        ],
        "panel_union_rows": len(union_rows),
        "design_based_ratio_rows": len(ratio_rows),
        "method_frontier_rows": len(frontier_rows),
        "corpus_near_census_rows": len(corpus_rows),
        "selection_weight_total": 609,
        "partial_identification_bounds_reported": True,
        "missing_imputed": False,
        "design_based_ratio_of_record_replaced": False,
        "new_solver_runs": False,
        "task_reselection": False,
        "source_labels_mutated": False,
        "internal_only": True,
    }
    stable_json_dump(report, output_directory / "report.json")
    stable_json_dump(
        _environment("ml10d_runtime_environment_v1"),
        output_directory / "environment.json",
    )
    text = f"""# ML-10D PySCF unions, frontiers, and ratios — internal final v1

Status: complete internal descriptive artifact. The known five-method PySCF
union solves {union['known_successes']} panel tasks and adds
{union['unique_additions_beyond_ladder_union']} known solves beyond the
18-item ladder union. Per-method and union counts preserve every cost-screened
and no-coverage cell as missing.

Design-based method ratios use the frozen weights summing to 609 and report a
known-success lower bound, missingness upper bound, and attempted-coverage
conditional estimate. Corpus rates are near-census observed estimates over
the 486 gradeable tasks covered by the accepted campaign, with cost-screened
partial-identification bounds. These estimates do not replace the existing
design-based ratio of record.

No solver run, task reselection, source-label mutation, missing-value
imputation, public placement, or push occurred.
"""
    (output_directory / "REPORT.md").write_text(text, encoding="utf-8")
    _write_manifest(
        output_directory,
        "ml10d_pyscf_desk_manifest_v1",
        preregistration_path,
        data.input_hashes,
    )
    return report
