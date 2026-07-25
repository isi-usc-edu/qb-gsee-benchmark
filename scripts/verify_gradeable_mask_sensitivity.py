#!/usr/bin/env python
"""Independent verifier for the ML-8C gradeable-mask sensitivity annex.

Checks the annex against its inputs without importing the run module: the mask
is re-derived from the ML-8A census, the gradeable-population weights are
recounted from the frozen Voronoi assignment, every published count and
headline counter is recomputed from the emitted CSVs, the comparison table is
re-joined against the parent final_v4 artifacts, and every manifest hash and
byte count is re-verified. Fails closed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

PARENT = Path("analysis/ml_g50_solver_families/final_v4")


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


def verify(root: Path, artifact: Path) -> dict[str, Any]:
    report = json.loads((artifact / "report.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (artifact / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (artifact / "schemas/report.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(report)
    checks = 1

    # 1. annex status: supersedes nothing, no predictor claim, no family input
    _check(report["supersedes"] is None, "annex claims to supersede something")
    _check(report["release_class"] == "internal_sensitivity_annex", "wrong class")
    _check(report["validated_predictor_claim"] is False, "predictor claim present")
    _check(report["family_used_as_model_input"] is False, "family used as input")
    _check(report["parent_bytes_unchanged_claim"] is True, "parent-bytes claim absent")
    checks += 5

    # 2. pinned inputs still hash as recorded
    for name, specification in sorted(report["inputs"].items()):
        path = root / str(specification["path"])
        _check(path.is_file(), f"missing input: {name}")
        _check(_sha256(path) == str(specification["sha256"]), f"input drift: {name}")
        checks += 1

    # 3. the equivalence guard actually compared the parent table
    guard = report["equivalence_guard"]
    parent_observations = root / PARENT / "normalized_observations.csv"
    _check(
        _sha256(parent_observations) == str(guard["parent_sha256"]),
        "parent observation hash in the guard does not match disk",
    )
    _check(guard["byte_identical"] is True, "equivalence guard did not pass")
    _check(
        str(guard["regenerated_sha256"]) == str(guard["parent_sha256"]),
        "guard hashes disagree with its own verdict",
    )
    checks += 3

    # 4. re-derive the mask from the census
    census = {
        str(row["task_uuid"]): row
        for row in _rows(root / str(report["inputs"]["gradeability_census"]["path"]))
    }
    parent_panel = sorted({str(row["task_uuid"]) for row in _rows(parent_observations)})
    expected_masked = sorted(
        task
        for task in parent_panel
        if census[task]["gradeable_for_campaign_scoring"].lower() != "true"
    )
    expected_retained = sorted(set(parent_panel) - set(expected_masked))
    _check(
        sorted(map(str, report["mask"]["masked_task_uuids"])) == expected_masked,
        "masked task set mismatch",
    )
    _check(
        sorted(map(str, report["mask"]["retained_task_uuids"])) == expected_retained,
        "retained task set mismatch",
    )
    _check(report["mask"]["hand_listed"] is False, "mask claims to be hand-listed")
    for task, reason in report["mask"]["masked_reasons"].items():
        _check(
            census[str(task)]["gradeability_reason"] == str(reason),
            f"masked reason mismatch: {task}",
        )
        checks += 1
    checks += 3

    # 5. masked observation table is exactly the parent table minus the mask
    parent_rows = _rows(parent_observations)
    masked_rows = _rows(artifact / "masked_observations.csv")
    retained_set = set(expected_retained)
    rebuilt = [row for row in parent_rows if str(row["task_uuid"]) in retained_set]
    _check(len(masked_rows) == len(rebuilt), "masked row count mismatch")
    key = lambda row: (str(row["solver_uuid"]), str(row["task_uuid"]))  # noqa: E731
    _check(
        sorted(map(key, masked_rows)) == sorted(map(key, rebuilt)),
        "masked row keys differ from the parent subset",
    )
    parent_by_key = {key(row): row for row in parent_rows}
    for row in masked_rows:
        source = parent_by_key[key(row)]
        _check(
            row["observed_outcome"] == source["observed_outcome"],
            f"label changed under masking: {key(row)}",
        )
        checks += 1

    removed = [row for row in parent_rows if str(row["task_uuid"]) not in retained_set]
    removed_counts = Counter(str(row["observed_outcome"]) for row in removed)
    panel = report["panel"]
    _check(int(panel["removed_cells"]) == len(removed), "removed cell count")
    _check(
        int(panel["removed_success_cells"]) == int(removed_counts.get("success", 0)),
        "removed success count",
    )
    _check(
        int(panel["removed_fail_cells"]) == int(removed_counts.get("fail", 0)),
        "removed fail count",
    )
    _check(int(panel["masked_labeled_cells"]) == len(masked_rows), "masked cell count")
    _check(int(panel["parent_labeled_cells"]) == len(parent_rows), "parent cell count")
    _check(int(panel["retained_tasks"]) == len(expected_retained), "retained count")
    _check(int(panel["masked_tasks"]) == len(expected_masked), "masked count")
    checks += 7

    # 6. recount the gradeable-population weights from the frozen assignment
    assignments = _rows(
        root / str(report["inputs"]["coverage_assignments_718"]["path"])
    )
    gradeable = {
        task: row["gradeable_for_campaign_scoring"].lower() == "true"
        for task, row in census.items()
    }
    recounted: Counter[str] = Counter()
    orphaned: list[str] = []
    for row in assignments:
        task = str(row["task_uuid"])
        center = str(row["selected_task_uuid"])
        if not gradeable.get(task, False):
            continue
        if center in retained_set:
            recounted[center] += 1
        else:
            orphaned.append(task)
    published = {
        str(row["task_uuid"]): int(row["gradeable_selection_weight"])
        for row in _rows(artifact / "gradeable_selection_weights.csv")
    }
    _check(
        set(published) == retained_set, "weight rows do not cover the retained centers"
    )
    for center, weight in sorted(published.items()):
        _check(
            weight == int(recounted.get(center, 0)),
            f"weight mismatch at {center}: {weight} != {recounted.get(center, 0)}",
        )
        checks += 1
    population = report["gradeable_population"]
    total = sum(1 for value in gradeable.values() if value)
    _check(int(population["gradeable_population_total"]) == total, "population total")
    _check(
        int(population["gradeable_population_covered"]) == sum(recounted.values()),
        "population covered",
    )
    _check(
        int(population["gradeable_population_orphaned"]) == len(orphaned),
        "population orphaned",
    )
    _check(
        int(population["restated_weight_sum"]) == sum(published.values()),
        "restated weight sum",
    )
    _check(
        sorted(map(str, population["orphaned_task_uuids"])) == sorted(orphaned),
        "orphan list mismatch",
    )
    _check(
        population["orphan_policy"] == "disclosed_never_reassigned",
        "orphan policy string",
    )
    _check(
        int(population["gradeable_population_covered"]) + len(orphaned) == total,
        "population accounting does not close",
    )
    checks += 7

    # 7. eligibility recomputed against the unchanged parent floor
    floor = json.loads(
        (root / "analysis/ml_g50_solver_families/preregistration.json").read_text(
            encoding="utf-8"
        )
    )["model_eligibility_floor"]
    family_of = {str(row["task_uuid"]): str(row["canonical_family"]) for row in parent_rows}
    eligibility = _rows(artifact / "variant_eligibility.csv")
    by_solver: dict[str, list[dict[str, str]]] = {}
    for row in masked_rows:
        by_solver.setdefault(str(row["solver_uuid"]), []).append(row)
    for row in eligibility:
        data = by_solver.get(str(row["solver_uuid"]), [])
        counts = Counter(str(item["observed_outcome"]) for item in data)
        family_counts = Counter(family_of[str(item["task_uuid"])] for item in data)
        minimum_fold = min(
            (len(data) - count for count in family_counts.values()), default=0
        )
        expected = all(
            [
                len(data) >= int(floor["minimum_labeled_tasks"]),
                counts["success"] >= int(floor["minimum_successes"]),
                counts["fail"] >= int(floor["minimum_failures"]),
                len(family_counts) >= int(floor["minimum_families"]),
                minimum_fold >= int(floor["minimum_fold_training_tasks"]),
            ]
        )
        _check(
            int(row["n_labels"]) == len(data),
            f"eligibility n_labels: {row['solver_short_name']}",
        )
        _check(
            int(row["n_success"]) == counts["success"],
            f"eligibility n_success: {row['solver_short_name']}",
        )
        _check(
            int(row["n_fail"]) == counts["fail"],
            f"eligibility n_fail: {row['solver_short_name']}",
        )
        _check(
            row["model_status"] == ("eligible" if expected else "insufficient_data"),
            f"eligibility status: {row['solver_short_name']}",
        )
        checks += 4

    # 8. headline counters recomputed from the emitted deltas
    deltas = _rows(artifact / "paired_deltas.csv")
    for comparison, field in (
        ("with_jw_vs_size_sector", "with_jw_ap_lower_bound_above_size_sector_count"),
        ("with_jw_vs_without_jw", "with_jw_ap_lower_bound_above_without_jw_count"),
    ):
        counted = sum(
            1
            for row in deltas
            if row["comparison"] == comparison
            and row["metric"] == "average_precision_success"
            and float(row["lower_95"]) > 0.0
        )
        _check(
            int(report["signals"][field]) == counted,
            f"headline counter mismatch: {field} ({report['signals'][field]} != {counted})",
        )
        checks += 1
    eligible = sum(1 for row in eligibility if row["model_status"] == "eligible")
    _check(
        int(report["signals"]["eligible_variant_denominator"]) == eligible,
        "eligible denominator",
    )
    _check(
        report["stop_at_triggered"]
        is (int(report["signals"]["with_jw_ap_lower_bound_above_size_sector_count"]) > 0),
        "stop_at flag inconsistent with the counter",
    )
    _check(
        report["negative_verdict_survives_decontamination"]
        is (
            int(report["signals"]["with_jw_ap_lower_bound_above_size_sector_count"]) == 0
            and int(report["signals"]["with_jw_ap_lower_bound_above_without_jw_count"])
            == 0
        ),
        "survival boolean inconsistent with the counters",
    )
    checks += 3

    # 9. parent counters recomputed from the parent artifact itself
    parent_deltas = _rows(root / PARENT / "paired_deltas.csv")
    for comparison, field in (
        ("with_jw_vs_size_sector", "with_jw_ap_lower_bound_above_size_sector_count"),
        ("with_jw_vs_without_jw", "with_jw_ap_lower_bound_above_without_jw_count"),
    ):
        counted = sum(
            1
            for row in parent_deltas
            if row["comparison"] == comparison
            and row["metric"] == "average_precision_success"
            and float(row["lower_95"]) > 0.0
        )
        _check(
            int(report["parent_signals"][field]) == counted,
            f"parent counter mismatch: {field}",
        )
        checks += 1

    # 10. comparison table re-joined against both sides
    comparison_rows = _rows(artifact / "comparison_vs_final_v4.csv")
    parent_eligibility = {
        str(row["solver_uuid"]): row
        for row in _rows(root / PARENT / "variant_eligibility.csv")
    }
    masked_eligibility = {str(row["solver_uuid"]): row for row in eligibility}
    _check(
        len(comparison_rows) == len(parent_eligibility) == len(masked_eligibility),
        "comparison row census mismatch",
    )
    for row in comparison_rows:
        uuid = str(row["solver_uuid"])
        _check(
            int(row["n_labels_before"]) == int(parent_eligibility[uuid]["n_labels"]),
            f"comparison n_labels_before: {uuid}",
        )
        _check(
            int(row["n_labels_after"]) == int(masked_eligibility[uuid]["n_labels"]),
            f"comparison n_labels_after: {uuid}",
        )
        _check(
            int(row["n_success_before"]) == int(parent_eligibility[uuid]["n_success"]),
            f"comparison n_success_before: {uuid}",
        )
        _check(
            int(row["n_success_after"]) == int(masked_eligibility[uuid]["n_success"]),
            f"comparison n_success_after: {uuid}",
        )
        _check(
            row["model_status_before"] == parent_eligibility[uuid]["model_status"],
            f"comparison status_before: {uuid}",
        )
        _check(
            row["model_status_after"] == masked_eligibility[uuid]["model_status"],
            f"comparison status_after: {uuid}",
        )
        checks += 6
    reported_changes = {
        str(change["solver_uuid"]) for change in report["eligibility_changes"]
    }
    actual_changes = {
        str(row["solver_uuid"])
        for row in comparison_rows
        if row["model_status_before"] != row["model_status_after"]
    }
    _check(reported_changes == actual_changes, "eligibility-change list mismatch")
    checks += 1

    # 11. prediction census and probability sanity
    predictions = _rows(artifact / "predictions.csv")
    _check(
        len(predictions) == eligible * 718 * 2,
        f"prediction row count: {len(predictions)}",
    )
    _check(
        len({(row["solver_uuid"], row["task_uuid"], row["feature_arm"]) for row in predictions})
        == len(predictions),
        "duplicate prediction keys",
    )
    for row in predictions:
        probability = float(row["probability_success"])
        _check(0.0 <= probability <= 1.0, "probability out of range")
        _check(
            row["predicted_outcome"] == ("success" if probability > 0.5 else "fail"),
            "predicted outcome is not argmax-consistent",
        )
        _check(
            row["family_used_as_model_input"].lower() == "false",
            "prediction row claims a family input",
        )
    checks += 3

    # 12. manifest hashes and byte counts
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
        "masked_tasks": len(expected_masked),
        "retained_tasks": len(expected_retained),
        "removed_success_cells": int(removed_counts.get("success", 0)),
        "eligible_variants": eligible,
        "parent_signals": report["parent_signals"],
        "signals": report["signals"],
        "negative_verdict_survives_decontamination": report[
            "negative_verdict_survives_decontamination"
        ],
        "stop_at_triggered": report["stop_at_triggered"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("analysis/ml_g50_solver_families/sensitivity_gradeable_mask_v1"),
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
