"""ML-8C gradeable-mask sensitivity annex to the G50 ``final_v4`` analysis.

Reruns the accepted solver-family analysis with the fail-by-construction panel
tasks masked, so the 0/18 physics-over-size-sector verdict can be checked
against label decontamination before the paper hardens it.

Every model, seed, baseline, metric, floor, and feature-policy decision is
imported from the frozen parent implementation rather than restated -- the mask
is the only difference, and the run asserts that by reproducing the parent's
1,728-row observation table byte-identically before masking anything.

This annex supersedes nothing; ``final_v4`` remains the analysis of record.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator

from qb_gsee_benchmark.ml.core_set import (
    _require,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.g50_solver_families import (
    canonical_family_map,
    derive_feature_policy,
    g50_variant_rows,
    load_preregistration,
    resolve_input_path,
    verify_inputs,
)
from qb_gsee_benchmark.ml.core_set import block_aware_distance, build_block_models
from qb_gsee_benchmark.ml.g50_solver_families_run import (
    ARMS,
    DELTA_COLUMNS,
    ELIGIBILITY_COLUMNS,
    GROWTH_COLUMNS,
    MODEL_ID,
    NESTEDNESS_COLUMNS,
    OBSERVATION_COLUMNS,
    PERFORMANCE_COLUMNS,
    PREDICTION_COLUMNS,
    PROTOCOL_ID,
    binary_counts,
    bootstrap_variant,
    build_nestedness_table,
    build_size_sector_frame,
    load_rung_recovery_amendment,
    load_size_sector_amendment,
    load_trimci_bounded_rung_amendment,
    lofo_knn_probabilities,
    lofo_prevalence_probabilities,
    lofo_size_sector_probabilities,
    normalize_g50_outcomes,
    variant_eligibility,
)

PREREGISTRATION_ID = "ml8c_gradeable_mask_sensitivity_preregistration_v1"
ANNEX_ID = "ml8c_gradeable_mask_sensitivity_v1"

EXPECTED_PANEL_TASKS = 96
EXPECTED_MASKED_TASKS = 16
EXPECTED_RETAINED_TASKS = 80
EXPECTED_CORPUS_TASKS = 718

GRADEABLE_WEIGHT_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "gradeable_selection_weight",
    "parent_selection_weight_718",
    "weight_definition",
]
COMPARISON_COLUMNS = [
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "solver_variant_id",
    "resource_ladder_id",
    "resource_value",
    "n_labels_before",
    "n_labels_after",
    "n_success_before",
    "n_success_after",
    "n_fail_before",
    "n_fail_after",
    "model_status_before",
    "model_status_after",
    "with_jw_vs_size_sector_ap_delta_before",
    "with_jw_vs_size_sector_ap_delta_after",
    "with_jw_vs_size_sector_ap_lower_95_before",
    "with_jw_vs_size_sector_ap_lower_95_after",
    "with_jw_vs_without_jw_ap_delta_before",
    "with_jw_vs_without_jw_ap_delta_after",
    "with_jw_vs_without_jw_ap_lower_95_before",
    "with_jw_vs_without_jw_ap_lower_95_after",
]
GRADEABLE_GROWTH_COLUMNS = [
    *GROWTH_COLUMNS[: GROWTH_COLUMNS.index("selection_weighted_population_success_rate")],
    "gradeable_selection_weighted_population_success_rate",
    "gradeable_population_rate_status",
    *GROWTH_COLUMNS[GROWTH_COLUMNS.index("population_rate_status") + 1 :],
]


def load_sensitivity_preregistration(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(
        payload.get("artifact_id") == PREREGISTRATION_ID,
        "wrong ML-8C preregistration",
    )
    _require(
        payload.get("frozen_before_masked_results") is True,
        "ML-8C preregistration is not frozen",
    )
    _require(payload.get("supersedes") is None, "annex must supersede nothing")
    return payload


def verify_sensitivity_inputs(
    root: Path, preregistration: Mapping[str, Any]
) -> dict[str, dict[str, str]]:
    resolved: dict[str, dict[str, str]] = {}
    for name, specification in sorted(preregistration["inputs"].items()):
        declared = specification.get("sha256")
        path = root / str(specification["path"])
        _require(path.is_file(), f"missing ML-8C input: {name}")
        digest = sha256_file(path)
        if declared:
            _require(
                digest == str(declared), f"ML-8C input hash drift: {name} -> {digest}"
            )
        resolved[name] = {"path": str(specification["path"]), "sha256": digest}
    return resolved


def load_mask(
    root: Path, preregistration: Mapping[str, Any], panel_tasks: Sequence[str]
) -> dict[str, Any]:
    """Derive the masked task set from the ML-8A census; never hand-listed."""
    census = pd.read_csv(
        root / str(preregistration["inputs"]["gradeability_census"]["path"])
    )
    gradeable = {
        str(row.task_uuid): bool(row.gradeable_for_campaign_scoring)
        for row in census.itertuples(index=False)
    }
    reason = {
        str(row.task_uuid): str(row.gradeability_reason)
        for row in census.itertuples(index=False)
    }
    panel = sorted(set(map(str, panel_tasks)))
    specification = preregistration["mask"]
    _require(
        len(panel) == int(specification["expected_panel_tasks"]),
        f"panel task census changed: {len(panel)}",
    )
    missing = [task for task in panel if task not in gradeable]
    _require(not missing, f"panel tasks absent from census: {missing[:3]}")
    retained = sorted(task for task in panel if gradeable[task])
    masked = sorted(task for task in panel if not gradeable[task])
    _require(
        len(masked) == int(specification["expected_masked_tasks"]),
        f"masked task count changed: {len(masked)}",
    )
    _require(
        len(retained) == int(specification["expected_retained_tasks"]),
        f"retained task count changed: {len(retained)}",
    )

    report = json.loads(
        (
            root
            / str(preregistration["inputs"]["gradeability_census_report"]["path"])
        ).read_text(encoding="utf-8")
    )
    declared = sorted(
        map(str, report["panel_cross_check"]["not_gradeable_task_uuids"])
    )
    _require(
        declared == masked,
        "mask disagrees with the census panel cross-check",
    )
    return {
        "retained": retained,
        "masked": masked,
        "masked_reasons": {task: reason[task] for task in masked},
        "census_gradeable_total": int(sum(gradeable.values())),
    }


def gradeable_selection_weights(
    root: Path,
    preregistration: Mapping[str, Any],
    retained: Sequence[str],
    census_gradeable: Mapping[str, bool],
) -> dict[str, Any]:
    """Restrict the frozen Voronoi assignment to the gradeable population.

    Orphaned gradeable tasks -- those whose frozen nearest-selected center is
    masked -- are disclosed, never reassigned.
    """
    assignments = pd.read_csv(
        root / str(preregistration["inputs"]["coverage_assignments_718"]["path"])
    )
    _require(
        len(assignments) == EXPECTED_CORPUS_TASKS,
        f"assignment row count changed: {len(assignments)}",
    )
    retained_set = set(map(str, retained))
    weights = Counter()
    orphaned: list[str] = []
    covered = 0
    for row in assignments.itertuples(index=False):
        task = str(row.task_uuid)
        center = str(row.selected_task_uuid)
        if not census_gradeable.get(task, False):
            continue
        if center in retained_set:
            weights[center] += 1
            covered += 1
        else:
            orphaned.append(task)
    total = int(sum(census_gradeable.values()))
    _require(
        covered + len(orphaned) == total,
        "gradeable population accounting does not close",
    )
    _require(
        set(weights) <= retained_set, "weight assigned to a non-retained center"
    )
    return {
        "weights": {center: int(weights.get(center, 0)) for center in sorted(retained_set)},
        "gradeable_population_total": total,
        "gradeable_population_covered": covered,
        "gradeable_population_orphaned": len(orphaned),
        "gradeable_population_coverage_fraction": covered / float(total),
        "orphaned_task_uuids": sorted(orphaned),
    }


def build_gradeable_growth_table(
    variants: Sequence[Mapping[str, Any]],
    observations: pd.DataFrame,
    coverage: pd.DataFrame,
    predictions: pd.DataFrame,
    retained_tasks: set[str],
    weights: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Observed ladder table over the retained panel with restated weights."""
    denominator = float(sum(weights.values()))
    _require(denominator > 0, "empty gradeable weighting")
    rows: list[dict[str, Any]] = []
    for variant in variants:
        observed = observations.loc[
            observations["solver_uuid"] == variant["solver_uuid"]
        ]
        covered = coverage.loc[coverage["solver_uuid"] == variant["solver_uuid"]]
        counts = binary_counts(observed["observed_outcome"])
        observed_tasks = set(map(str, observed["task_uuid"]))
        complete = observed_tasks == retained_tasks
        weighted_success = None
        if complete:
            success_tasks = set(
                map(
                    str,
                    observed.loc[
                        observed["observed_outcome"] == "success", "task_uuid"
                    ],
                )
            )
            weighted_success = (
                sum(weights[task] for task in success_tasks) / denominator
            )
        predicted = predictions.loc[
            (predictions["solver_uuid"] == variant["solver_uuid"])
            & (predictions["feature_arm"] == "with_jw")
        ]
        predicted_success = (
            int((predicted["predicted_outcome"] == "success").sum())
            if len(predicted)
            else None
        )
        rows.append(
            {
                "solver_family_id": variant["solver_family_id"],
                "solver_short_name": variant["solver_short_name"],
                "solver_uuid": variant["solver_uuid"],
                "solver_variant_id": variant["solver_variant_id"],
                "resource_ladder_id": variant["resource_ladder_id"],
                "resource_axis_name": variant["resource_axis_name"],
                "resource_value": variant["resource_value"],
                "resource_units": variant["resource_units"],
                "resource_rank": variant["resource_rank"],
                "potential_cells": len(covered),
                "labeled_cells": len(observed),
                "coverage_fraction": len(observed) / len(covered),
                "n_success": counts["success"],
                "n_fail": counts["fail"],
                "selected_sample_success_rate": (
                    counts["success"] / len(observed) if len(observed) else None
                ),
                "gradeable_selection_weighted_population_success_rate": weighted_success,
                "gradeable_population_rate_status": (
                    "estimated_covered_gradeable_subpopulation_80_task_panel"
                    if complete
                    else "not_estimable_incomplete_or_censored_panel"
                ),
                "predicted_success_tasks_with_jw": predicted_success,
                "predicted_success_rate_with_jw": (
                    predicted_success / float(EXPECTED_CORPUS_TASKS)
                    if predicted_success is not None
                    else None
                ),
            }
        )
    return rows


