"""ML-8B / ML-5c gradeable-eligible core-set reselection.

Reselects the k=96 floor_free campaign panel over the gradeable candidate set
established by the accepted ML-8A census, under the unchanged binding doctrine.
The selection primitives are imported from the frozen ``core_set`` module rather
than reimplemented, so the only thing that changes is which tasks are eligible.

Held throughout: the promoted binding manifest remains the campaign-scope
manifest of record until a PI ack for ML-5c is issued and consumed.
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
    _tie_rank,
    assign_global,
    block_aware_distance,
    build_block_models,
    global_farthest_first,
    sha256_file,
    stable_csv_dump,
    stable_json_dump,
)
from qb_gsee_benchmark.ml.g50_solver_families import (
    canonical_family_map,
    derive_feature_policy,
    g50_variant_rows,
)

AMENDMENT_ID = "ml5c_gradeable_reselection_amendment_v1"
ARTIFACT_ID = "ml5c_gradeable_reselection_v1"

EXPECTED_CORPUS_TASKS = 718
EXPECTED_CANDIDATES = 609
SELECTION_K = 96
SELECTION_SEED = 20260714

PRIMARY_MODE = "pure_reselection"
SECONDARY_MODE = "retain_and_extend"

SELECTED_COLUMNS = [
    "mode",
    "selection_order",
    "task_uuid",
    "canonical_family",
    "gradeable_for_campaign_scoring",
    "in_binding_manifest",
    "origin",
    "binding_selection",
]
WEIGHT_COLUMNS = [
    "mode",
    "task_uuid",
    "canonical_family",
    "selection_weight",
    "cell_radius",
    "cell_mean_distance",
    "weight_definition",
    "population",
    "admissible_for_population_statements",
    "binding_selection",
]
ASSIGNMENT_COLUMNS = [
    "mode",
    "task_uuid",
    "canonical_family",
    "gradeable_for_campaign_scoring",
    "assigned_center_task_uuid",
    "assigned_center_canonical_family",
    "assignment_distance",
    "cross_family_assignment",
    "population",
]
COVERAGE_MAP_COLUMNS = [
    "mode",
    "task_uuid",
    "canonical_family",
    "gradeable_for_campaign_scoring",
    "assigned_center_task_uuid",
    "assignment_distance",
    "coverage_weight_contribution",
    "role",
    "admissible_for_population_statements",
]
DELTA_COLUMNS = [
    "mode",
    "task_uuid",
    "canonical_family",
    "disposition",
    "gradeable_for_campaign_scoring",
    "gradeability_reason",
    "binding_selection_weight_718",
]
BOM_COLUMNS = [
    "mode",
    "task_uuid",
    "canonical_family",
    "solver_family_id",
    "solver_family_uuid",
    "solver_identity_locked",
]
CURVE_COLUMNS = [
    "mode",
    "k",
    "coverage_radius",
    "distance_q95",
    "mean_distance",
    "median_distance",
]
FAMILY_CENSUS_COLUMNS = [
    "mode",
    "canonical_family",
    "n_corpus_tasks",
    "n_gradeable_tasks",
    "n_selected_centers",
    "selected_weight_609",
    "zero_gradeable_family",
    "carries_population_statements",
    "role",
]
DEPLOYMENT_COLUMNS = [
    "task_uuid",
    "canonical_family",
    "gradeability_reason",
    "solver_family_id",
    "solver_short_name",
    "solver_uuid",
    "posterior_mean_probability_success",
    "credible_lower_95",
    "credible_upper_95",
    "assigned_center_task_uuid",
    "assigned_center_distance",
    "output_kind",
    "validated_predictor_claim",
    "calibration_verdict",
]

CALIBRATION_VERDICT = (
    "at the accessible panel size, model calibration could be neither "
    "established nor refuted"
)


def load_amendment(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(payload.get("artifact_id") == AMENDMENT_ID, "wrong ML-5c amendment")
    _require(
        payload.get("frozen_before_selection_output") is True,
        "ML-5c amendment is not frozen",
    )
    _require(payload.get("supersedes") is None, "ML-5c must supersede nothing")
    _require(payload.get("binding_selection") is False, "amendment must not bind")
    _require(payload.get("outcome_blind") is True, "amendment must be outcome-blind")
    return payload


def verify_amendment_inputs(
    root: Path, amendment: Mapping[str, Any]
) -> dict[str, dict[str, str]]:
    resolved: dict[str, dict[str, str]] = {}
    for name, specification in sorted(amendment["inputs"].items()):
        path = root / str(specification["path"])
        _require(path.is_file(), f"missing ML-5c input: {name}")
        digest = sha256_file(path)
        _require(
            digest == str(specification["sha256"]),
            f"ML-5c input hash drift: {name} -> {digest}",
        )
        resolved[name] = {
            "path": str(specification["path"]),
            "sha256": digest,
            "role": str(specification.get("role", "")),
        }
    return resolved


def build_metric(
    features: pd.DataFrame,
    metadata: pd.DataFrame,
    identifiers: Sequence[str],
    *,
    scaling: str,
    variance_threshold: float,
) -> dict[str, Any]:
    """Derive the block-aware primary metric over the whole corpus."""
    policy = derive_feature_policy(metadata, identifiers)
    columns = list(policy["selected"])
    models = build_block_models(
        features,
        metadata,
        columns,
        scaling=scaling,
        variance_threshold=variance_threshold,
        universal_only=False,
    )
    distance, shared = block_aware_distance(len(features), models)
    return {
        "columns": columns,
        "n_columns": len(columns),
        "n_eligible": len(policy["eligible"]),
        "n_gauge_excluded": len(policy["gauge"]),
        "n_identifier_excluded": len(policy["identifiers"]),
        "n_jw": len(policy["jw"]),
        "distance": distance,
        "shared": shared,
        "blocks": len(models),
    }


def verify_candidate_metric_placement(
    shared: np.ndarray, indices: Sequence[int], tasks: Sequence[str]
) -> dict[str, Any]:
    """Task-level 'model_eligible': every candidate pair shares a block."""
    subset = shared[np.ix_(list(indices), list(indices))]
    minimum = int(subset.min())
    offenders: list[str] = []
    if minimum <= 0:
        rows, columns = np.nonzero(subset <= 0)
        offenders = sorted(
            {str(tasks[list(indices)[int(row)]]) for row in rows}
            | {str(tasks[list(indices)[int(column)]]) for column in columns}
        )
    return {
        "minimum_shared_blocks_among_candidates": minimum,
        "all_candidates_placeable": bool(minimum > 0),
        "unplaceable_task_uuids": offenders,
    }


def select_pure(
    distance: np.ndarray, candidate_indices: Sequence[int], tasks: Sequence[str], *, k: int, seed: int
) -> tuple[list[int], list[dict[str, Any]]]:
    """Global farthest-first over the candidate set, mapped back to corpus rows."""
    local = np.asarray(candidate_indices, dtype=int)
    submatrix = distance[np.ix_(local, local)]
    local_tasks = [str(tasks[index]) for index in local]
    chosen, curve = global_farthest_first(submatrix, local_tasks, max_k=k, seed=seed)
    return [int(local[position]) for position in chosen], curve


def select_retain_and_extend(
    distance: np.ndarray,
    candidate_indices: Sequence[int],
    tasks: Sequence[str],
    retained_indices: Sequence[int],
    *,
    k: int,
    seed: int,
) -> tuple[list[int], list[dict[str, Any]]]:
    """Keep the gradeable incumbents, then farthest-first the remainder."""
    local = np.asarray(candidate_indices, dtype=int)
    position_of = {int(value): position for position, value in enumerate(local)}
    for index in retained_indices:
        _require(int(index) in position_of, "retained center is not a candidate")
    submatrix = distance[np.ix_(local, local)]
    local_tasks = [str(tasks[index]) for index in local]
    selected = [position_of[int(index)] for index in retained_indices]
    _require(len(selected) <= k, "more incumbents than the budget allows")
    nearest = submatrix[:, selected].min(axis=1)
    curve = [
        {
            "k": len(selected),
            "coverage_radius": float(np.max(nearest)),
            "distance_q95": float(np.quantile(nearest, 0.95)),
            "mean_distance": float(np.mean(nearest)),
            "median_distance": float(np.median(nearest)),
        }
    ]
    selected_set = set(selected)
    while len(selected) < k:
        candidates = [
            index for index in range(len(local_tasks)) if index not in selected_set
        ]
        best = max(float(nearest[index]) for index in candidates)
        tied = [
            index
            for index in candidates
            if abs(float(nearest[index]) - best) <= 1.0e-12 + 1.0e-12 * abs(best)
        ]
        chosen = min(
            tied, key=lambda index: (_tie_rank(local_tasks[index], seed), local_tasks[index])
        )
        selected.append(chosen)
        selected_set.add(chosen)
        nearest = np.minimum(nearest, submatrix[:, chosen])
        curve.append(
            {
                "k": len(selected),
                "coverage_radius": float(np.max(nearest)),
                "distance_q95": float(np.quantile(nearest, 0.95)),
                "mean_distance": float(np.mean(nearest)),
                "median_distance": float(np.median(nearest)),
            }
        )
    return [int(local[position]) for position in selected], curve


def voronoi_weights(
    distance: np.ndarray,
    selected: Sequence[int],
    population_indices: Sequence[int],
    tasks: Sequence[str],
    *,
    seed: int,
) -> dict[str, Any]:
    """Nearest-selected-center assignment restricted to a declared population."""
    population = np.asarray(population_indices, dtype=int)
    assignments, assignment_distance = assign_global(
        distance, selected, list(map(str, tasks)), seed
    )
    counts: Counter[int] = Counter()
    radius: dict[int, float] = {}
    total: dict[int, float] = {}
    for index in population:
        center = int(assignments[index])
        counts[center] += 1
        value = float(assignment_distance[index])
        radius[center] = max(radius.get(center, 0.0), value)
        total[center] = total.get(center, 0.0) + value
    return {
        "assignments": assignments,
        "assignment_distance": assignment_distance,
        "counts": {int(center): int(counts.get(int(center), 0)) for center in selected},
        "radius": {int(center): float(radius.get(int(center), 0.0)) for center in selected},
        "mean_distance": {
            int(center): (
                float(total.get(int(center), 0.0)) / counts[int(center)]
                if counts.get(int(center))
                else 0.0
            )
            for center in selected
        },
        "population_size": int(len(population)),
    }


def _report_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://qb-gsee-benchmark/analysis/ml_core_set_v2/report.schema.json",
        "title": "ML-5c gradeable-eligible reselection report",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "artifact_id",
            "status",
            "effective",
            "supersedes",
            "binding_selection",
            "campaign_scope_manifest_of_record",
            "manifest_of_record_unchanged",
            "outcome_blind",
            "family_used_for_selection",
            "candidates",
            "metric",
            "metric_divergence",
            "modes",
            "weight_sets",
            "zero_gradeable_families",
            "deployment_target_layer",
            "sensitivity_193_columns",
            "inputs",
            "amendment",
        ],
        "properties": {
            "artifact_id": {"const": ARTIFACT_ID},
            "status": {"const": "held_pending_pi_ack"},
            "effective": {"const": False},
            "supersedes": {"type": "null"},
            "binding_selection": {"const": False},
            "campaign_scope_manifest_of_record": {"const": False},
            "manifest_of_record_unchanged": {"type": "string"},
            "outcome_blind": {"const": True},
            "family_used_for_selection": {"const": False},
            "candidates": {"type": "object"},
            "metric": {"type": "object"},
            "metric_divergence": {"type": "object"},
            "modes": {"type": "object"},
            "weight_sets": {"type": "object"},
            "zero_gradeable_families": {"type": "object"},
            "deployment_target_layer": {"type": "object"},
            "sensitivity_193_columns": {"type": "object"},
            "inputs": {"type": "object"},
            "amendment": {"type": "object"},
        },
    }


def _markdown_report(
    report: Mapping[str, Any],
    delta_rows: Sequence[Mapping[str, Any]],
    family_rows: Sequence[Mapping[str, Any]],
) -> str:
    candidates = report["candidates"]
    modes = report["modes"]
    weights = report["weight_sets"]
    divergence = report["metric_divergence"]
    deployment = report["deployment_target_layer"]
    lines = [
        "# ML-5c gradeable-eligible reselection — HELD (pending PI ack)",
        "",
        "Reselection of the k=96 `floor_free` campaign panel over the gradeable",
        "candidate set, under the unchanged binding doctrine. **Supersedes",
        f"nothing**: `{report['manifest_of_record_unchanged'][:8]}…` remains the",
        "campaign-scope manifest of record until a PI ack for ML-5c is issued and",
        "consumed. `binding_selection` is `false` in every payload.",
        "",
        "## Candidate set",
        "",
        f"- corpus tasks: {candidates['corpus_tasks']}",
        f"- gradeable candidates (ML-8A census): **{candidates['candidates']}**",
        f"- excluded as panel-ineligible per Matt O43: {candidates['excluded']}",
        f"- every candidate placeable in the metric: "
        f"**{str(candidates['all_candidates_placeable']).lower()}** "
        f"(minimum shared blocks among candidate pairs: "
        f"{candidates['minimum_shared_blocks_among_candidates']})",
        "",
        "## Selection",
        "",
        "| mode | role | coverage radius | q95 | families hit | families unsampled |",
        "|---|---|---|---|---|---|",
    ]
    for name in (PRIMARY_MODE, SECONDARY_MODE):
        record = modes[name]
        lines.append(
            f"| `{name}` | {record['role']} | "
            f"{record['coverage_radius']:.12f} | {record['distance_q95']:.12f} | "
            f"{record['families_hit']} | {record['families_unsampled']} |"
        )
    lines += [
        "",
        "### Delta against the manifest of record",
        "",
        "| mode | retained | leaving | entering | rerun tasks | rerun cells "
        "(× 4 locked solvers) |",
        "|---|---|---|---|---|---|",
    ]
    for name in (PRIMARY_MODE, SECONDARY_MODE):
        record = modes[name]
        lines.append(
            f"| `{name}` | {record['retained']} | {record['leaving']} | "
            f"{record['entering']} | {record['entering']} | "
            f"{record['rerun_cells']} |"
        )
    lines += [
        "",
        "Solver identities are NOT reopened; the bill of materials names the four",
        "locked identities only.",
        "",
        "## Two weight sets, two populations",
        "",
        f"- `selection_weights_609` — Voronoi cluster sizes over the "
        f"{weights['selection_weights_609']['sums_to']} gradeable candidates. "
        f"**Scored-population weighting**; the only one admissible for "
        f"population success-rate statements. max weight "
        f"{weights['selection_weights_609']['max_weight']}, min "
        f"{weights['selection_weights_609']['min_weight']}.",
        f"- `coverage_weights_718` — all "
        f"{weights['coverage_weights_718']['sums_to']} corpus tasks mapped to "
        f"their nearest selected center. **Coverage/deployment map only, NOT a "
        f"scored-population weighting**; every row is labelled. max weight "
        f"{weights['coverage_weights_718']['max_weight']}.",
        "",
        "## Zero-gradeable families — no population statements",
        "",
        f"{report['zero_gradeable_families']['count']} canonical families have no "
        "gradeable task and are unrepresentable in any gradeable panel. Scored "
        f"weight attributed to them: "
        f"**{report['zero_gradeable_families']['scored_weight_attributed']}**.",
        "",
        "| canonical family | corpus tasks |",
        "|---|---|",
    ]
    for record in report["zero_gradeable_families"]["families"]:
        lines.append(
            f"| `{record['canonical_family']}` | {record['n_tasks']} |"
        )
    lines += [
        "",
        "## FLAG — 191 vs 193 column metric divergence",
        "",
        f"Pre-existing in the accepted record, not introduced here, and",
        f"scientifically material. The ML-5 binding selection used "
        f"**{divergence['ml5_binding_metric']['columns']}** columns; the accepted",
        f"G-50/ML-8C/ML-8D chain uses "
        f"**{divergence['g50_chain_metric']['columns']}**. The two extra columns",
        f"({', '.join(divergence['extra_columns'])}) are populated on only "
        f"**{divergence['extra_column_coverage']}/"
        f"{divergence['extra_column_corpus']}** tasks, so admitting them adds a",
        "narrow applicability block. The primary run uses the 191-column metric",
        "exactly as ordered, so the delta above is attributable solely to the",
        "gradeable-eligibility restriction; the 193-column run is reported as a",
        "sensitivity. ML-5c does not rule on which metric should be canonical.",
        "",
        f"Sensitivity overlap (primary vs 193-column, same mode and seed): "
        f"**{report['sensitivity_193_columns']['overlap_count']}/"
        f"{SELECTION_K}** centers shared "
        f"({report['sensitivity_193_columns']['overlap_fraction']:.6f}).",
        "",
        "## Deployment-target estimate layer",
        "",
        f"{deployment['tasks']} non-gradeable tasks × "
        f"{deployment['variants']} eligible variants = "
        f"**{deployment['rows']}** estimate rows, each carrying the ML-8D",
        "posterior mean and 95% credible interval plus the assigned nearest",
        "gradeable center. Every row is `output_kind=estimate` with",
        "`validated_predictor_claim=false`, and the ML-8D adjudication travels",
        "verbatim:",
        "",
        f"> {deployment['adjudication_language_verbatim']}",
        "",
        f"Variants certified calibrated: "
        f"**{deployment['calibration_certified_variants']}**. The design-based",
        "track remains the sole ratio of record and the ML-6",
        "no-validated-predictor rule stands unamended.",
        "",
        "## Fences honoured",
        "",
        "- held; `binding_selection=false`; no promotion commit in this wave",
        "- outcome-blind: no solver outcome, label, or metric bundle read in the",
        "  selection",
        "- family is reporting-only, never a selection or assignment input",
        "- solver identities not reopened; no solver run, submission, or PBS work",
        "",
    ]
    return "\n".join(lines)


def run_ml5c_reselection(
    root: Path, amendment_path: Path, output_directory: Path
) -> dict[str, Any]:
    """Execute one complete deterministic ML-5c reselection."""
    _require(not output_directory.exists(), f"output exists: {output_directory}")
    amendment = load_amendment(amendment_path)
    inputs = verify_amendment_inputs(root, amendment)
    doctrine = amendment["unchanged_doctrine"]

    features = pd.read_csv(
        root / inputs["feature_table"]["path"], low_memory=False
    )
    tasks = list(map(str, features["task_uuid"]))
    _require(
        len(tasks) == len(set(tasks)) == EXPECTED_CORPUS_TASKS,
        "feature task census changed",
    )
    task_index = {task: index for index, task in enumerate(tasks)}
    identifiers = json.loads(
        (root / inputs["identifier_screen"]["path"]).read_text(encoding="utf-8")
    )["identifier_columns"]
    taxonomy = json.loads(
        (root / inputs["canonical_families"]["path"]).read_text(encoding="utf-8")
    )
    canonical = canonical_family_map(taxonomy)

    census = pd.read_csv(root / inputs["gradeability_census"]["path"])
    gradeable = {
        str(row.task_uuid): bool(row.gradeable_for_campaign_scoring)
        for row in census.itertuples(index=False)
    }
    reason = {
        str(row.task_uuid): str(row.gradeability_reason)
        for row in census.itertuples(index=False)
    }
    candidate_tasks = [task for task in tasks if gradeable[task]]
    _require(
        len(candidate_tasks) == EXPECTED_CANDIDATES,
        f"candidate census changed: {len(candidate_tasks)}",
    )
    candidate_indices = [task_index[task] for task in candidate_tasks]

    primary_metadata = pd.read_csv(
        root / inputs["feature_metadata_ml5_191"]["path"]
    )
    primary = build_metric(
        features,
        primary_metadata,
        identifiers,
        scaling=str(doctrine["scaling"]),
        variance_threshold=float(doctrine["pca_variance_threshold"]),
    )
    declared = amendment["column_metric_divergence"]["ml5_binding_metric"]["columns"]
    _require(
        primary["n_columns"] == int(declared),
        f"primary metric column count {primary['n_columns']} != declared {declared}",
    )
    placement = verify_candidate_metric_placement(
        primary["shared"], candidate_indices, tasks
    )
    _require(
        placement["all_candidates_placeable"],
        f"unplaceable candidates: {placement['unplaceable_task_uuids'][:5]}",
    )

    binding = json.loads(
        (root / inputs["binding_selection_manifest"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    binding_weights = pd.read_csv(
        root / inputs["binding_selection_weights_718"]["path"]
    )
    binding_panel = sorted({str(value) for value in binding_weights["task_uuid"]})
    _require(len(binding_panel) == SELECTION_K, "binding panel census changed")
    binding_weight_by_task = {
        str(row.task_uuid): int(row.selection_weight)
        for row in binding_weights.itertuples(index=False)
    }
    incumbent_gradeable = sorted(task for task in binding_panel if gradeable[task])

    variants = g50_variant_rows(root / inputs["solver_family_catalog"]["path"])
    solver_families: dict[str, str] = {}
    for variant in variants:
        solver_families[str(variant["solver_family_id"])] = str(
            variant["solver_family_uuid"]
        )
    _require(
        len(solver_families) == int(amendment["bill_of_materials"]["locked_solver_family_count"]),
        f"locked solver family census changed: {len(solver_families)}",
    )

    selected_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    assignment_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    bom_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    modes: dict[str, Any] = {}
    selections: dict[str, list[int]] = {}

    for mode in (PRIMARY_MODE, SECONDARY_MODE):
        if mode == PRIMARY_MODE:
            chosen, curve = select_pure(
                primary["distance"],
                candidate_indices,
                tasks,
                k=SELECTION_K,
                seed=int(doctrine["seed"]),
            )
        else:
            chosen, curve = select_retain_and_extend(
                primary["distance"],
                candidate_indices,
                tasks,
                [task_index[task] for task in incumbent_gradeable],
                k=SELECTION_K,
                seed=int(doctrine["seed"]),
            )
        selections[mode] = chosen
        _require(len(set(chosen)) == SELECTION_K, f"duplicate center: {mode}")
        _require(
            all(gradeable[tasks[index]] for index in chosen),
            f"non-gradeable center selected: {mode}",
        )
        chosen_tasks = [tasks[index] for index in chosen]
        incumbent_set = set(binding_panel)
        for order, index in enumerate(chosen, start=1):
            task = tasks[index]
            selected_rows.append(
                {
                    "mode": mode,
                    "selection_order": order,
                    "task_uuid": task,
                    "canonical_family": canonical[task],
                    "gradeable_for_campaign_scoring": True,
                    "in_binding_manifest": task in incumbent_set,
                    "origin": (
                        "retained_incumbent"
                        if mode == SECONDARY_MODE and task in set(incumbent_gradeable)
                        else "farthest_first_pick"
                    ),
                    "binding_selection": False,
                }
            )
        for row in curve:
            curve_rows.append({"mode": mode, **row})

        scored = voronoi_weights(
            primary["distance"],
            chosen,
            candidate_indices,
            tasks,
            seed=int(doctrine["seed"]),
        )
        coverage = voronoi_weights(
            primary["distance"],
            chosen,
            list(range(len(tasks))),
            tasks,
            seed=int(doctrine["seed"]),
        )
        _require(
            sum(scored["counts"].values()) == EXPECTED_CANDIDATES,
            f"scored weights do not sum to the candidate set: {mode}",
        )
        _require(
            sum(coverage["counts"].values()) == EXPECTED_CORPUS_TASKS,
            f"coverage weights do not sum to the corpus: {mode}",
        )
        for index in chosen:
            task = tasks[index]
            weight_rows.append(
                {
                    "mode": mode,
                    "task_uuid": task,
                    "canonical_family": canonical[task],
                    "selection_weight": scored["counts"][int(index)],
                    "cell_radius": scored["radius"][int(index)],
                    "cell_mean_distance": scored["mean_distance"][int(index)],
                    "weight_definition": str(doctrine["weight_definition"]),
                    "population": "gradeable_candidates_609",
                    "admissible_for_population_statements": True,
                    "binding_selection": False,
                }
            )
        for index in candidate_indices:
            task = tasks[index]
            center = tasks[int(scored["assignments"][index])]
            assignment_rows.append(
                {
                    "mode": mode,
                    "task_uuid": task,
                    "canonical_family": canonical[task],
                    "gradeable_for_campaign_scoring": True,
                    "assigned_center_task_uuid": center,
                    "assigned_center_canonical_family": canonical[center],
                    "assignment_distance": float(scored["assignment_distance"][index]),
                    "cross_family_assignment": canonical[task] != canonical[center],
                    "population": "gradeable_candidates_609",
                }
            )
        for index in range(len(tasks)):
            task = tasks[index]
            center = tasks[int(coverage["assignments"][index])]
            coverage_rows.append(
                {
                    "mode": mode,
                    "task_uuid": task,
                    "canonical_family": canonical[task],
                    "gradeable_for_campaign_scoring": gradeable[task],
                    "assigned_center_task_uuid": center,
                    "assignment_distance": float(
                        coverage["assignment_distance"][index]
                    ),
                    "coverage_weight_contribution": 1,
                    "role": "coverage_and_deployment_map_only",
                    "admissible_for_population_statements": False,
                }
            )

        chosen_set = set(chosen_tasks)
        retained = sorted(chosen_set & incumbent_set)
        leaving = sorted(incumbent_set - chosen_set)
        entering = sorted(chosen_set - incumbent_set)
        for task in retained:
            delta_rows.append(
                {
                    "mode": mode,
                    "task_uuid": task,
                    "canonical_family": canonical[task],
                    "disposition": "retained",
                    "gradeable_for_campaign_scoring": gradeable[task],
                    "gradeability_reason": reason[task],
                    "binding_selection_weight_718": binding_weight_by_task.get(task),
                }
            )
        for task in leaving:
            delta_rows.append(
                {
                    "mode": mode,
                    "task_uuid": task,
                    "canonical_family": canonical[task],
                    "disposition": "leaving",
                    "gradeable_for_campaign_scoring": gradeable[task],
                    "gradeability_reason": reason[task],
                    "binding_selection_weight_718": binding_weight_by_task.get(task),
                }
            )
        for task in entering:
            delta_rows.append(
                {
                    "mode": mode,
                    "task_uuid": task,
                    "canonical_family": canonical[task],
                    "disposition": "entering",
                    "gradeable_for_campaign_scoring": gradeable[task],
                    "gradeability_reason": reason[task],
                    "binding_selection_weight_718": None,
                }
            )
            for solver_family_id in sorted(solver_families):
                bom_rows.append(
                    {
                        "mode": mode,
                        "task_uuid": task,
                        "canonical_family": canonical[task],
                        "solver_family_id": solver_family_id,
                        "solver_family_uuid": solver_families[solver_family_id],
                        "solver_identity_locked": True,
                    }
                )

        families_hit = sorted({canonical[task] for task in chosen_tasks})
        all_families = sorted(set(canonical.values()))
        modes[mode] = {
            "role": "PRIMARY" if mode == PRIMARY_MODE else "SECONDARY_LABELLED_VARIANT",
            "k": SELECTION_K,
            "coverage_radius": float(curve[-1]["coverage_radius"]),
            "distance_q95": float(curve[-1]["distance_q95"]),
            "families_hit": len(families_hit),
            "families_unsampled": len(all_families) - len(families_hit),
            "families_unsampled_list": sorted(set(all_families) - set(families_hit)),
            "retained": len(retained),
            "leaving": len(leaving),
            "entering": len(entering),
            "rerun_cells": len(entering) * len(solver_families),
            "scored_weight_sum": int(sum(scored["counts"].values())),
            "scored_weight_max": int(max(scored["counts"].values())),
            "scored_weight_min": int(min(scored["counts"].values())),
            "coverage_weight_sum": int(sum(coverage["counts"].values())),
            "coverage_weight_max": int(max(coverage["counts"].values())),
        }

    zero_families = list(amendment["zero_gradeable_families"]["families"])
    zero_names = {str(record["canonical_family"]) for record in zero_families}
    primary_weights = {
        str(row["task_uuid"]): int(row["selection_weight"])
        for row in weight_rows
        if row["mode"] == PRIMARY_MODE
    }
    scored_weight_to_zero = sum(
        weight
        for task, weight in primary_weights.items()
        if canonical[task] in zero_names
    )
    _require(
        scored_weight_to_zero == 0,
        "scored weight attributed to a zero-gradeable family",
    )

    corpus_family_counts = Counter(canonical[task] for task in tasks)
    gradeable_family_counts = Counter(canonical[task] for task in candidate_tasks)
    for mode in (PRIMARY_MODE, SECONDARY_MODE):
        centers = {tasks[index] for index in selections[mode]}
        mode_weights = {
            str(row["task_uuid"]): int(row["selection_weight"])
            for row in weight_rows
            if row["mode"] == mode
        }
        for family in sorted(corpus_family_counts):
            family_centers = [task for task in centers if canonical[task] == family]
            family_rows.append(
                {
                    "mode": mode,
                    "canonical_family": family,
                    "n_corpus_tasks": int(corpus_family_counts[family]),
                    "n_gradeable_tasks": int(gradeable_family_counts.get(family, 0)),
                    "n_selected_centers": len(family_centers),
                    "selected_weight_609": sum(
                        mode_weights[task] for task in family_centers
                    ),
                    "zero_gradeable_family": family in zero_names,
                    "carries_population_statements": family not in zero_names,
                    "role": "reporting_only_never_a_constraint",
                }
            )

    # ---- sensitivity: the 193-column current metric, identical mode and seed
    sensitivity_metadata = pd.read_csv(
        root / inputs["feature_metadata_current_193"]["path"]
    )
    sensitivity = build_metric(
        features,
        sensitivity_metadata,
        identifiers,
        scaling=str(doctrine["scaling"]),
        variance_threshold=float(doctrine["pca_variance_threshold"]),
    )
    sensitivity_chosen, _ = select_pure(
        sensitivity["distance"],
        candidate_indices,
        tasks,
        k=SELECTION_K,
        seed=int(doctrine["seed"]),
    )
    sensitivity_tasks = {tasks[index] for index in sensitivity_chosen}
    primary_tasks = {tasks[index] for index in selections[PRIMARY_MODE]}
    overlap = sorted(primary_tasks & sensitivity_tasks)

    # ---- deployment-target estimate layer
    posteriors = pd.read_csv(root / inputs["ml8d_posteriors"]["path"])
    non_gradeable = [task for task in tasks if not gradeable[task]]
    primary_assignments = {
        str(row["task_uuid"]): (
            str(row["assigned_center_task_uuid"]),
            float(row["assignment_distance"]),
        )
        for row in coverage_rows
        if row["mode"] == PRIMARY_MODE
    }
    deployment_rows: list[dict[str, Any]] = []
    subset = posteriors.loc[posteriors["task_uuid"].astype(str).isin(set(non_gradeable))]
    for row in subset.itertuples(index=False):
        task = str(row.task_uuid)
        center, distance_value = primary_assignments[task]
        deployment_rows.append(
            {
                "task_uuid": task,
                "canonical_family": canonical[task],
                "gradeability_reason": reason[task],
                "solver_family_id": str(row.solver_family_id),
                "solver_short_name": str(row.solver_short_name),
                "solver_uuid": str(row.solver_uuid),
                "posterior_mean_probability_success": float(row.probability_success),
                "credible_lower_95": float(row.credible_lower_95),
                "credible_upper_95": float(row.credible_upper_95),
                "assigned_center_task_uuid": center,
                "assigned_center_distance": distance_value,
                "output_kind": "estimate",
                "validated_predictor_claim": False,
                "calibration_verdict": CALIBRATION_VERDICT,
            }
        )
    deployment_rows.sort(
        key=lambda row: (row["task_uuid"], row["solver_family_id"], row["solver_short_name"])
    )
    deployment_variants = len({row["solver_uuid"] for row in deployment_rows})
    _require(
        len(deployment_rows) == len(non_gradeable) * deployment_variants,
        "deployment layer is not a complete task x variant rectangle",
    )

    report = {
        "artifact_id": ARTIFACT_ID,
        "status": "held_pending_pi_ack",
        "effective": False,
        "supersedes": None,
        "binding_selection": False,
        "campaign_scope_manifest_of_record": False,
        "manifest_of_record_unchanged": str(
            amendment["manifest_of_record_unchanged"]
        ),
        "outcome_blind": True,
        "family_used_for_selection": False,
        "candidates": {
            "corpus_tasks": len(tasks),
            "candidates": len(candidate_tasks),
            "excluded": len(tasks) - len(candidate_tasks),
            **placement,
        },
        "metric": {
            "n_columns": primary["n_columns"],
            "n_eligible": primary["n_eligible"],
            "n_gauge_excluded": primary["n_gauge_excluded"],
            "n_identifier_excluded": primary["n_identifier_excluded"],
            "n_jw": primary["n_jw"],
            "applicability_blocks": primary["blocks"],
            "scaling": str(doctrine["scaling"]),
            "pca_variance_threshold": float(doctrine["pca_variance_threshold"]),
            "seed": int(doctrine["seed"]),
        },
        "metric_divergence": amendment["column_metric_divergence"],
        "modes": modes,
        "weight_sets": {
            "selection_weights_609": {
                "sums_to": modes[PRIMARY_MODE]["scored_weight_sum"],
                "max_weight": modes[PRIMARY_MODE]["scored_weight_max"],
                "min_weight": modes[PRIMARY_MODE]["scored_weight_min"],
                "role": "scored_population_weighting",
                "admissible_for_population_statements": True,
            },
            "coverage_weights_718": {
                "sums_to": modes[PRIMARY_MODE]["coverage_weight_sum"],
                "max_weight": modes[PRIMARY_MODE]["coverage_weight_max"],
                "role": "coverage_and_deployment_map_only",
                "admissible_for_population_statements": False,
            },
        },
        "zero_gradeable_families": {
            "count": len(zero_families),
            "families": zero_families,
            "scored_weight_attributed": int(scored_weight_to_zero),
            "carry_population_statements": False,
        },
        "deployment_target_layer": {
            "tasks": len(non_gradeable),
            "variants": deployment_variants,
            "rows": len(deployment_rows),
            "output_kind": "estimate",
            "validated_predictor_claim": False,
            "calibration_certified_variants": 0,
            "adjudication_language_verbatim": CALIBRATION_VERDICT,
            "ratio_of_record": "design_based",
            "ml6_no_validated_predictor_rule": "stands_unamended",
        },
        "sensitivity_193_columns": {
            "n_columns": sensitivity["n_columns"],
            "n_eligible": sensitivity["n_eligible"],
            "n_jw": sensitivity["n_jw"],
            "mode": PRIMARY_MODE,
            "overlap_count": len(overlap),
            "overlap_fraction": len(overlap) / float(SELECTION_K),
            "primary_only_task_uuids": sorted(primary_tasks - sensitivity_tasks),
            "sensitivity_only_task_uuids": sorted(sensitivity_tasks - primary_tasks),
        },
        "inputs": inputs,
        "amendment": {
            "artifact_id": amendment["artifact_id"],
            "path": str(amendment_path.relative_to(root)),
            "sha256": sha256_file(amendment_path),
        },
    }
    Draft202012Validator(_report_schema()).validate(report)

    output_directory.mkdir(parents=True, exist_ok=False)
    stable_csv_dump(selected_rows, SELECTED_COLUMNS, output_directory / "selected_tasks.csv")
    stable_csv_dump(
        [row for row in weight_rows if row["mode"] == PRIMARY_MODE],
        WEIGHT_COLUMNS,
        output_directory / "selection_weights_609.csv",
    )
    stable_csv_dump(
        [row for row in assignment_rows if row["mode"] == PRIMARY_MODE],
        ASSIGNMENT_COLUMNS,
        output_directory / "coverage_assignments_609.csv",
    )
    stable_csv_dump(
        [row for row in coverage_rows if row["mode"] == PRIMARY_MODE],
        COVERAGE_MAP_COLUMNS,
        output_directory / "coverage_map_718.csv",
    )
    stable_csv_dump(
        delta_rows, DELTA_COLUMNS, output_directory / "delta_vs_binding_manifest.csv"
    )
    stable_csv_dump(bom_rows, BOM_COLUMNS, output_directory / "rerun_bill_of_materials.csv")
    stable_csv_dump(curve_rows, CURVE_COLUMNS, output_directory / "coverage_curve.csv")
    stable_csv_dump(family_rows, FAMILY_CENSUS_COLUMNS, output_directory / "family_census.csv")
    stable_csv_dump(
        deployment_rows,
        DEPLOYMENT_COLUMNS,
        output_directory / "deployment_target_estimates.csv",
    )
    secondary = output_directory / "retain_and_extend"
    stable_csv_dump(
        [row for row in weight_rows if row["mode"] == SECONDARY_MODE],
        WEIGHT_COLUMNS,
        secondary / "selection_weights_609.csv",
    )
    stable_csv_dump(
        [row for row in coverage_rows if row["mode"] == SECONDARY_MODE],
        COVERAGE_MAP_COLUMNS,
        secondary / "coverage_map_718.csv",
    )
    stable_json_dump(
        report["sensitivity_193_columns"],
        output_directory / "sensitivity_193_columns.json",
    )
    candidate_manifest = {
        "artifact_id": "ml5c_gradeable_reselection_candidate_manifest_v1",
        "status": "held_pending_pi_ack",
        "binding_selection": False,
        "campaign_scope_manifest_of_record": False,
        "effective": False,
        "manifest_of_record_unchanged": report["manifest_of_record_unchanged"],
        "chosen_k": SELECTION_K,
        "chosen_mode": None,
        "modes_offered": [PRIMARY_MODE, SECONDARY_MODE],
        "primary_mode": PRIMARY_MODE,
        "primary_selected_task_uuids": sorted(primary_tasks),
        "retain_and_extend_selected_task_uuids": sorted(
            {tasks[index] for index in selections[SECONDARY_MODE]}
        ),
        "doctrine": dict(doctrine),
        "metric": report["metric"],
        "inputs": inputs,
    }
    stable_json_dump(candidate_manifest, output_directory / "candidate_manifest.json")
    stable_json_dump(report, output_directory / "report.json")
    stable_json_dump(_report_schema(), output_directory / "schemas/report.schema.json")
    (output_directory / "REPORT.md").write_text(
        _markdown_report(report, delta_rows, family_rows), encoding="utf-8"
    )

    manifest_files = sorted(
        path
        for path in output_directory.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    manifest = {
        "artifact_id": "ml5c_gradeable_reselection_manifest_v1",
        "status": "held_pending_pi_ack",
        "binding_selection": False,
        "campaign_scope_manifest_of_record": False,
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
    return {"report": report, "manifest": manifest, "candidate_manifest": candidate_manifest}
