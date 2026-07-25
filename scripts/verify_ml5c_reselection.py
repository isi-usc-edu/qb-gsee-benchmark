#!/usr/bin/env python
"""Independent verifier for the ML-8B / ML-5c gradeable reselection.

Re-derives the candidate set from the census, rebuilds the primary metric from
the pinned metadata, independently reimplements global farthest-first and the
nearest-center Voronoi assignment, and checks that the emitted selection,
both weight sets, the delta against the manifest of record, the bill of
materials, the family census, and the deployment layer all reproduce. Does not
import the run module. Fails closed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator


class VerificationError(RuntimeError):
    pass


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _tie_rank(task_uuid: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{task_uuid}".encode()).hexdigest()


def _farthest_first(distance: np.ndarray, tasks: list[str], k: int, seed: int) -> list[int]:
    """Independent restatement of the frozen selector."""
    scores = -np.mean(distance, axis=1)

    def pick(candidates: list[int], values: np.ndarray) -> int:
        best = max(float(values[index]) for index in candidates)
        tied = [
            index
            for index in candidates
            if abs(float(values[index]) - best) <= 1e-12 + 1e-12 * abs(best)
        ]
        return min(tied, key=lambda index: (_tie_rank(tasks[index], seed), tasks[index]))

    first = pick(list(range(len(tasks))), scores)
    selected = [first]
    nearest = distance[:, first].copy()
    while len(selected) < k:
        remaining = [index for index in range(len(tasks)) if index not in set(selected)]
        chosen = pick(remaining, nearest)
        selected.append(chosen)
        nearest = np.minimum(nearest, distance[:, chosen])
    return selected


def _assign(distance: np.ndarray, centers: list[int], tasks: list[str], seed: int):
    assignments = []
    distances = []
    for index in range(len(tasks)):
        values = distance[index, centers]
        minimum = float(np.min(values))
        tied = [
            center
            for center, value in zip(centers, values)
            if abs(float(value) - minimum) <= 1e-12 + 1e-12 * abs(minimum)
        ]
        chosen = min(tied, key=lambda c: (_tie_rank(tasks[c], seed), tasks[c]))
        assignments.append(chosen)
        distances.append(float(distance[index, chosen]))
    return assignments, distances


def verify(root: Path, artifact: Path) -> dict[str, Any]:
    import sys

    sys.path.insert(0, str(root / "src"))
    from qb_gsee_benchmark.ml.core_set import block_aware_distance, build_block_models
    from qb_gsee_benchmark.ml.g50_solver_families import derive_feature_policy

    report = json.loads((artifact / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (artifact / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    candidate_manifest = json.loads(
        (artifact / "candidate_manifest.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (artifact / "schemas/report.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(report)
    checks = 1

    # 1. held state
    for payload in (report, manifest, candidate_manifest):
        _check(payload["status"] == "held_pending_pi_ack", "not held")
        _check(payload["binding_selection"] is False, "binding_selection must be false")
        _check(
            payload["campaign_scope_manifest_of_record"] is False,
            "must not claim manifest of record",
        )
        checks += 3
    _check(report["supersedes"] is None, "claims to supersede something")
    _check(report["outcome_blind"] is True, "not outcome-blind")
    _check(report["family_used_for_selection"] is False, "family used for selection")
    _check(candidate_manifest["chosen_mode"] is None, "a mode was chosen")
    checks += 4

    # 2. pinned inputs
    for name, specification in sorted(report["inputs"].items()):
        path = root / str(specification["path"])
        _check(path.is_file(), f"missing input: {name}")
        _check(_sha256(path) == str(specification["sha256"]), f"input drift: {name}")
        checks += 1

    # 3. candidate set re-derived from the census
    census = {
        str(row["task_uuid"]): row
        for row in _rows(root / str(report["inputs"]["gradeability_census"]["path"]))
    }
    features = pd.read_csv(
        root / str(report["inputs"]["feature_table"]["path"]), low_memory=False
    )
    tasks = [str(value) for value in features["task_uuid"]]
    candidates = [
        task
        for task in tasks
        if census[task]["gradeable_for_campaign_scoring"].lower() == "true"
    ]
    _check(
        len(candidates) == int(report["candidates"]["candidates"]),
        "candidate count mismatch",
    )
    _check(
        len(tasks) - len(candidates) == int(report["candidates"]["excluded"]),
        "excluded count mismatch",
    )
    checks += 2

    # 4. rebuild the primary metric and independently reselect
    metadata = pd.read_csv(
        root / str(report["inputs"]["feature_metadata_ml5_191"]["path"])
    )
    identifiers = json.loads(
        (root / str(report["inputs"]["identifier_screen"]["path"])).read_text(
            encoding="utf-8"
        )
    )["identifier_columns"]
    policy = derive_feature_policy(metadata, identifiers)
    _check(
        len(policy["selected"]) == int(report["metric"]["n_columns"]),
        f"metric column count: {len(policy['selected'])}",
    )
    models = build_block_models(
        features,
        metadata,
        list(policy["selected"]),
        scaling=str(report["metric"]["scaling"]),
        variance_threshold=float(report["metric"]["pca_variance_threshold"]),
        universal_only=False,
    )
    distance, shared = block_aware_distance(len(features), models)
    index_of = {task: index for index, task in enumerate(tasks)}
    local = [index_of[task] for task in candidates]
    _check(
        int(shared[np.ix_(local, local)].min())
        == int(report["candidates"]["minimum_shared_blocks_among_candidates"]),
        "candidate shared-block minimum mismatch",
    )
    submatrix = distance[np.ix_(local, local)]
    seed = int(report["metric"]["seed"])
    k = int(candidate_manifest["chosen_k"])
    recomputed = _farthest_first(submatrix, list(candidates), k, seed)
    recomputed_tasks = [candidates[position] for position in recomputed]
    checks += 2

    selected = _rows(artifact / "selected_tasks.csv")
    primary_mode = str(candidate_manifest["primary_mode"])
    primary_rows = [row for row in selected if row["mode"] == primary_mode]
    _check(len(primary_rows) == k, f"primary selection size: {len(primary_rows)}")
    published_order = [
        row["task_uuid"]
        for row in sorted(primary_rows, key=lambda row: int(row["selection_order"]))
    ]
    _check(
        published_order == recomputed_tasks,
        "independent farthest-first reselection does not reproduce the published order",
    )
    _check(
        sorted(map(str, candidate_manifest["primary_selected_task_uuids"]))
        == sorted(recomputed_tasks),
        "candidate manifest selection mismatch",
    )
    for row in selected:
        _check(
            row["gradeable_for_campaign_scoring"].lower() == "true",
            f"non-gradeable center: {row['task_uuid']}",
        )
        _check(row["binding_selection"].lower() == "false", "center claims binding")
        checks += 2
    checks += 4

    # 5. both weight sets recomputed
    centers = [index_of[task] for task in recomputed_tasks]
    scored_assign, scored_distance = _assign(distance, centers, tasks, seed)
    scored_counts: Counter[str] = Counter()
    for task in candidates:
        scored_counts[tasks[scored_assign[index_of[task]]]] += 1
    published_weights = {
        str(row["task_uuid"]): int(row["selection_weight"])
        for row in _rows(artifact / "selection_weights_609.csv")
    }
    _check(set(published_weights) == set(recomputed_tasks), "weight row coverage")
    for task, weight in sorted(published_weights.items()):
        _check(
            weight == int(scored_counts.get(task, 0)),
            f"scored weight mismatch at {task}: {weight} != {scored_counts.get(task, 0)}",
        )
        checks += 1
    _check(
        sum(published_weights.values()) == len(candidates),
        "scored weights do not sum to the candidate set",
    )
    for row in _rows(artifact / "selection_weights_609.csv"):
        _check(
            row["admissible_for_population_statements"].lower() == "true",
            "scored weight row not marked admissible",
        )
        _check(row["population"] == "gradeable_candidates_609", "wrong population label")
        checks += 2

    coverage = _rows(artifact / "coverage_map_718.csv")
    _check(len(coverage) == len(tasks), "coverage map size")
    coverage_counts: Counter[str] = Counter()
    for row in coverage:
        task = str(row["task_uuid"])
        expected_center = tasks[scored_assign[index_of[task]]]
        _check(
            str(row["assigned_center_task_uuid"]) == expected_center,
            f"coverage assignment mismatch: {task}",
        )
        _check(
            row["admissible_for_population_statements"].lower() == "false",
            "coverage row wrongly marked admissible for population statements",
        )
        _check(
            row["role"] == "coverage_and_deployment_map_only", "coverage role label"
        )
        coverage_counts[expected_center] += 1
        checks += 3
    _check(sum(coverage_counts.values()) == len(tasks), "coverage weights sum")
    checks += 5

    # 6. delta and bill of materials
    binding_weights = {
        str(row["task_uuid"]): int(row["selection_weight"])
        for row in _rows(
            root / str(report["inputs"]["binding_selection_weights_718"]["path"])
        )
    }
    incumbents = set(binding_weights)
    _check(len(incumbents) == k, "incumbent panel size")
    delta = [row for row in _rows(artifact / "delta_vs_binding_manifest.csv") if row["mode"] == primary_mode]
    chosen_set = set(recomputed_tasks)
    expected = {
        "retained": sorted(chosen_set & incumbents),
        "leaving": sorted(incumbents - chosen_set),
        "entering": sorted(chosen_set - incumbents),
    }
    for disposition, members in expected.items():
        published = sorted(
            str(row["task_uuid"]) for row in delta if row["disposition"] == disposition
        )
        _check(published == members, f"delta {disposition} mismatch")
        _check(
            int(report["modes"][primary_mode][disposition]) == len(members),
            f"delta {disposition} count mismatch",
        )
        checks += 2
    bom = [row for row in _rows(artifact / "rerun_bill_of_materials.csv") if row["mode"] == primary_mode]
    families = sorted({str(row["solver_family_id"]) for row in bom}) if bom else []
    _check(
        len(bom) == len(expected["entering"]) * (len(families) if families else 0),
        "bill of materials is not entering x locked solver identities",
    )
    _check(
        int(report["modes"][primary_mode]["rerun_cells"]) == len(bom),
        "rerun cell count mismatch",
    )
    for row in bom:
        _check(
            row["solver_identity_locked"].lower() == "true",
            "bill of materials row does not lock the solver identity",
        )
        _check(
            str(row["task_uuid"]) in set(expected["entering"]),
            "bill of materials names a non-entering task",
        )
        checks += 2
    checks += 3

    # 7. zero-gradeable families carry no scored weight
    zero = {
        str(record["canonical_family"])
        for record in report["zero_gradeable_families"]["families"]
    }
    family_of = {
        str(row["task_uuid"]): str(row["canonical_family"])
        for row in _rows(artifact / "coverage_map_718.csv")
    }
    attributed = sum(
        weight for task, weight in published_weights.items() if family_of[task] in zero
    )
    _check(attributed == 0, "scored weight attributed to a zero-gradeable family")
    _check(
        int(report["zero_gradeable_families"]["scored_weight_attributed"]) == 0,
        "report claims nonzero zero-gradeable weight",
    )
    for row in _rows(artifact / "family_census.csv"):
        if str(row["canonical_family"]) in zero:
            _check(
                int(row["n_gradeable_tasks"]) == 0,
                f"zero-gradeable family has gradeable tasks: {row['canonical_family']}",
            )
            _check(
                row["carries_population_statements"].lower() == "false",
                "zero-gradeable family claims population statements",
            )
        _check(row["role"] == "reporting_only_never_a_constraint", "family role label")
        checks += 1
    checks += 2

    # 8. deployment-target layer
    deployment = _rows(artifact / "deployment_target_estimates.csv")
    non_gradeable = sorted(set(tasks) - set(candidates))
    variants = sorted({str(row["solver_uuid"]) for row in deployment})
    _check(
        len(deployment) == len(non_gradeable) * len(variants),
        "deployment layer is not a complete rectangle",
    )
    _check(
        sorted({str(row["task_uuid"]) for row in deployment}) == non_gradeable,
        "deployment layer task set mismatch",
    )
    posteriors = {
        (str(row["task_uuid"]), str(row["solver_uuid"])): row
        for row in _rows(root / str(report["inputs"]["ml8d_posteriors"]["path"]))
    }
    verdict = str(report["deployment_target_layer"]["adjudication_language_verbatim"])
    for row in deployment:
        key = (str(row["task_uuid"]), str(row["solver_uuid"]))
        source = posteriors[key]
        _check(
            abs(
                float(row["posterior_mean_probability_success"])
                - float(source["probability_success"])
            )
            <= 1e-12,
            f"deployment posterior mismatch: {key}",
        )
        _check(
            abs(float(row["credible_lower_95"]) - float(source["credible_lower_95"]))
            <= 1e-12
            and abs(float(row["credible_upper_95"]) - float(source["credible_upper_95"]))
            <= 1e-12,
            f"deployment credible interval mismatch: {key}",
        )
        _check(row["output_kind"] == "estimate", "deployment row not an estimate")
        _check(
            row["validated_predictor_claim"].lower() == "false",
            "deployment row claims a validated predictor",
        )
        _check(row["calibration_verdict"] == verdict, "adjudication language altered")
        expected_center = tasks[scored_assign[index_of[str(row["task_uuid"])]]]
        _check(
            str(row["assigned_center_task_uuid"]) == expected_center,
            f"deployment center mismatch: {key}",
        )
        checks += 6
    _check(
        int(report["deployment_target_layer"]["calibration_certified_variants"]) == 0,
        "a variant is claimed calibrated",
    )
    _check(
        report["deployment_target_layer"]["ratio_of_record"] == "design_based",
        "ratio of record altered",
    )
    checks += 4

    # 9. sensitivity overlap recomputed
    sensitivity_metadata = pd.read_csv(
        root / str(report["inputs"]["feature_metadata_current_193"]["path"])
    )
    sensitivity_policy = derive_feature_policy(sensitivity_metadata, identifiers)
    _check(
        len(sensitivity_policy["selected"])
        == int(report["sensitivity_193_columns"]["n_columns"]),
        "sensitivity column count mismatch",
    )
    sensitivity_models = build_block_models(
        features,
        sensitivity_metadata,
        list(sensitivity_policy["selected"]),
        scaling=str(report["metric"]["scaling"]),
        variance_threshold=float(report["metric"]["pca_variance_threshold"]),
        universal_only=False,
    )
    sensitivity_distance, _ = block_aware_distance(len(features), sensitivity_models)
    sensitivity_selected = _farthest_first(
        sensitivity_distance[np.ix_(local, local)], list(candidates), k, seed
    )
    sensitivity_tasks = {candidates[position] for position in sensitivity_selected}
    overlap = sorted(chosen_set & sensitivity_tasks)
    _check(
        len(overlap) == int(report["sensitivity_193_columns"]["overlap_count"]),
        f"sensitivity overlap mismatch: {len(overlap)}",
    )
    _check(
        sorted(map(str, report["sensitivity_193_columns"]["primary_only_task_uuids"]))
        == sorted(chosen_set - sensitivity_tasks),
        "sensitivity primary-only list mismatch",
    )
    checks += 3

    # 10. manifest hashes
    declared = {
        str(record["path"]): (int(record["bytes"]), str(record["sha256"]))
        for record in manifest["files"]
    }
    present = sorted(
        str(path.relative_to(artifact))
        for path in artifact.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    _check(present == sorted(declared), "manifest file list mismatch")
    for relative, (size, digest) in sorted(declared.items()):
        path = artifact / relative
        _check(path.stat().st_size == size, f"manifest byte count: {relative}")
        _check(_sha256(path) == digest, f"manifest hash: {relative}")
        checks += 2

    return {
        "status": "VERIFIED",
        "checks": checks,
        "candidates": len(candidates),
        "k": k,
        "retained": len(expected["retained"]),
        "leaving": len(expected["leaving"]),
        "entering": len(expected["entering"]),
        "rerun_cells": len(bom),
        "sensitivity_overlap": len(overlap),
        "deployment_rows": len(deployment),
        "binding_selection": report["binding_selection"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact", type=Path, default=Path("analysis/ml_core_set_v2/held_v1")
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    artifact = arguments.artifact
    if not artifact.is_absolute():
        artifact = root / artifact
    try:
        result = verify(root, artifact)
    except Exception as error:  # noqa: BLE001 - fail closed by design
        print(json.dumps({"status": "FAILED", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
