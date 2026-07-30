"""Verified post-G59 panel refresh for solver-family ML."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from qb_gsee_benchmark.ml.core_set import _require, sha256_file
from qb_gsee_benchmark.ml.g50_solver_families import (
    canonical_family_map,
    g50_variant_rows,
    load_preregistration,
    resolve_input_path,
)
from qb_gsee_benchmark.ml.g50_solver_families_run import (
    _load_tasks,
    _scored_observation,
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _verify_path(path: Path, expected: str, label: str) -> None:
    _require(path.is_file(), f"missing {label}: {path}")
    _require(sha256_file(path) == expected, f"{label} changed")


def _verify_harvest_sums(directory: Path) -> dict[str, str]:
    path = directory / "SHA256SUMS"
    _require(path.is_file(), f"missing G59 harvest checksums: {path}")
    expected: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        digest, name = raw.split("  ", 1)
        _require(name not in expected, f"duplicate G59 checksum entry: {name}")
        expected[name] = digest
    required = {
        "README.md",
        "build_g59_harvest.py",
        "PARENT_ATTEMPTS.csv",
        "VARIANT_OBSERVATIONS.csv",
        "TERMINAL_CELLS.csv",
        "HARVEST_MANIFEST.json",
    }
    _require(set(expected) == required, "G59 harvest checksum member set changed")
    for name, digest in expected.items():
        _verify_path(directory / name, digest, f"G59 harvest member {name}")
    return expected


def load_g59_panel_refresh(
    root: Path,
    amendment_path: Path,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Load, verify, and merge the accepted G50 baseline with G59 results."""

    amendment = _read_json(amendment_path)
    _require(
        amendment.get("amendment_id") == "ml_g59_panel_refresh_amendment_v1",
        "wrong G59 panel-refresh amendment",
    )
    _require(amendment.get("frozen_before_refit") is True, "unfrozen G59 amendment")

    parent = amendment["parent_analysis"]
    preregistration_path = root / parent["preregistration_path"]
    parent_manifest_path = root / parent["final_manifest_path"]
    baseline_observations_path = root / parent["normalized_observations_path"]
    baseline_coverage_path = root / parent["coverage_path"]
    _verify_path(
        preregistration_path, parent["preregistration_sha256"], "parent preregistration"
    )
    _verify_path(
        parent_manifest_path, parent["final_manifest_sha256"], "parent final manifest"
    )
    _verify_path(
        baseline_observations_path,
        parent["normalized_observations_sha256"],
        "parent normalized observations",
    )
    _verify_path(baseline_coverage_path, parent["coverage_sha256"], "parent coverage")

    selection = amendment["selection_of_record"]
    selection_manifest_path = root / selection["manifest_path"]
    panel_path = root / selection["panel_path"]
    _verify_path(
        selection_manifest_path,
        selection["manifest_sha256"],
        "selection-of-record manifest",
    )
    _verify_path(panel_path, selection["panel_sha256"], "panel of record")

    acquisition = amendment["g59_acquisition_contract"]
    required_path = Path(acquisition["required_attempts_external_path"])
    scope_path = Path(acquisition["scope_external_path"])
    builder_path = Path(acquisition["harvest_builder_external_path"])
    harvest_manifest_path = Path(acquisition["harvest_manifest_external_path"])
    harvest_rows_path = Path(acquisition["variant_observations_external_path"])
    terminal_cells_path = Path(acquisition["terminal_cells_external_path"])
    _verify_path(required_path, acquisition["required_attempts_sha256"], "G59 attempts")
    _verify_path(scope_path, acquisition["scope_sha256"], "G59 scope")
    _verify_path(builder_path, acquisition["harvest_builder_sha256"], "G59 harvester")
    checksums = _verify_harvest_sums(harvest_manifest_path.parent)

    harvest_manifest = _read_json(harvest_manifest_path)
    census = harvest_manifest["census"]
    complete = harvest_manifest.get("status") == "complete"
    if require_complete:
        _require(complete, "G59 harvest is not complete")
        _require(
            harvest_manifest.get("final_archive_emitted") is True,
            "complete G59 harvest lacks final archive",
        )
    _require(
        int(census["required_attempts"])
        == int(acquisition["required_parent_attempts"]),
        "G59 parent census changed",
    )
    _require(
        int(census["expanded_variant_rows"])
        == int(acquisition["required_expanded_variant_rows"]),
        "G59 expanded variant census changed",
    )
    _require(
        int(census["terminal_cells"]) == int(acquisition["required_terminal_cells"]),
        "G59 terminal census changed",
    )
    _require(
        int(census["dmrg_terminal_cells"])
        == int(acquisition["required_dmrg_terminal_cells"]),
        "G59 DMRG terminal census changed",
    )

    preregistration = load_preregistration(preregistration_path)
    taxonomy = _read_json(
        resolve_input_path(root, preregistration["inputs"]["canonical_families"])
    )
    canonical = canonical_family_map(taxonomy)
    tasks = _load_tasks(root)
    variants = g50_variant_rows(
        resolve_input_path(root, preregistration["inputs"]["solver_family_catalog"])
    )
    variant_by_uuid = {str(row["solver_uuid"]): row for row in variants}

    panel_rows = _read_csv(panel_path)
    _require(len(panel_rows) == int(selection["selected_tasks"]) == 96, "panel drift")
    _require(
        len({row["task_uuid"] for row in panel_rows}) == 96, "duplicate panel task"
    )
    panel_tasks = {row["task_uuid"] for row in panel_rows}
    retained_tasks = {
        row["task_uuid"] for row in panel_rows if row["origin"] == "retained_incumbent"
    }
    entering_tasks = {
        row["task_uuid"] for row in panel_rows if row["origin"] == "farthest_first_pick"
    }
    _require(
        len(retained_tasks) == 80 and len(entering_tasks) == 16, "panel origins drift"
    )
    weights = {row["task_uuid"]: int(row["selection_weight_609"]) for row in panel_rows}
    _require(
        sum(weights.values()) == int(selection["selection_weight_sum"]) == 609,
        "weight drift",
    )

    baseline_observations = _read_csv(baseline_observations_path)
    baseline_coverage = _read_csv(baseline_coverage_path)
    _require(len(baseline_observations) == 1728, "baseline observation census changed")
    _require(len(baseline_coverage) == 1728, "baseline coverage census changed")
    baseline_tasks = {row["task_uuid"] for row in baseline_observations}
    _require(len(baseline_tasks) == 96, "baseline task census changed")
    _require(
        len(baseline_tasks - panel_tasks) == int(selection["leaving_tasks"]) == 16,
        "leaving task census changed",
    )
    _require(
        panel_tasks - baseline_tasks == entering_tasks, "entering task identity changed"
    )

    required_rows = _read_csv(required_path)
    required_pairs = {
        (row["task_uuid"], row["solver_family_id"]) for row in required_rows
    }
    _require(
        len(required_rows) == len(required_pairs) == 86, "G59 required pairs drift"
    )
    harvest_rows = _read_csv(harvest_rows_path)
    terminal_rows = _read_csv(terminal_cells_path)
    _require(len(harvest_rows) == 408, "G59 variant row census changed")
    _require(len(terminal_rows) == 86, "G59 terminal row census changed")
    harvest_pairs = {
        (row["task_uuid"], row["solver_family_id"]) for row in harvest_rows
    }
    _require(harvest_pairs == required_pairs, "G59 harvested pair coverage changed")
    if require_complete:
        _require(
            {row["label_ready"] for row in harvest_rows} == {"true"},
            "G59 harvest contains pending labels",
        )

    expected_per_family = {"dmrg": 4, "shci": 5, "trimci": 8, "ipie_afqmc": 1}
    pair_counts = Counter(
        (row["task_uuid"], row["solver_family_id"]) for row in harvest_rows
    )
    _require(
        all(
            count == expected_per_family[family]
            for (_, family), count in pair_counts.items()
        ),
        "G59 family expansion changed",
    )

    observations = [
        row
        for row in baseline_observations
        if row["task_uuid"] in panel_tasks
        and (row["task_uuid"], row["solver_family_id"]) not in required_pairs
    ]
    coverage = [
        row
        for row in baseline_coverage
        if row["task_uuid"] in panel_tasks
        and (row["task_uuid"], row["solver_family_id"]) not in required_pairs
    ]
    baseline_rows_retained = len(observations)

    for row in harvest_rows:
        if row["label_ready"] != "true":
            continue
        task_uuid = row["task_uuid"]
        variant = variant_by_uuid.get(row["solver_uuid"])
        _require(
            variant is not None, f"unknown G59 solver variant: {row['solver_uuid']}"
        )
        for field in ("solver_family_id", "solver_short_name", "solver_variant_id"):
            _require(
                str(row[field]) == str(variant[field]), f"G59 variant {field} drift"
            )
        _require(
            task_uuid in panel_tasks and task_uuid in tasks, "unknown G59 panel task"
        )
        status = row["variant_observation_status"]
        observed = bool(row["energy_hartree"])
        _require(
            observed == status.startswith("observed_"),
            f"G59 observation status/energy mismatch: {task_uuid}/{row['solver_uuid']}",
        )
        reason = (
            None
            if observed
            else (
                "bounded_attempt_ended_before_milestone"
                if status == "bounded_failure_unreached"
                else "bounded_parent_failed_before_terminal_result"
            )
        )
        observation = _scored_observation(
            task_uuid=task_uuid,
            task=tasks[task_uuid],
            canonical_family=canonical[task_uuid],
            variant=variant,
            energy=float(row["energy_hartree"]) if observed else None,
            source=row["observation_source"],
            reason_override=reason,
            raw_status=row["parent_terminal_state"],
            force_fail=not observed,
        )
        if not observed:
            observation["metric_outcome_annotation"] = "indeterminate"
            observation["metric_status_annotation"] = "indeterminate"
        observations.append(observation)
        coverage.append(
            {
                "task_uuid": task_uuid,
                "canonical_family": canonical[task_uuid],
                "solver_family_id": variant["solver_family_id"],
                "solver_short_name": variant["solver_short_name"],
                "solver_uuid": variant["solver_uuid"],
                "solver_variant_id": variant["solver_variant_id"],
                "resource_ladder_id": variant["resource_ladder_id"],
                "resource_value": variant["resource_value"],
                "coverage_status": status,
                "coverage_reason": f"g59_parent:{row['parent_terminal_state']}",
                "enters_binary_label_table": True,
            }
        )

    observation_keys = {(row["task_uuid"], row["solver_uuid"]) for row in observations}
    coverage_keys = {(row["task_uuid"], row["solver_uuid"]) for row in coverage}
    if require_complete:
        _require(
            len(observations) == len(observation_keys) == 1728,
            "merged label census changed",
        )
        _require(
            len(coverage) == len(coverage_keys) == 1728,
            "merged coverage census changed",
        )
        per_task = Counter(row["task_uuid"] for row in observations)
        per_variant = Counter(row["solver_uuid"] for row in observations)
        _require(
            set(per_task) == panel_tasks and set(per_task.values()) == {18},
            "merged task coverage changed",
        )
        _require(
            len(per_variant) == 18 and set(per_variant.values()) == {96},
            "merged variant coverage changed",
        )
        _require(
            {row["observed_outcome"] for row in observations} <= {"fail", "success"},
            "non-binary merged label",
        )

    observations.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["task_uuid"],
        )
    )
    coverage.sort(
        key=lambda row: (
            row["solver_family_id"],
            row["solver_short_name"],
            row["task_uuid"],
        )
    )
    preflight = {
        "artifact_id": "ml_g59_panel_refresh_preflight_v1",
        "status": "pass" if complete else "incomplete_waiting_for_required_attempts",
        "complete_harvest": complete,
        "scientific_outcomes_consumed": True,
        "model_fitted": False,
        "checks": {
            "amendment_frozen": True,
            "parent_hashes_verified": True,
            "selection_of_record_hashes_verified": True,
            "g59_contract_hashes_verified": True,
            "harvest_member_hashes_verified": True,
            "exact_required_pair_coverage": True,
            "exact_variant_expansion": True,
            "complete_binary_panel": complete,
            "no_monotonic_repair": True,
        },
        "census": {
            "panel_tasks": len(panel_tasks),
            "retained_tasks": len(retained_tasks),
            "entering_tasks": len(entering_tasks),
            "required_parent_attempts": len(required_pairs),
            "harvest_variant_rows": len(harvest_rows),
            "baseline_rows_retained": baseline_rows_retained,
            "merged_rows": len(observations),
            "selection_weight_sum": sum(weights.values()),
        },
    }
    return {
        "amendment": amendment,
        "observations": observations,
        "coverage": coverage,
        "selection_weights": weights,
        "terminal_cells_path": terminal_cells_path,
        "preflight": preflight,
        "input_hashes": {
            "amendment": sha256_file(amendment_path),
            "harvest_manifest": checksums["HARVEST_MANIFEST.json"],
            "harvest_variant_observations": checksums["VARIANT_OBSERVATIONS.csv"],
            "harvest_terminal_cells": checksums["TERMINAL_CELLS.csv"],
        },
    }


def panel_refresh_analysis_revision(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Return deterministic metadata consumed by the shared finalizer."""

    return {
        "analysis_revision_id": "ml_g59_panel_refresh_v1",
        "report_artifact_id": "ml_g59_solver_family_solvability_v1",
        "manifest_artifact_id": "ml_g59_solver_family_solvability_manifest_v1",
        "selection_weight_sum": 609,
        "preflight": dict(bundle["preflight"]),
        "input_hashes": dict(bundle["input_hashes"]),
        "merge_policy": dict(bundle["amendment"]["merge_policy"]),
    }
