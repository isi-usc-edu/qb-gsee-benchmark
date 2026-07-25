#!/usr/bin/env python
"""Independent verifier for the ML-8D UQ solvability artifact.

Re-derives the design-based ratios from the pinned weights and labels, recounts
the gradeable population, recomputes the calibration instruments and the frozen
gate arithmetic from the emitted per-task posteriors, re-checks every
probability/interval invariant, recomputes the kNN comparison columns from the
pinned predictions, and re-verifies every manifest hash and byte count. Does not
import the run module's estimator code. Fails closed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

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


def _close(left: float, right: float, tolerance: float = 1.0e-9) -> bool:
    return abs(left - right) <= tolerance


def _ece(pairs: list[tuple[float, float]], bins: int) -> float:
    """Equal-count binning matching the frozen rule (stable order, np.array_split)."""
    ordered = sorted(range(len(pairs)), key=lambda i: (pairs[i][0], i))
    total = len(ordered)
    base, extra = divmod(total, bins)
    groups: list[list[int]] = []
    start = 0
    for index in range(bins):
        size = base + (1 if index < extra else 0)
        groups.append(ordered[start : start + size])
        start += size
    error = 0.0
    for group in groups:
        if not group:
            continue
        mean_predicted = sum(pairs[i][0] for i in group) / len(group)
        observed = sum(pairs[i][1] for i in group) / len(group)
        error += len(group) / total * abs(mean_predicted - observed)
    return error


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

    # 1. held state and standing rules
    _check(report["status"] == "held_pending_pi_review", "not held")
    _check(report["effective"] is False, "effective must be false")
    _check(report["supersedes"] is None, "claims to supersede something")
    _check(report["ratio_of_record"] == "design_based", "wrong ratio of record")
    _check(report["validated_predictor_claim"] is False, "predictor claim present")
    _check(report["family_used_as_model_input"] is False, "family used as input")
    _check(report["every_model_output_labelled_estimate"] is True, "outputs unlabelled")
    _check(report["scope"] == "gradeable_tasks_only", "wrong scope")
    _check(report["stop_at"]["interpretation_offered"] is False, "interpretation offered")
    _check(
        report["stop_at"]["no_validated_predictor_rule_stands"] is True,
        "no-validated-predictor rule not asserted",
    )
    _check(report["kernel_psd_summary"]["silent_correction"] is False, "silent PSD fix")
    checks += 11

    # 2. pinned inputs still hash as recorded
    for name, specification in sorted(report["inputs"].items()):
        path = root / str(specification["path"])
        _check(path.is_file(), f"missing input: {name}")
        _check(_sha256(path) == str(specification["sha256"]), f"input drift: {name}")
        checks += 1

    census = {
        str(row["task_uuid"]): row["gradeable_for_campaign_scoring"].lower() == "true"
        for row in _rows(root / str(report["inputs"]["gradeability_census"]["path"]))
    }
    gradeable_total = sum(1 for value in census.values() if value)
    _check(
        int(report["panel"]["gradeable_corpus_tasks"]) == gradeable_total,
        "gradeable corpus count",
    )
    checks += 1

    observations = _rows(root / str(report["inputs"]["masked_observations"]["path"]))
    weights = {
        str(row["task_uuid"]): int(row["gradeable_selection_weight"])
        for row in _rows(
            root / str(report["inputs"]["gradeable_selection_weights"]["path"])
        )
    }
    panel = sorted(weights)
    _check(
        int(report["panel"]["training_panel_tasks"]) == len(panel), "training panel size"
    )
    _check(all(census[task] for task in panel), "non-gradeable task in the panel")
    checks += 2

    labels_by_variant: dict[str, dict[str, int]] = defaultdict(dict)
    for row in observations:
        labels_by_variant[str(row["solver_uuid"])][str(row["task_uuid"])] = int(
            str(row["observed_outcome"]) == "success"
        )

    # 3. design-based ratios re-derived from weights and labels
    design = _rows(artifact / "design_based_ratios.csv")
    _check(len(design) == len(labels_by_variant), "design row census")
    for row in design:
        uuid = str(row["solver_uuid"])
        labels = labels_by_variant[uuid]
        _check(set(labels) == set(panel), f"label/panel mismatch: {uuid}")
        numerator = sum(weights[task] for task in panel if labels[task] == 1)
        denominator = sum(weights[task] for task in panel)
        _check(
            _close(float(row["design_based_ratio"]), numerator / denominator),
            f"design ratio mismatch: {uuid}",
        )
        _check(int(row["weight_sum"]) == denominator, f"weight sum: {uuid}")
        _check(
            int(row["n_success_centers"]) == sum(labels.values()),
            f"success centers: {uuid}",
        )
        _check(int(row["n_centers"]) == len(panel), f"center count: {uuid}")
        _check(row["role"] == "ratio_of_record", f"design role: {uuid}")
        _check(row["primary_interval"] == "family_grouped", f"primary interval: {uuid}")
        lower = float(row["family_grouped_lower_95"])
        upper = float(row["family_grouped_upper_95"])
        _check(lower <= float(row["design_based_ratio"]) <= upper, f"interval: {uuid}")
        _check(
            float(row["center_level_lower_95"]) <= float(row["center_level_upper_95"]),
            f"sensitivity interval order: {uuid}",
        )
        _check(
            int(row["family_grouped_accepted_draws"])
            <= int(row["family_grouped_attempted_draws"]),
            f"draw accounting: {uuid}",
        )
        checks += 9

    # 4. per-task posteriors: census, ranges, argmax-free invariants
    posterior = _rows(artifact / "per_task_posterior.csv")
    variants = sorted({str(row["solver_uuid"]) for row in posterior})
    _check(
        len(posterior) == len(variants) * 718,
        f"posterior row census: {len(posterior)}",
    )
    _check(
        int(report["panel"]["posterior_rows"]) == len(posterior), "posterior row count"
    )
    by_variant: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in posterior:
        probability = float(row["probability_success"])
        _check(0.0 <= probability <= 1.0, "probability out of range")
        _check(
            float(row["credible_lower_95"]) <= probability + 1.0e-9
            and probability <= float(row["credible_upper_95"]) + 1.0e-9,
            f"credible interval does not bracket the mean: {row['task_uuid']}",
        )
        _check(float(row["latent_sd"]) >= 0.0, "negative latent sd")
        _check(row["output_kind"] == "estimate", "posterior row not labelled estimate")
        _check(
            row["family_used_as_model_input"].lower() == "false",
            "posterior row claims a family input",
        )
        _check(
            (row["gradeable_for_campaign_scoring"].lower() == "true")
            == census[str(row["task_uuid"])],
            f"gradeable flag mismatch: {row['task_uuid']}",
        )
        by_variant[str(row["solver_uuid"])].append(row)
    checks += 3

    # 5. model-based ratio = unweighted mean over gradeable corpus tasks
    ratios = {
        (str(row["solver_uuid"]), str(row["lengthscale_variant"])): row
        for row in _rows(artifact / "model_based_ratios.csv")
    }
    for uuid, rows in sorted(by_variant.items()):
        selected = [
            float(row["probability_success"])
            for row in rows
            if census[str(row["task_uuid"])]
        ]
        _check(len(selected) == gradeable_total, f"gradeable prediction count: {uuid}")
        published = ratios[(uuid, "median")]
        _check(
            _close(float(published["model_based_ratio"]), sum(selected) / len(selected), 1.0e-9),
            f"model ratio mismatch: {uuid}",
        )
        _check(
            int(published["n_gradeable_corpus_tasks"]) == gradeable_total,
            f"model ratio denominator: {uuid}",
        )
        _check(
            float(published["credible_lower_95"])
            <= float(published["credible_upper_95"]),
            f"credible interval order: {uuid}",
        )
        _check(published["output_kind"] == "estimate", f"ratio not an estimate: {uuid}")
        checks += 4

    # 6. calibration instruments and the frozen gate, recomputed
    gate_settings = report["calibration_gate"]
    bins = int(gate_settings["reliability_bins"])
    threshold = float(gate_settings["ece_threshold"])
    calibration = {str(row["solver_uuid"]): row for row in _rows(artifact / "calibration.csv")}
    gate = _rows(artifact / "calibration_gate.csv")
    _check(len(gate) == len(variants) == int(gate_settings["assessed_count"]), "gate census")
    reliability: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _rows(artifact / "reliability_bins.csv"):
        reliability[str(row["solver_uuid"])].append(row)

    passed = 0
    for row in gate:
        uuid = str(row["solver_uuid"])
        labels = labels_by_variant[uuid]
        predicted = {
            str(item["task_uuid"]): float(item["probability_success"])
            for item in by_variant[uuid]
        }
        pairs = [(predicted[task], float(labels[task])) for task in panel]
        recomputed = _ece(pairs, bins)
        _check(
            _close(float(row["expected_calibration_error"]), recomputed, 1.0e-9),
            f"ECE mismatch: {uuid} ({row['expected_calibration_error']} vs {recomputed})",
        )
        ece_met = recomputed <= threshold
        _check(
            (row["ece_condition_met"].lower() == "true") == ece_met,
            f"ECE condition: {uuid}",
        )
        lower = row["slope_lower_95"]
        upper = row["slope_upper_95"]
        contains = bool(
            lower not in ("", "None")
            and upper not in ("", "None")
            and float(lower) <= 1.0 <= float(upper)
        )
        _check(
            (row["slope_interval_contains_one"].lower() == "true") == contains,
            f"slope condition: {uuid}",
        )
        verdict = ece_met and contains
        _check(
            (row["calibration_gate_passed"].lower() == "true") == verdict,
            f"gate verdict: {uuid}",
        )
        _check(_close(float(row["ece_threshold"]), threshold), f"threshold: {uuid}")
        passed += int(verdict)
        # reliability bins must partition the labelled panel
        bin_rows = reliability[uuid]
        _check(
            sum(int(item["n_tasks"]) for item in bin_rows) == len(panel),
            f"reliability bins do not partition the panel: {uuid}",
        )
        _check(len(bin_rows) <= bins, f"too many reliability bins: {uuid}")
        for item in bin_rows:
            _check(
                _close(
                    float(item["absolute_gap"]),
                    abs(
                        float(item["mean_predicted"]) - float(item["observed_frequency"])
                    ),
                ),
                f"reliability gap arithmetic: {uuid}/{item['bin_index']}",
            )
        record = calibration[uuid]
        _check(
            _close(
                float(record["observed_frequency"]),
                sum(labels[task] for task in panel) / len(panel),
            ),
            f"observed frequency: {uuid}",
        )
        _check(
            _close(
                float(record["mean_predicted"]),
                sum(predicted[task] for task in panel) / len(panel),
            ),
            f"mean predicted: {uuid}",
        )
        _check(
            _close(
                float(record["brier"]),
                sum((predicted[task] - labels[task]) ** 2 for task in panel) / len(panel),
            ),
            f"brier: {uuid}",
        )
        checks += 10

    _check(int(gate_settings["passed_count"]) == passed, "gate passed count")
    _check(
        report["stop_at"]["triggered"] is bool(passed > 0),
        "stop_at flag inconsistent with the gate count",
    )
    _check(
        sorted(map(str, gate_settings["passed_variants"]))
        == sorted(
            str(row["solver_short_name"])
            for row in gate
            if row["calibration_gate_passed"].lower() == "true"
        ),
        "passed-variant list mismatch",
    )
    checks += 3

    # 7. kNN comparison columns recomputed from the pinned predictions
    knn_rows = [
        row
        for row in _rows(root / str(report["inputs"]["knn_predictions"]["path"]))
        if row["feature_arm"] == "with_jw"
    ]
    knn_by_variant: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in knn_rows:
        knn_by_variant[str(row["solver_uuid"])].append(row)
    comparison = _rows(artifact / "ratio_comparison.csv")
    _check(len(comparison) == len(variants), "comparison row census")
    design_by_uuid = {str(row["solver_uuid"]): row for row in design}
    for row in comparison:
        uuid = str(row["solver_uuid"])
        subset = [
            item for item in knn_by_variant[uuid] if census[str(item["task_uuid"])]
        ]
        _check(len(subset) == gradeable_total, f"kNN gradeable census: {uuid}")
        hard = sum(1 for item in subset if item["predicted_outcome"] == "success") / len(
            subset
        )
        mean_probability = sum(
            float(item["probability_success"]) for item in subset
        ) / len(subset)
        _check(
            _close(float(row["knn_corpus_hard_label_rate"]), hard),
            f"kNN hard-label rate: {uuid}",
        )
        _check(
            _close(float(row["knn_corpus_mean_probability"]), mean_probability),
            f"kNN mean probability: {uuid}",
        )
        ratio = float(design_by_uuid[uuid]["design_based_ratio"])
        _check(
            _close(float(row["design_based_ratio"]), ratio),
            f"comparison design ratio: {uuid}",
        )
        _check(
            _close(float(row["knn_hard_label_gap_to_design"]), abs(hard - ratio)),
            f"kNN hard gap: {uuid}",
        )
        _check(
            _close(
                float(row["knn_mean_probability_gap_to_design"]),
                abs(mean_probability - ratio),
            ),
            f"kNN mean gap: {uuid}",
        )
        gp_gap = abs(float(row["gp_model_based_ratio"]) - ratio)
        _check(_close(float(row["gp_gap_to_design"]), gp_gap), f"GP gap: {uuid}")
        _check(
            (row["gp_narrows_hard_label_gap"].lower() == "true")
            == bool(gp_gap < abs(hard - ratio)),
            f"GP narrows hard gap flag: {uuid}",
        )
        _check(
            (row["gp_narrows_mean_probability_gap"].lower() == "true")
            == bool(gp_gap < abs(mean_probability - ratio)),
            f"GP narrows mean gap flag: {uuid}",
        )
        checks += 8

    # 8. PSD diagnostics and lengthscale sensitivity coverage
    psd = _rows(artifact / "kernel_psd_diagnostics.csv")
    summary = report["kernel_psd_summary"]
    _check(int(summary["kernels"]) == len(psd), "psd row census")
    _check(
        int(summary["projections_applied"])
        == sum(1 for row in psd if row["projection_applied"].lower() == "true"),
        "psd projection count",
    )
    _check(
        _close(
            float(summary["min_eigenvalue_overall"]),
            min(float(row["min_eigenvalue_before_projection"]) for row in psd),
            1.0e-12,
        ),
        "psd minimum eigenvalue",
    )
    for row in psd:
        _check(float(row["lengthscale"]) > 0.0, "nonpositive lengthscale")
        _check(int(row["n_training"]) > 0, "empty training fold")
    sensitivity = _rows(artifact / "lengthscale_sensitivity.csv")
    expected_variants = set(map(str, report["panel"]["lengthscale_variants"]))
    _check(
        len(sensitivity) == len(variants) * len(expected_variants),
        "sensitivity row census",
    )
    _check(
        {str(row["lengthscale_variant"]) for row in sensitivity} == expected_variants,
        "sensitivity variant coverage",
    )
    checks += 6

    # 9. manifest hashes and byte counts
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
        "variants": len(variants),
        "gradeable_corpus_tasks": gradeable_total,
        "training_panel_tasks": len(panel),
        "calibration_gate_passed_count": passed,
        "stop_at_triggered": report["stop_at"]["triggered"],
        "ratio_of_record": report["ratio_of_record"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--artifact", type=Path, default=Path("analysis/ml_solvability_uq/held_v1")
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
