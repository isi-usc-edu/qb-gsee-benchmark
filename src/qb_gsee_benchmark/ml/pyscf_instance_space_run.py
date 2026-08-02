"""Deterministic ML-10A PySCF extension of the accepted instance space."""

from __future__ import annotations

import contextlib
import io
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from instancespace.data.options import ParallelOptions, TraceOptions
from instancespace.stages.trace import TraceStage
from sklearn.metrics import accuracy_score, balanced_accuracy_score

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.instance_space_run import (
    _fit_one_pythia_target,
    _footprint_metrics,
    _geometry_payload,
    _instancespace_021_trace_compatibility,
)
from qb_gsee_benchmark.ml.pyscf_hardness_labels import (
    DISPLAY_BY_ITEM,
    METHOD_ORDER,
    PreparedPyscfData,
    label_records,
    prepare_pyscf_data,
)
from qb_gsee_benchmark.ml.pyscf_hardness_run import (
    LABEL_COLUMNS,
    _environment,
    _write_manifest,
)


TARGET_ORDER = (*METHOD_ORDER, "ladder_plus_pyscf_portfolio")


def _single_trace(z: np.ndarray, labels: np.ndarray):
    _require(z.shape == (len(labels), 2), "TRACE coordinate shape changed")
    _require(len(labels) >= 3, "TRACE needs at least three tasks")
    boolean = np.asarray(labels, dtype=bool)
    with (
        _instancespace_021_trace_compatibility(),
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        return TraceStage.trace(
            z=np.asarray(z, dtype=float),
            y_bin=boolean[:, None],
            p=np.zeros(len(boolean), dtype=int),
            beta=boolean,
            algo_labels=["target"],
            trace_opts=TraceOptions.default(use_sim=False, purity=0.55),
            parallel_opts=ParallelOptions.default(flag=False, n_cores=1),
        )


def _target_table(data: PreparedPyscfData) -> dict[str, pd.DataFrame]:
    panel_coordinates = data.panel_coordinates.set_index("task_uuid")
    targets: dict[str, pd.DataFrame] = {}
    for item in METHOD_ORDER:
        labels = data.labels.loc[
            data.labels["in_panel"]
            & data.labels["item_id"].eq(item)
            & data.labels["response_observed"]
        ].copy()
        labels = labels.join(panel_coordinates[["z1", "z2"]], on="task_uuid")
        _require(
            bool(labels[["z1", "z2"]].notna().all().all()), "panel coordinate missing"
        )
        targets[item] = labels

    ladder = data.ladder_panel.set_index("task_uuid")
    pyscf = data.labels.loc[data.labels["in_panel"]].pivot(
        index="task_uuid", columns="item_id", values="solvable"
    )
    known_pyscf_success = pyscf.eq(True).any(axis=1)
    portfolio = data.panel_coordinates[
        ["task_uuid", "canonical_family", "z1", "z2"]
    ].copy()
    portfolio = portfolio.join(
        ladder["solvable_1x_portfolio_union"], on="task_uuid"
    ).join(known_pyscf_success.rename("known_pyscf_success"), on="task_uuid")
    portfolio["solvable"] = portfolio["solvable_1x_portfolio_union"].astype(
        bool
    ) | portfolio["known_pyscf_success"].astype(bool)
    portfolio["response_observed"] = True
    portfolio["item_id"] = "ladder_plus_pyscf_portfolio"
    targets["ladder_plus_pyscf_portfolio"] = portfolio
    return targets


def _panel_trace(
    targets: Mapping[str, pd.DataFrame], gate_by_target: Mapping[str, bool]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    polygons: dict[str, Any] = {
        "artifact_id": "ml10a_panel_trace_polygons_v2",
        "output_kind": "estimate",
        "projection_refit": False,
        "targets": {},
    }
    for target in TARGET_ORDER:
        frame = targets[target]
        trace = _single_trace(
            frame[["z1", "z2"]].to_numpy(dtype=float),
            frame["solvable"].astype(bool).to_numpy(),
        )
        footprint = trace.good[0]
        metrics = _footprint_metrics(footprint, trace.space)
        rows.append(
            {
                "target": target,
                "method": DISPLAY_BY_ITEM.get(target, "ladder plus PySCF portfolio"),
                "footprint_kind": "good",
                "observed_tasks": len(frame),
                "solved_tasks": int(frame["solvable"].astype(bool).sum()),
                **metrics,
                "pythia_gate_passed": bool(gate_by_target[target]),
                "interpretation": (
                    "descriptive_geometry"
                    if gate_by_target[target]
                    else "caveated_feature_adequacy_gate_failed"
                ),
                "status": "estimated" if footprint.area > 0 else "degenerate",
                "projection_refit": False,
                "missing_imputed": False,
                "output_kind": "estimate",
            }
        )
        polygons["targets"][target] = {
            "empirical_space": _geometry_payload(trace.space),
            "good": _geometry_payload(footprint),
        }
    return rows, polygons


def _fit_pythia_and_validate(
    data: PreparedPyscfData, targets: Mapping[str, pd.DataFrame]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, bool]]:
    corpus_coordinates = data.corpus_coordinates.reset_index(drop=True)
    corpus_z = corpus_coordinates[["z1", "z2"]].to_numpy(dtype=float)
    corpus_position = {
        task_uuid: index
        for index, task_uuid in enumerate(corpus_coordinates["task_uuid"].astype(str))
    }
    gate_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    gate_by_target: dict[str, bool] = {}
    for target in TARGET_ORDER:
        panel = targets[target]
        row, _, corpus_probability = _fit_one_pythia_target(
            panel[["z1", "z2"]].to_numpy(dtype=float),
            corpus_z,
            panel["solvable"].astype(bool).to_numpy(),
        )
        row.update(
            {
                "target": target,
                "method": DISPLAY_BY_ITEM.get(target, "ladder plus PySCF portfolio"),
                "training_tasks": len(panel),
                "kernel": "rbf",
                "projection_refit": False,
                "missing_imputed": False,
                "output_kind": "estimate",
            }
        )
        gate_rows.append(row)
        gate_by_target[target] = bool(row["gate_passed"])
        if target == "ladder_plus_pyscf_portfolio":
            continue
        external = data.labels.loc[
            ~data.labels["in_panel"]
            & data.labels["item_id"].eq(target)
            & data.labels["response_observed"]
        ].copy()
        positions = [corpus_position[task] for task in external["task_uuid"]]
        probability = corpus_probability[positions]
        truth = external["solvable"].astype(bool).to_numpy()
        predicted = probability >= 0.5
        positives = int(truth.sum())
        negatives = int((~truth).sum())
        majority = max(positives, negatives) / len(truth)
        raw = float(accuracy_score(truth, predicted))
        balanced = float(balanced_accuracy_score(truth, predicted))
        validation_rows.append(
            {
                "target": target,
                "method": DISPLAY_BY_ITEM[target],
                "training_panel_tasks": len(panel),
                "external_nonpanel_tasks": len(external),
                "external_positive": positives,
                "external_negative": negatives,
                "raw_accuracy": raw,
                "balanced_accuracy": balanced,
                "majority_baseline": majority,
                "gate_passed": raw >= max(0.70, majority + 0.05) and balanced >= 0.60,
                "gate_rule": "raw >= max(0.70, majority + 0.05) and balanced >= 0.60",
                "projection_refit": False,
                "classifier_trained_on_panel_only": True,
                "missing_imputed": False,
                "output_kind": "external_validation_estimate",
            }
        )
    return gate_rows, validation_rows, gate_by_target


def _corpus_trace(
    data: PreparedPyscfData,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    coordinates = data.corpus_coordinates.set_index("task_uuid")
    rows: list[dict[str, Any]] = []
    polygons: dict[str, Any] = {
        "artifact_id": "ml10a_corpus_trace_polygons_v2",
        "output_kind": "estimate",
        "projection_refit": False,
        "targets": {},
    }
    for item in METHOD_ORDER:
        frame = data.labels.loc[
            data.labels["item_id"].eq(item) & data.labels["response_observed"]
        ].copy()
        frame = frame.join(coordinates[["z1", "z2"]], on="task_uuid")
        trace = _single_trace(
            frame[["z1", "z2"]].to_numpy(dtype=float),
            frame["solvable"].astype(bool).to_numpy(),
        )
        footprint = trace.good[0]
        rows.append(
            {
                "target": item,
                "method": DISPLAY_BY_ITEM[item],
                "footprint_kind": "good",
                "observed_tasks": len(frame),
                "solved_tasks": int(frame["solvable"].eq(True).sum()),
                **_footprint_metrics(footprint, trace.space),
                "status": "estimated" if footprint.area > 0 else "degenerate",
                "projection_refit": False,
                "missing_imputed": False,
                "output_kind": "external_observed_geometry_estimate",
            }
        )
        polygons["targets"][item] = {
            "empirical_space": _geometry_payload(trace.space),
            "good": _geometry_payload(footprint),
        }
    return rows, polygons


def _bootstrap_trace(
    targets: Mapping[str, pd.DataFrame], replicates: int, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(seed=seed)
    draw_rows: list[dict[str, Any]] = []
    for target in TARGET_ORDER:
        frame = targets[target].reset_index(drop=True)
        groups = sorted(frame["canonical_family"].astype(str).unique())
        indices = {
            family: np.flatnonzero(frame["canonical_family"].astype(str).eq(family))
            for family in groups
        }
        for replicate in range(replicates):
            selected_groups = rng.choice(groups, size=len(groups), replace=True)
            draw_indices = np.concatenate(
                [indices[str(group)] for group in selected_groups]
            )
            z = frame.loc[draw_indices, ["z1", "z2"]].to_numpy(dtype=float)
            labels = frame.loc[draw_indices, "solvable"].astype(bool).to_numpy()
            status = "estimated"
            try:
                trace = _single_trace(z, labels)
                metrics = _footprint_metrics(trace.good[0], trace.space)
                if trace.good[0].area <= 0:
                    status = "degenerate"
            except (ValueError, RuntimeError):
                metrics = {
                    "area": 0.0,
                    "area_normalized": 0.0,
                    "density": 0.0,
                    "density_normalized": 0.0,
                    "purity": 0.0,
                    "elements": 0,
                    "good_elements": 0,
                }
                status = "degenerate"
            draw_rows.append(
                {
                    "replicate": replicate,
                    "target": target,
                    "method": DISPLAY_BY_ITEM.get(
                        target, "ladder plus PySCF portfolio"
                    ),
                    "sampled_blocks": len(selected_groups),
                    "sampled_rows": len(draw_indices),
                    **metrics,
                    "status": status,
                    "projection_refit": False,
                    "missing_imputed": False,
                    "output_kind": "estimate",
                }
            )
    draws = pd.DataFrame(draw_rows)
    interval_rows: list[dict[str, Any]] = []
    for target, group in draws.groupby("target", sort=False):
        for metric in (
            "area",
            "area_normalized",
            "density",
            "density_normalized",
            "purity",
        ):
            values = group[metric].to_numpy(dtype=float)
            interval_rows.append(
                {
                    "target": target,
                    "method": DISPLAY_BY_ITEM.get(
                        target, "ladder plus PySCF portfolio"
                    ),
                    "metric": metric,
                    "estimate_mean": float(np.mean(values)),
                    "estimate_median": float(np.median(values)),
                    "ci_lower": float(np.quantile(values, 0.025)),
                    "ci_upper": float(np.quantile(values, 0.975)),
                    "replicates": replicates,
                    "degenerate_draws": int(group["status"].eq("degenerate").sum()),
                    "interval_scope": "canonical_family_block_bootstrap_conditional_on_fixed_projection_and_observed_coverage",
                    "output_kind": "estimate",
                }
            )
    return draw_rows, interval_rows


def run_instance_space_finalization(
    root: Path,
    preregistration_path: Path,
    output_directory: Path,
    *,
    bootstrap_replicates: int | None = None,
) -> dict[str, Any]:
    """Build the ML-10A final_v2 extension without refitting the projection."""

    _require(
        not output_directory.exists(), f"output already exists: {output_directory}"
    )
    for name in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ[name] = "1"
    os.environ["PYTHONHASHSEED"] = "0"
    data = prepare_pyscf_data(root, preregistration_path)
    targets = _target_table(data)
    gate_rows, validation_rows, gate_by_target = _fit_pythia_and_validate(data, targets)
    panel_trace_rows, panel_polygons = _panel_trace(targets, gate_by_target)
    corpus_trace_rows, corpus_polygons = _corpus_trace(data)
    replicates = (
        int(bootstrap_replicates)
        if bootstrap_replicates is not None
        else int(
            data.preregistration["ml10a_instance_space"]["bootstrap"]["replicates"]
        )
    )
    draw_rows, interval_rows = _bootstrap_trace(
        targets,
        replicates,
        int(data.preregistration["ml10a_instance_space"]["bootstrap"]["seed"]),
    )
    ladder_success = data.ladder_panel["solvable_1x_portfolio_union"].astype(bool)
    pyscf = data.labels.loc[data.labels["in_panel"]].pivot(
        index="task_uuid", columns="item_id", values="solvable"
    )
    known_pyscf = pyscf.eq(True).any(axis=1)
    ladder_by_task = data.ladder_panel.set_index("task_uuid")[
        "solvable_1x_portfolio_union"
    ].astype(bool)
    known_pyscf = known_pyscf.reindex(ladder_by_task.index)
    comparison_rows = [
        {
            "portfolio": "18_item_ladder_union",
            "known_solved_tasks": int(ladder_success.sum()),
            "unique_additions_vs_ladder": 0,
            "panel_tasks": 96,
            "missing_imputed": False,
            "output_kind": "estimate",
        },
        {
            "portfolio": "five_method_pyscf_union",
            "known_solved_tasks": int(known_pyscf.sum()),
            "unique_additions_vs_ladder": int((known_pyscf & ~ladder_by_task).sum()),
            "panel_tasks": 96,
            "missing_imputed": False,
            "output_kind": "estimate",
        },
        {
            "portfolio": "ladder_plus_pyscf_union",
            "known_solved_tasks": int((ladder_by_task | known_pyscf).sum()),
            "unique_additions_vs_ladder": int((known_pyscf & ~ladder_by_task).sum()),
            "panel_tasks": 96,
            "missing_imputed": False,
            "output_kind": "estimate",
        },
    ]

    output_directory.mkdir(parents=True)
    stable_csv_dump(
        label_records(data), LABEL_COLUMNS, output_directory / "pyscf_labels.csv"
    )
    stable_csv_dump(
        gate_rows, list(gate_rows[0]), output_directory / "panel_pythia_gate.csv"
    )
    stable_csv_dump(
        validation_rows,
        list(validation_rows[0]),
        output_directory / "corpus_validation.csv",
    )
    stable_csv_dump(
        panel_trace_rows,
        list(panel_trace_rows[0]),
        output_directory / "panel_trace_footprints.csv",
    )
    stable_json_dump(panel_polygons, output_directory / "panel_trace_polygons.json")
    stable_csv_dump(
        corpus_trace_rows,
        list(corpus_trace_rows[0]),
        output_directory / "corpus_trace_footprints.csv",
    )
    stable_json_dump(corpus_polygons, output_directory / "corpus_trace_polygons.json")
    stable_csv_dump(
        draw_rows, list(draw_rows[0]), output_directory / "bootstrap_draws.csv"
    )
    stable_csv_dump(
        interval_rows,
        list(interval_rows[0]),
        output_directory / "bootstrap_intervals.csv",
    )
    stable_csv_dump(
        comparison_rows,
        list(comparison_rows[0]),
        output_directory / "portfolio_union_comparison.csv",
    )
    projection_binding = {
        "artifact_id": "ml10a_fixed_projection_binding_v2",
        "projection_refit": False,
        "ml9a_manifest_sha256": data.input_hashes["ml9a_manifest"],
        "panel_coordinates_sha256": data.input_hashes["ml9a_panel_coordinates"],
        "corpus_coordinates_sha256": data.input_hashes["ml9a_corpus_coordinates"],
        "projection_features_sha256": data.input_hashes["ml9a_projection_features"],
        "projection_matrix_sha256": data.input_hashes["ml9a_projection_matrix"],
        "cloister_boundary_sha256": data.input_hashes["ml9a_cloister_boundary"],
        "status": "pass",
    }
    stable_json_dump(projection_binding, output_directory / "projection_binding.json")
    stable_json_dump(
        _environment("ml10a_runtime_environment_v2"),
        output_directory / "environment.json",
    )

    ccsdt = next(row for row in panel_trace_rows if row["target"] == "pyscf_ccsd_t")
    combined = comparison_rows[-1]
    report = {
        "artifact_id": "ml10a_instance_space_report_v2",
        "status": "complete_internal_descriptive",
        "output_kind": "estimate",
        "projection_refit": False,
        "panel_tasks": 96,
        "covered_panel_tasks": 92,
        "corpus_tasks": 718,
        "covered_corpus_tasks": 591,
        "pyscf_tracks": 5,
        "panel_pythia_gates_passed": int(
            sum(bool(row["gate_passed"]) for row in gate_rows)
        ),
        "panel_pythia_gates_total": len(gate_rows),
        "external_validation_gates_passed": int(
            sum(bool(row["gate_passed"]) for row in validation_rows)
        ),
        "external_validation_gates_total": len(validation_rows),
        "ccsd_t_known_panel_solves": ccsdt["solved_tasks"],
        "ccsd_t_trace": ccsdt,
        "ladder_plus_pyscf_known_panel_solves": combined["known_solved_tasks"],
        "pyscf_unique_additions_beyond_ladder": combined["unique_additions_vs_ladder"],
        "bootstrap_replicates": replicates,
        "bootstrap_interval_rows": len(interval_rows),
        "missing_imputed": False,
        "validated_predictor_claim": False,
        "design_based_ratio_of_record_replaced": False,
        "new_solver_runs": False,
        "task_reselection": False,
        "source_labels_mutated": False,
        "internal_only": True,
    }
    stable_json_dump(report, output_directory / "report.json")
    text = f"""# ML-10A Instance Space Analysis — internal final v2

Status: complete internal descriptive artifact. The accepted ML-9A transform,
projection, coordinates, and boundary remain fixed; no PySCF outcome refit the
space. Five method footprints use only gradeable attempted cells, while the
ladder-plus-PySCF portfolio remains defined for all 96 panel tasks.

CCSD(T), the named practical boundary, has {ccsdt['solved_tasks']} known panel
solves and a normalized TRACE area of {float(ccsdt['area_normalized']):.6f}.
The known five-method PySCF union adds
{combined['unique_additions_vs_ladder']} solves beyond the ladder union, so the
combined portfolio remains at {combined['known_solved_tasks']} known panel
solves.

Panel PYTHIA gates pass for {report['panel_pythia_gates_passed']}/
{report['panel_pythia_gates_total']} targets. External nonpanel validation
passes the same descriptive accuracy gate for
{report['external_validation_gates_passed']}/
{report['external_validation_gates_total']} PySCF methods. Failures remain
reported as feature-adequacy findings; no validated-predictor claim is made.

Intervals use {replicates} canonical-family block bootstrap draws per target,
conditional on the fixed projection and each target's observed coverage. Raw
draws are retained. Missing cells are not imputed. No solver run, task
reselection, source-label mutation, ratio replacement, public placement, or
push occurred.
"""
    (output_directory / "REPORT.md").write_text(text, encoding="utf-8")
    _write_manifest(
        output_directory,
        "ml10a_instance_space_manifest_v2",
        preregistration_path,
        data.input_hashes,
    )
    return report