def _ap_delta(
    deltas: pd.DataFrame, solver_uuid: str, comparison: str
) -> tuple[float | None, float | None]:
    subset = deltas.loc[
        (deltas["solver_uuid"].astype(str) == str(solver_uuid))
        & (deltas["comparison"].astype(str) == comparison)
        & (deltas["metric"].astype(str) == "average_precision_success")
    ]
    if not len(subset):
        return None, None
    _require(len(subset) == 1, f"duplicate delta row: {solver_uuid}/{comparison}")
    row = subset.iloc[0]
    return float(row["delta"]), float(row["lower_95"])


def build_comparison_table(
    variants: Sequence[Mapping[str, Any]],
    parent_eligibility: pd.DataFrame,
    parent_deltas: pd.DataFrame,
    masked_eligibility: Sequence[Mapping[str, Any]],
    masked_deltas: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    masked_frame = pd.DataFrame(masked_deltas) if masked_deltas else pd.DataFrame(
        columns=["solver_uuid", "comparison", "metric", "delta", "lower_95"]
    )
    masked_by_uuid = {str(row["solver_uuid"]): row for row in masked_eligibility}
    parent_by_uuid = {
        str(row.solver_uuid): row for row in parent_eligibility.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for variant in variants:
        uuid = str(variant["solver_uuid"])
        before = parent_by_uuid[uuid]
        after = masked_by_uuid[uuid]
        record = {
            "solver_family_id": variant["solver_family_id"],
            "solver_short_name": variant["solver_short_name"],
            "solver_uuid": uuid,
            "solver_variant_id": variant["solver_variant_id"],
            "resource_ladder_id": variant["resource_ladder_id"],
            "resource_value": variant["resource_value"],
            "n_labels_before": int(before.n_labels),
            "n_labels_after": int(after["n_labels"]),
            "n_success_before": int(before.n_success),
            "n_success_after": int(after["n_success"]),
            "n_fail_before": int(before.n_fail),
            "n_fail_after": int(after["n_fail"]),
            "model_status_before": str(before.model_status),
            "model_status_after": str(after["model_status"]),
        }
        for comparison, label in (
            ("with_jw_vs_size_sector", "with_jw_vs_size_sector_ap"),
            ("with_jw_vs_without_jw", "with_jw_vs_without_jw_ap"),
        ):
            delta_before, lower_before = _ap_delta(parent_deltas, uuid, comparison)
            delta_after, lower_after = _ap_delta(masked_frame, uuid, comparison)
            record[f"{label}_delta_before"] = delta_before
            record[f"{label}_delta_after"] = delta_after
            record[f"{label}_lower_95_before"] = lower_before
            record[f"{label}_lower_95_after"] = lower_after
        rows.append(record)
    rows.sort(key=lambda row: (row["solver_family_id"], row["solver_short_name"]))
    return rows


def _positive_lower_bound_count(
    deltas: Sequence[Mapping[str, Any]] | pd.DataFrame, comparison: str
) -> int:
    frame = pd.DataFrame(deltas) if not isinstance(deltas, pd.DataFrame) else deltas
    if not len(frame):
        return 0
    subset = frame.loc[
        (frame["comparison"].astype(str) == comparison)
        & (frame["metric"].astype(str) == "average_precision_success")
    ]
    return int(sum(float(value) > 0.0 for value in subset["lower_95"]))


def _report_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://qb-gsee-benchmark/analysis/ml_g50_solver_families/sensitivity_gradeable_mask_v1/report.schema.json",
        "title": "ML-8C gradeable-mask sensitivity annex report",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "artifact_id",
            "status",
            "release_class",
            "supersedes",
            "parent_analysis_of_record",
            "parent_bytes_unchanged_claim",
            "validated_predictor_claim",
            "family_used_as_model_input",
            "mask",
            "panel",
            "gradeable_population",
            "signals",
            "parent_signals",
            "negative_verdict_survives_decontamination",
            "stop_at_triggered",
            "eligibility_changes",
            "equivalence_guard",
            "bootstrap_attempts_by_variant",
            "label_policy",
            "inputs",
            "preregistration",
        ],
        "properties": {
            "artifact_id": {"const": ANNEX_ID},
            "status": {"const": "complete_internal_sensitivity_annex_no_gate"},
            "release_class": {"const": "internal_sensitivity_annex"},
            "supersedes": {"type": "null"},
            "parent_analysis_of_record": {"type": "string"},
            "parent_bytes_unchanged_claim": {"const": True},
            "validated_predictor_claim": {"const": False},
            "family_used_as_model_input": {"const": False},
            "mask": {"type": "object"},
            "panel": {"type": "object"},
            "gradeable_population": {"type": "object"},
            "signals": {"type": "object"},
            "parent_signals": {"type": "object"},
            "negative_verdict_survives_decontamination": {"type": "boolean"},
            "stop_at_triggered": {"type": "boolean"},
            "eligibility_changes": {"type": "array"},
            "equivalence_guard": {"type": "object"},
            "bootstrap_attempts_by_variant": {"type": "object"},
            "label_policy": {"type": "object"},
            "inputs": {"type": "object"},
            "preregistration": {"type": "object"},
        },
    }


def _markdown_report(
    report: Mapping[str, Any], comparison: Sequence[Mapping[str, Any]]
) -> str:
    panel = report["panel"]
    population = report["gradeable_population"]
    signals = report["signals"]
    parent = report["parent_signals"]
    lines = [
        "# ML-8C gradeable-mask sensitivity annex to `final_v4`",
        "",
        "Internal sensitivity annex. **Supersedes nothing** — `final_v4` remains",
        "the analysis of record and its bytes are unchanged. Rerun of the accepted",
        "solver-family analysis with the fail-by-construction panel tasks masked,",
        "to test whether the 0/18 negative verdict survives label",
        "decontamination.",
        "",
        "## Mask",
        "",
        f"- panel tasks: {panel['panel_tasks']}",
        f"- masked (not gradeable for campaign scoring): "
        f"**{panel['masked_tasks']}**",
        f"- retained denominator: **{panel['retained_tasks']}**",
        f"- labeled cells: {panel['parent_labeled_cells']} → "
        f"**{panel['masked_labeled_cells']}**",
        f"- masked cells removed: {panel['removed_cells']}, of which "
        f"{panel['removed_success_cells']} were successes and "
        f"{panel['removed_fail_cells']} were failures",
        "",
        "The mask is derived from the ML-8A census, not hand-listed. Masked tasks",
        "and their reasons:",
        "",
        "| task_uuid | reason |",
        "|---|---|",
    ]
    for task, reason in sorted(report["mask"]["masked_reasons"].items()):
        lines.append(f"| `{task}` | `{reason}` |")
    lines += [
        "",
        "## Equivalence guard",
        "",
        "Before masking, the run regenerated the parent observation table and",
        f"compared it byte-for-byte to the pinned `final_v4` table: "
        f"**{'IDENTICAL' if report['equivalence_guard']['byte_identical'] else 'MISMATCH'}**.",
        "The mask is therefore the only difference from the parent analysis.",
        "",
        "## Gradeable-population reweighting",
        "",
        f"- gradeable corpus population: {population['gradeable_population_total']}",
        f"- covered by a retained center: "
        f"**{population['gradeable_population_covered']}** "
        f"({population['gradeable_population_coverage_fraction']:.6f})",
        f"- orphaned (frozen nearest center is masked; disclosed, never "
        f"reassigned): **{population['gradeable_population_orphaned']}**",
        "",
        "Restated population rates estimate the **covered** gradeable",
        "subpopulation, not all",
        f"{population['gradeable_population_total']} gradeable tasks. The parent",
        "`/96` corpus-weighted rates are quoted unchanged from `final_v4`;",
        "neither denominator is presented alone.",
        "",
        "## Headline verdict",
        "",
        "| counter | `final_v4` | masked |",
        "|---|---|---|",
        f"| variants whose with-JW AP beats the size-sector baseline "
        f"(95% lower bound > 0) | "
        f"{parent['with_jw_ap_lower_bound_above_size_sector_count']}/"
        f"{parent['eligible_variant_denominator']} | "
        f"**{signals['with_jw_ap_lower_bound_above_size_sector_count']}/"
        f"{signals['eligible_variant_denominator']}** |",
        f"| variants where adding JW features improves AP "
        f"(95% lower bound > 0) | "
        f"{parent['with_jw_ap_lower_bound_above_without_jw_count']}/"
        f"{parent['eligible_variant_denominator']} | "
        f"**{signals['with_jw_ap_lower_bound_above_without_jw_count']}/"
        f"{signals['eligible_variant_denominator']}** |",
        "",
        f"`negative_verdict_survives_decontamination`: "
        f"**{str(report['negative_verdict_survives_decontamination']).lower()}**",
        "",
    ]
    if report["stop_at_triggered"]:
        lines += [
            "> **STOP-AT TRIGGERED — FLAG FOR PI.** At least one variant's",
            "> physics-over-size-sector average-precision paired delta has a 95%",
            "> lower bound above zero under this mask. Numbers are reported",
            "> plainly below and in `paired_deltas.csv`; no interpretation, paper",
            "> framing, or predictor claim is offered here.",
            "",
        ]
    else:
        lines += [
            "STOP-AT not triggered: no variant's physics-over-size-sector",
            "average-precision paired delta has a 95% lower bound above zero",
            "under the mask.",
            "",
        ]
    changes = report["eligibility_changes"]
    lines += ["## Eligibility changes", ""]
    if changes:
        lines += ["| variant | before | after |", "|---|---|---|"]
        for change in changes:
            lines.append(
                f"| `{change['solver_short_name']}` | "
                f"{change['model_status_before']} | {change['model_status_after']} |"
            )
    else:
        lines.append(
            "None: every variant keeps its parent eligibility status under the "
            "unchanged floor."
        )
    lines += [
        "",
        "## Per-variant physics-over-size-sector average precision",
        "",
        "| variant | labels | successes | AP delta (parent) | 95% lower (parent) "
        "| AP delta (masked) | 95% lower (masked) |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in comparison:
        def _format(value: Any) -> str:
            return "—" if value is None else f"{float(value):+.6f}"

        lines.append(
            f"| `{row['solver_short_name']}` | "
            f"{row['n_labels_before']}→{row['n_labels_after']} | "
            f"{row['n_success_before']}→{row['n_success_after']} | "
            f"{_format(row['with_jw_vs_size_sector_ap_delta_before'])} | "
            f"{_format(row['with_jw_vs_size_sector_ap_lower_95_before'])} | "
            f"{_format(row['with_jw_vs_size_sector_ap_delta_after'])} | "
            f"{_format(row['with_jw_vs_size_sector_ap_lower_95_after'])} |"
        )
    lines += [
        "",
        "## Fences honoured",
        "",
        "- supersedes nothing; `final_v4` bytes unchanged",
        "- no metric, tolerance, seed, floor, model, or label-policy change",
        "- no reselection, reassignment, or new solver run",
        "- internal annex only: no public or dashboard placement",
        "- canonical family is grouping and reporting only, never a model input",
        "- no validated-predictor claim is made or implied",
        "",
    ]
    return "\n".join(lines)


def run_gradeable_mask_sensitivity(
    root: Path,
    sensitivity_preregistration_path: Path,
    output_directory: Path,
) -> dict[str, Any]:
    """Execute one complete deterministic ML-8C sensitivity run."""
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    sensitivity = load_sensitivity_preregistration(sensitivity_preregistration_path)
    sensitivity_inputs = verify_sensitivity_inputs(root, sensitivity)

    parent_directory = root / "analysis/ml_g50_solver_families"
    preregistration_path = parent_directory / "preregistration.json"
    preregistration = load_preregistration(preregistration_path)
    verify_inputs(root, preregistration)
    _, backfill = load_size_sector_amendment(
        root,
        parent_directory / "amendment_size_sector_backfill.json",
        preregistration_path,
    )
    _, rung_recovery = load_rung_recovery_amendment(
        root, parent_directory / "amendment_rung_ledger_recovery.json"
    )
    trimci_amendment, trimci_recovery = load_trimci_bounded_rung_amendment(
        root,
        parent_directory / "amendment_trimci_bounded_rung_semantics.json",
        preregistration_path,
    )

    features = pd.read_csv(
        resolve_input_path(root, preregistration["inputs"]["feature_table"]),
        low_memory=False,
    )
    metadata = pd.read_csv(
        resolve_input_path(root, preregistration["inputs"]["feature_metadata"])
    )
    taxonomy = json.loads(
        resolve_input_path(
            root, preregistration["inputs"]["canonical_families"]
        ).read_text(encoding="utf-8")
    )
    identifiers = json.loads(
        resolve_input_path(
            root, preregistration["inputs"]["identifier_screen"]
        ).read_text(encoding="utf-8")
    )["identifier_columns"]
    canonical = canonical_family_map(taxonomy)
    tasks = list(map(str, features["task_uuid"]))
    _require(
        len(tasks) == len(set(tasks)) == EXPECTED_CORPUS_TASKS,
        "feature task census changed",
    )
    families = np.asarray([canonical[task] for task in tasks], dtype=object)
    task_index = {task: index for index, task in enumerate(tasks)}
    policy = derive_feature_policy(metadata, identifiers)
    size_sector = build_size_sector_frame(features, backfill).reindex(tasks)

    variants = g50_variant_rows(
        resolve_input_path(root, preregistration["inputs"]["solver_family_catalog"])
    )
    observations, coverage_rows = normalize_g50_outcomes(
        root,
        preregistration,
        variants,
        canonical,
        rung_recovery,
        trimci_recovery,
    )
    parent_frame = pd.DataFrame(observations)
    coverage_frame = pd.DataFrame(coverage_rows)

    # Equivalence guard: prove the mask is the only difference.
    output_directory.mkdir(parents=True, exist_ok=False)
    guard_path = output_directory / "_parent_observations_regenerated.csv"
    stable_csv_dump(observations, OBSERVATION_COLUMNS, guard_path)
    parent_observations_path = root / str(
        sensitivity["inputs"]["parent_normalized_observations"]["path"]
    )
    regenerated_digest = sha256_file(guard_path)
    parent_digest = sha256_file(parent_observations_path)
    guard_path.unlink()
    equivalence = {
        "regenerated_sha256": regenerated_digest,
        "parent_sha256": parent_digest,
        "byte_identical": regenerated_digest == parent_digest,
    }
    _require(
        equivalence["byte_identical"],
        "regenerated parent observations differ from the pinned final_v4 table",
    )

    panel_tasks = sorted(set(map(str, parent_frame["task_uuid"])))
    mask = load_mask(root, sensitivity, panel_tasks)
    retained = set(mask["retained"])
    masked_set = set(mask["masked"])

    census = pd.read_csv(
        root / str(sensitivity["inputs"]["gradeability_census"]["path"])
    )
    census_gradeable = {
        str(row.task_uuid): bool(row.gradeable_for_campaign_scoring)
        for row in census.itertuples(index=False)
    }
    population = gradeable_selection_weights(
        root, sensitivity, mask["retained"], census_gradeable
    )
    weights = population["weights"]

    removed = parent_frame.loc[parent_frame["task_uuid"].astype(str).isin(masked_set)]
    masked_frame = (
        parent_frame.loc[parent_frame["task_uuid"].astype(str).isin(retained)]
        .sort_values(["solver_uuid", "task_uuid"], kind="stable")
        .reset_index(drop=True)
    )
    _require(
        len(masked_frame) + len(removed) == len(parent_frame),
        "mask partition does not close",
    )

    geometry_cache: dict[tuple[str, ...], np.ndarray] = {}
    distances: dict[tuple[str, str], np.ndarray] = {}
    for solver_family, columns in sorted(policy["solver_family_columns"].items()):
        for arm, arm_columns in (
            ("with_jw", columns),
            ("without_jw", sorted(set(columns) - set(policy["jw"]))),
        ):
            key = tuple(arm_columns)
            if key not in geometry_cache:
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
                geometry_cache[key] = block_aware_distance(len(features), models)[0]
            distances[(solver_family, arm)] = geometry_cache[key]

    eligibility = variant_eligibility(
        masked_frame, variants, preregistration["model_eligibility_floor"]
    )
    eligibility_by_uuid = {str(row["solver_uuid"]): row for row in eligibility}

    prediction_rows: list[dict[str, Any]] = []
    performance_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    bootstrap_attempts: dict[str, int] = {}
    for variant in variants:
        status = eligibility_by_uuid[str(variant["solver_uuid"])]
        if status["model_status"] != "eligible":
            continue
        data = masked_frame.loc[
            masked_frame["solver_uuid"] == variant["solver_uuid"]
        ].sort_values("task_uuid", kind="stable")
        training_indices = np.asarray(
            [task_index[str(task)] for task in data["task_uuid"]], dtype=int
        )
        y = data["observed_outcome"].eq("success").to_numpy(dtype=int)
        label_families = families[training_indices]
        prevalence = lofo_prevalence_probabilities(training_indices, y, families)
        ridge = lofo_size_sector_probabilities(
            size_sector,
            training_indices,
            y,
            families,
            seed=int(preregistration["seeds"]["model"]),
        )
        full_probabilities: dict[str, np.ndarray] = {}
        for arm in ARMS:
            full_probabilities[arm] = lofo_knn_probabilities(
                distances[(str(variant["solver_family_id"]), arm)],
                training_indices,
                y,
                families,
                tasks,
                k=int(preregistration["model"]["k"]),
            )
        probability_sets = {
            ("physics_knn", "with_jw"): full_probabilities["with_jw"][training_indices],
            ("physics_knn", "without_jw"): full_probabilities["without_jw"][
                training_indices
            ],
            ("lofo_prevalence", "not_applicable"): prevalence[training_indices],
            ("lofo_size_sector_ridge", "not_applicable"): ridge[training_indices],
        }
        performance, deltas, attempted = bootstrap_variant(
            variant=variant,
            y=y,
            families=label_families,
            probability_sets=probability_sets,
            resamples=int(preregistration["bootstrap"]["accepted_two_class_draws"]),
            seed=int(preregistration["bootstrap"]["seed"]),
        )
        performance_rows.extend(performance)
        delta_rows.extend(deltas)
        bootstrap_attempts[str(variant["solver_short_name"])] = attempted
        for index, task_uuid in enumerate(tasks):
            for arm in ARMS:
                probability_success = float(full_probabilities[arm][index])
                predicted = "success" if probability_success > 0.5 else "fail"
                prediction_rows.append(
                    {
                        "task_uuid": task_uuid,
                        "canonical_family": canonical[task_uuid],
                        "solver_family_id": variant["solver_family_id"],
                        "solver_family_uuid": variant["solver_family_uuid"],
                        "solver_short_name": variant["solver_short_name"],
                        "solver_uuid": variant["solver_uuid"],
                        "solver_variant_id": variant["solver_variant_id"],
                        "resource_ladder_id": variant["resource_ladder_id"],
                        "resource_value": variant["resource_value"],
                        "feature_arm": arm,
                        "model": MODEL_ID,
                        "protocol": PROTOCOL_ID,
                        "prediction_kind": "leave_one_canonical_family_out",
                        "predicted_outcome": predicted,
                        "predicted_probability": (
                            probability_success
                            if predicted == "success"
                            else 1.0 - probability_success
                        ),
                        "probability_fail": 1.0 - probability_success,
                        "probability_success": probability_success,
                        "family_used_as_model_input": False,
                        "n_training_labels": len(y),
                        "n_training_families": len(set(map(str, label_families))),
                    }
                )

    prediction_rows.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["task_uuid"],
            row["feature_arm"],
        )
    )
    performance_rows.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["estimator"],
            row["feature_arm"],
            row["metric"],
        )
    )
    delta_rows.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["comparison"],
            row["metric"],
        )
    )
    prediction_frame = pd.DataFrame(prediction_rows)

    growth = build_gradeable_growth_table(
        variants, masked_frame, coverage_frame, prediction_frame, retained, weights
    )
    nestedness = build_nestedness_table(
        variants, masked_frame, prediction_frame, retained, weights
    )

    parent_eligibility = pd.read_csv(
        parent_directory / "final_v4/variant_eligibility.csv"
    )
    parent_deltas = pd.read_csv(parent_directory / "final_v4/paired_deltas.csv")
    comparison = build_comparison_table(
        variants, parent_eligibility, parent_deltas, eligibility, delta_rows
    )
    eligibility_changes = [
        {
            "solver_short_name": row["solver_short_name"],
            "solver_uuid": row["solver_uuid"],
            "model_status_before": row["model_status_before"],
            "model_status_after": row["model_status_after"],
        }
        for row in comparison
        if row["model_status_before"] != row["model_status_after"]
    ]

    eligible_count = sum(row["model_status"] == "eligible" for row in eligibility)
    _require(
        len(prediction_rows) == eligible_count * EXPECTED_CORPUS_TASKS * len(ARMS),
        "prediction row count does not match the eligible variant census",
    )
    prediction_schema = json.loads(
        (parent_directory / "predictions.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(prediction_schema).validate(prediction_rows)

    signals = {
        "with_jw_ap_lower_bound_above_size_sector_count": _positive_lower_bound_count(
            delta_rows, "with_jw_vs_size_sector"
        ),
        "with_jw_ap_lower_bound_above_without_jw_count": _positive_lower_bound_count(
            delta_rows, "with_jw_vs_without_jw"
        ),
        "eligible_variant_denominator": eligible_count,
        "interpretation": "descriptive_only_no_multiplicity_claim",
    }
    parent_signals = {
        "with_jw_ap_lower_bound_above_size_sector_count": _positive_lower_bound_count(
            parent_deltas, "with_jw_vs_size_sector"
        ),
        "with_jw_ap_lower_bound_above_without_jw_count": _positive_lower_bound_count(
            parent_deltas, "with_jw_vs_without_jw"
        ),
        "eligible_variant_denominator": int(
            (parent_eligibility["model_status"] == "eligible").sum()
        ),
    }
    stop_at = signals["with_jw_ap_lower_bound_above_size_sector_count"] > 0
    removed_counts = Counter(map(str, removed["observed_outcome"]))

    report = {
        "artifact_id": ANNEX_ID,
        "status": "complete_internal_sensitivity_annex_no_gate",
        "release_class": "internal_sensitivity_annex",
        "supersedes": None,
        "parent_analysis_of_record": "analysis/ml_g50_solver_families/final_v4",
        "parent_bytes_unchanged_claim": True,
        "validated_predictor_claim": False,
        "family_used_as_model_input": False,
        "mask": {
            "derived_from_census": True,
            "hand_listed": False,
            "masked_task_uuids": mask["masked"],
            "masked_reasons": mask["masked_reasons"],
            "retained_task_uuids": mask["retained"],
        },
        "panel": {
            "panel_tasks": len(panel_tasks),
            "masked_tasks": len(mask["masked"]),
            "retained_tasks": len(mask["retained"]),
            "parent_labeled_cells": len(parent_frame),
            "masked_labeled_cells": len(masked_frame),
            "removed_cells": len(removed),
            "removed_success_cells": int(removed_counts.get("success", 0)),
            "removed_fail_cells": int(removed_counts.get("fail", 0)),
            "analysis_variants": len(variants),
            "eligible_variants": eligible_count,
            "prediction_rows": len(prediction_rows),
            "canonical_families_in_labels": len(
                set(map(str, masked_frame["canonical_family"]))
            ),
        },
        "gradeable_population": {
            key: population[key]
            for key in (
                "gradeable_population_total",
                "gradeable_population_covered",
                "gradeable_population_orphaned",
                "gradeable_population_coverage_fraction",
                "orphaned_task_uuids",
            )
        }
        | {
            "weight_definition": "count of gradeable corpus tasks whose frozen nearest-selected center is this task",
            "orphan_policy": "disclosed_never_reassigned",
            "estimand": "covered_gradeable_subpopulation",
            "restated_weight_sum": int(sum(weights.values())),
            "max_restated_weight": int(max(weights.values())),
            "min_restated_weight": int(min(weights.values())),
        },
        "signals": signals,
        "parent_signals": parent_signals,
        "negative_verdict_survives_decontamination": (
            signals["with_jw_ap_lower_bound_above_size_sector_count"] == 0
            and signals["with_jw_ap_lower_bound_above_without_jw_count"] == 0
        ),
        "stop_at_triggered": stop_at,
        "eligibility_changes": eligibility_changes,
        "equivalence_guard": equivalence,
        "bootstrap_attempts_by_variant": bootstrap_attempts,
        "label_policy": {
            **preregistration["label_policy"],
            "trimci_unobserved_recovery_rung": "bounded_binary_fail_no_energy",
            "trimci_bounded_rung_amendment": trimci_amendment["artifact_id"],
        },
        "inputs": sensitivity_inputs,
        "preregistration": {
            "artifact_id": sensitivity["artifact_id"],
            "path": str(sensitivity_preregistration_path.relative_to(root)),
            "sha256": sha256_file(sensitivity_preregistration_path),
        },
    }
    Draft202012Validator(_report_schema()).validate(report)

    weight_rows = [
        {
            "task_uuid": task,
            "canonical_family": canonical[task],
            "gradeable_selection_weight": weights[task],
            "parent_selection_weight_718": None,
            "weight_definition": "gradeable_population_feature_space_voronoi_cluster_size",
        }
        for task in sorted(weights)
    ]
    parent_weight_frame = pd.read_csv(
        resolve_input_path(root, preregistration["inputs"]["selection_weights"])
    )
    parent_weights = {
        str(row.task_uuid): int(row.selection_weight)
        for row in parent_weight_frame.itertuples(index=False)
    }
    for row in weight_rows:
        row["parent_selection_weight_718"] = parent_weights[str(row["task_uuid"])]

    stable_csv_dump(
        masked_frame.to_dict(orient="records"),
        OBSERVATION_COLUMNS,
        output_directory / "masked_observations.csv",
    )
    stable_csv_dump(
        eligibility, ELIGIBILITY_COLUMNS, output_directory / "variant_eligibility.csv"
    )
    stable_csv_dump(
        performance_rows,
        PERFORMANCE_COLUMNS,
        output_directory / "family_balanced_performance.csv",
    )
    stable_csv_dump(delta_rows, DELTA_COLUMNS, output_directory / "paired_deltas.csv")
    stable_csv_dump(
        growth, GRADEABLE_GROWTH_COLUMNS, output_directory / "ladder_growth.csv"
    )
    stable_csv_dump(
        nestedness, NESTEDNESS_COLUMNS, output_directory / "nestedness.csv"
    )
    stable_csv_dump(
        weight_rows,
        GRADEABLE_WEIGHT_COLUMNS,
        output_directory / "gradeable_selection_weights.csv",
    )
    stable_csv_dump(
        comparison, COMPARISON_COLUMNS, output_directory / "comparison_vs_final_v4.csv"
    )
    stable_csv_dump(
        prediction_rows, PREDICTION_COLUMNS, output_directory / "predictions.csv"
    )
    stable_json_dump(report, output_directory / "report.json")
    stable_json_dump(
        _report_schema(), output_directory / "schemas/report.schema.json"
    )
    (output_directory / "REPORT.md").write_text(
        _markdown_report(report, comparison), encoding="utf-8"
    )

    manifest_files = sorted(
        path
        for path in output_directory.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    manifest = {
        "artifact_id": "ml8c_gradeable_mask_sensitivity_manifest_v1",
        "release_class": "internal_sensitivity_annex",
        "supersedes": None,
        "parent_analysis_of_record": "analysis/ml_g50_solver_families/final_v4",
        "files": [
            {
                "path": str(path.relative_to(output_directory)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in manifest_files
        ],
    }
    stable_json_dump(manifest, output_directory / "artifact_manifest.json")
    return {"report": report, "comparison": comparison, "manifest": manifest}
