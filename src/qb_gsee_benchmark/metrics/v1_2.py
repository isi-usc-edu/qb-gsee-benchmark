"""Pure metric functions implementing ``METRICS_SPEC_v1`` version 1.2.

The functions in this module accept ordinary mappings/sequences and perform no
I/O.  Names are versioned deliberately: a future definition change must create
a new implementation rather than silently changing a derived bundle.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any, Iterable, Mapping, Sequence

METRICS_SPEC_VERSION = "1.2"
VALID_REFERENCE_GRADES = frozenset(
    {"exact", "multiple_nearly_exact", "one_nearly_exact", "analytical"}
)
OUTCOMES = ("success", "miss", "indeterminate")
SIMILARITY_DISPLAY_FLOOR = 10

DEFINITIONS: dict[str, dict[str, str]] = {
    "outcome": {
        "definition": (
            "success iff a usable returned energy satisfies |E-E_ref| <= "
            "tau_task; miss iff it exceeds tau_task; indeterminate iff no "
            "usable energy was returned. Scored only on reference-valid tasks."
        ),
        "spec_section": "METRICS_SPEC_v1.md sections 2, 3, 4, and 6",
    },
    "graded_residual": {
        "definition": "r(solver, task) = |E-E_ref| / tau_task for completed runs.",
        "spec_section": "METRICS_SPEC_v1.md section 6",
    },
    "panel_success_rate": {
        "definition": (
            "successes divided by attempts, including indeterminate attempts, "
            "across the observed solver panel for a reference-valid task."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 6",
    },
    "task_class": {
        "definition": (
            "solved_by_all when every attempt succeeds, solved_by_none when no "
            "attempt succeeds, and contested otherwise; panel-composition-dependent."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 6",
    },
    "stratified_outcome_rate": {
        "definition": (
            "Per-solver success, miss, and indeterminate counts and rates within "
            "family/tier/size strata, with instance and family bootstrap intervals."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 5",
    },
    "agreement": {
        "definition": (
            "agreement(i,j;task)=1 iff both energies exist and |E_i-E_j| <= "
            "tau_task; aggregate is the fraction over jointly completed tasks. "
            "Agreement is evidence of consistency, not correctness."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 7",
    },
    "solver_spread": {
        "definition": (
            "Maximum minus minimum energy over completed panel results for a task."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 7",
    },
    "failure_set_jaccard": {
        "definition": (
            "Jaccard similarity of solver failure sets (miss union indeterminate) "
            "over jointly attempted reference-valid tasks."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 8",
    },
    "absolute_error_spearman": {
        "definition": (
            "Spearman rank correlation of |E-E_ref| over jointly completed, "
            "reference-valid tasks."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 8",
    },
}


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _requirements(task: Mapping[str, Any]) -> Mapping[str, Any]:
    value = task.get("requirements", {})
    return value if isinstance(value, Mapping) else {}


def _features(task: Mapping[str, Any]) -> Mapping[str, Any]:
    value = task.get("features", {})
    return value if isinstance(value, Mapping) else {}


def _reference_grade(task: Mapping[str, Any]) -> str:
    req = _requirements(task)
    return str(
        task.get("reference_provenance_grade")
        or req.get("reference_energy_provenance")
        or "no_reference"
    )


def _threshold(task: Mapping[str, Any]) -> float | None:
    return _finite_number(_requirements(task).get("absolute_accuracy_threshold"))


def _reference_energy(task: Mapping[str, Any]) -> float | None:
    return _finite_number(_requirements(task).get("reference_energy"))


def _reference_uncertainty(task: Mapping[str, Any]) -> float | None:
    req = _requirements(task)
    for key in ("reference_energy_uncertainty", "reference_energy_standard_error"):
        value = _finite_number(req.get(key))
        if value is not None:
            units = str(req.get(f"{key}_units") or req.get("reference_energy_uncertainty_units") or "Hartree").lower()
            if units in {"millihartree", "mhartree", "mha"}:
                value /= 1000.0
            return value
    return None


def _public_task(task: Mapping[str, Any]) -> bool:
    return str(task.get("curation_tier", "unspecified")) != "test"


def _reference_valid(task: Mapping[str, Any]) -> bool:
    return (
        _public_task(task)
        and _reference_grade(task) in VALID_REFERENCE_GRADES
        and _reference_energy(task) is not None
        and (_threshold(task) or 0.0) > 0.0
    )


def _labels(task: Mapping[str, Any]) -> dict[str, str]:
    features = _features(task)
    uncertainty = _reference_uncertainty(task)
    threshold = _threshold(task)
    dominated = (
        uncertainty is not None and threshold is not None and uncertainty > threshold / 2.0
    )
    return {
        "family": str(task.get("family") or features.get("family") or "unspecified"),
        "tier": str(task.get("curation_tier") or "unspecified"),
        "size_band": str(task.get("size_band") or features.get("size_band") or "unspecified"),
        "reference_threshold_stratum": (
            "threshold_dominated_by_reference" if dominated else "reference_supported_threshold"
        ),
    }


def classify_outcome_v1_2(
    energy: Any, task: Mapping[str, Any]
) -> dict[str, Any]:
    """Classify one attempted result, including explicit reference gating."""

    usable_energy = _finite_number(energy)
    threshold = _threshold(task)
    reference = _reference_energy(task)
    uncertainty = _reference_uncertainty(task)
    result: dict[str, Any] = {
        "outcome": None,
        "metric_status": "ok",
        "energy": usable_energy,
        "absolute_error": None,
        "graded_residual": None,
        "reference_grade": _reference_grade(task),
        "reference_energy": reference,
        "threshold": threshold,
        "reference_uncertainty": uncertainty,
        "threshold_dominated_by_reference": bool(
            uncertainty is not None
            and threshold is not None
            and uncertainty > threshold / 2.0
        ),
    }
    if not _public_task(task):
        result["metric_status"] = "excluded_test_tier"
        return result
    if not _reference_valid(task):
        result["metric_status"] = "excluded_invalid_reference"
        if usable_energy is None:
            result["outcome"] = "indeterminate"
        return result
    if usable_energy is None:
        result["outcome"] = "indeterminate"
        return result
    error = abs(usable_energy - float(reference))
    result["absolute_error"] = error
    result["graded_residual"] = error / float(threshold)
    result["outcome"] = "success" if error <= float(threshold) else "miss"
    return result


def per_solver_task_primitives_v1_2(
    tasks: Mapping[str, Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return one scored primitive for each reference-valid attempted pair."""

    rows: list[dict[str, Any]] = []
    for attempt in attempts:
        task_id = str(attempt.get("task_uuid", ""))
        task = tasks.get(task_id)
        if task is None:
            continue
        classified = classify_outcome_v1_2(attempt.get("energy"), task)
        if classified["metric_status"] != "ok":
            continue
        rows.append(
            {
                "solver": str(attempt.get("solver", "unknown")),
                "task_uuid": task_id,
                **_labels(task),
                **classified,
            }
        )
    return sorted(rows, key=lambda row: (row["solver"], row["task_uuid"]))


def panel_descriptive_stats_v1_2(
    primitives: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in primitives:
        grouped[str(row["task_uuid"])].append(row)
    output = []
    for task_id, rows in grouped.items():
        counts = Counter(str(row["outcome"]) for row in rows)
        attempts = len(rows)
        successes = counts["success"]
        task_class = (
            "solved_by_all"
            if successes == attempts
            else "solved_by_none"
            if successes == 0
            else "contested"
        )
        output.append(
            {
                "task_uuid": task_id,
                **{key: rows[0][key] for key in _labels({}).keys()},
                "n_attempts": attempts,
                "outcome_counts": {name: counts[name] for name in OUTCOMES},
                "panel_success_rate": successes / attempts,
                "task_class": task_class,
                "panel_composition_dependent": True,
            }
        )
    return sorted(output, key=lambda row: row["task_uuid"])


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * probability
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _bootstrap_interval(
    rows: Sequence[Mapping[str, Any]], cluster_key: str | None, seed: int, iterations: int
) -> list[float] | None:
    if not rows:
        return None
    rng = random.Random(seed)
    if cluster_key is None:
        units = [[row] for row in rows]
    else:
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row[cluster_key])].append(row)
        units = list(grouped.values())
    estimates = []
    for _ in range(iterations):
        sampled = [rng.choice(units) for _ in units]
        flat = [row for unit in sampled for row in unit]
        estimates.append(sum(row["outcome"] == "success" for row in flat) / len(flat))
    return [_percentile(estimates, 0.025), _percentile(estimates, 0.975)]


def stratified_aggregation_v1_2(
    primitives: Sequence[Mapping[str, Any]], *, bootstrap_iterations: int = 1000
) -> list[dict[str, Any]]:
    """Aggregate outcome splits across the joint family/tier/size strata."""

    grouped: dict[tuple[str, str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in primitives:
        key = (
            str(row["solver"]),
            str(row["family"]),
            str(row["tier"]),
            str(row["size_band"]),
            str(row["reference_threshold_stratum"]),
        )
        grouped[key].append(row)
    output = []
    for key, rows in sorted(grouped.items()):
        counts = Counter(str(row["outcome"]) for row in rows)
        attempts = len(rows)
        seed_material = "|".join(key).encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
        output.append(
            {
                "solver": key[0],
                "stratum": {
                    "family": key[1],
                    "tier": key[2],
                    "size_band": key[3],
                    "reference_threshold_stratum": key[4],
                },
                "n_attempts": attempts,
                "n_families": len({str(row["family"]) for row in rows}),
                "outcome_counts": {name: counts[name] for name in OUTCOMES},
                "outcome_rates": {name: counts[name] / attempts for name in OUTCOMES},
                "success_rate_bootstrap_95": {
                    "instance_level": _bootstrap_interval(
                        rows, None, seed, bootstrap_iterations
                    ),
                    "family_level_governing": _bootstrap_interval(
                        rows, "family", seed + 1, bootstrap_iterations
                    ),
                    "iterations": bootstrap_iterations,
                },
                "absolute_errors": sorted(
                    float(row["absolute_error"])
                    for row in rows
                    if row.get("absolute_error") is not None
                ),
                "graded_residuals": sorted(
                    float(row["graded_residual"])
                    for row in rows
                    if row.get("graded_residual") is not None
                ),
            }
        )
    return output


def agreement_v1_2(
    tasks: Mapping[str, Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compute per-task spreads and pairwise cross-solver agreement."""

    by_task: dict[str, dict[str, float]] = defaultdict(dict)
    for attempt in attempts:
        task_id = str(attempt.get("task_uuid", ""))
        task = tasks.get(task_id)
        energy = _finite_number(attempt.get("energy"))
        if task is not None and _public_task(task) and energy is not None:
            by_task[task_id][str(attempt.get("solver", "unknown"))] = energy
    per_task = []
    pair_values: dict[tuple[str, str, str, str, str, str], list[int]] = defaultdict(list)
    for task_id, energies in sorted(by_task.items()):
        task = tasks[task_id]
        threshold = _threshold(task)
        spread = max(energies.values()) - min(energies.values()) if energies else None
        per_task.append(
            {
                "task_uuid": task_id,
                **_labels(task),
                "reference_grade": _reference_grade(task),
                "reference_uncertainty": _reference_uncertainty(task),
                "n_completed": len(energies),
                "solver_spread": spread,
                "threshold": threshold,
            }
        )
        if threshold is None or threshold <= 0:
            continue
        labels = _labels(task)
        for left, right in combinations(sorted(energies), 2):
            key = (
                left,
                right,
                labels["family"],
                labels["tier"],
                labels["size_band"],
                labels["reference_threshold_stratum"],
            )
            pair_values[key].append(int(abs(energies[left] - energies[right]) <= threshold))
    aggregate = []
    for key, values in sorted(pair_values.items()):
        aggregate.append(
            {
                "solver_i": key[0],
                "solver_j": key[1],
                "stratum": {
                    "family": key[2],
                    "tier": key[3],
                    "size_band": key[4],
                    "reference_threshold_stratum": key[5],
                },
                "n_jointly_completed": len(values),
                "n_agree": sum(values),
                "agreement_fraction": sum(values) / len(values),
                "interpretation": "consistency_not_correctness",
            }
        )
    return {"per_task_spread": per_task, "aggregate": aggregate}


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(indexed):
        stop = start + 1
        while stop < len(indexed) and indexed[stop][1] == indexed[start][1]:
            stop += 1
        rank = (start + 1 + stop) / 2.0
        for position in range(start, stop):
            ranks[indexed[position][0]] = rank
        start = stop
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) < 2:
        return None
    lmean = sum(left) / len(left)
    rmean = sum(right) / len(right)
    numerator = sum((x - lmean) * (y - rmean) for x, y in zip(left, right))
    lnorm = sum((x - lmean) ** 2 for x in left)
    rnorm = sum((y - rmean) ** 2 for y in right)
    if lnorm == 0 or rnorm == 0:
        return None
    return numerator / math.sqrt(lnorm * rnorm)


def solver_similarity_v1_2(
    primitives: Sequence[Mapping[str, Any]], *, display_floor: int = SIMILARITY_DISPLAY_FLOOR
) -> list[dict[str, Any]]:
    by_solver: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in primitives:
        by_solver[str(row["solver"])][str(row["task_uuid"])] = row
    output = []
    for left, right in combinations(sorted(by_solver), 2):
        common = sorted(set(by_solver[left]) & set(by_solver[right]))
        left_fail = {task for task in common if by_solver[left][task]["outcome"] != "success"}
        right_fail = {task for task in common if by_solver[right][task]["outcome"] != "success"}
        union = left_fail | right_fail
        completed = [
            task
            for task in common
            if by_solver[left][task]["outcome"] != "indeterminate"
            and by_solver[right][task]["outcome"] != "indeterminate"
        ]
        spearman = _pearson(
            _average_ranks([float(by_solver[left][task]["absolute_error"]) for task in completed]),
            _average_ranks([float(by_solver[right][task]["absolute_error"]) for task in completed]),
        )
        sufficient = len(common) >= display_floor
        output.append(
            {
                "solver_i": left,
                "solver_j": right,
                "n_jointly_attempted": len(common),
                "n_jointly_completed": len(completed),
                "display_floor": display_floor,
                "status": "ok" if sufficient else "insufficient_data",
                "failure_set_jaccard": (
                    (len(left_fail & right_fail) / len(union) if union else 1.0)
                    if sufficient
                    else None
                ),
                "absolute_error_spearman": spearman if sufficient else None,
            }
        )
    return output


def build_bundle_v1_2(
    tasks: Mapping[str, Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    *,
    bootstrap_iterations: int = 1000,
) -> dict[str, Any]:
    """Build the complete serializable v1.2 bundle from normalized records."""

    public_attempts = [
        attempt
        for attempt in attempts
        if str(attempt.get("task_uuid", "")) in tasks
        and _public_task(tasks[str(attempt.get("task_uuid", ""))])
    ]
    primitives = per_solver_task_primitives_v1_2(tasks, attempts)
    agreement = agreement_v1_2(tasks, attempts)
    task_classes = panel_descriptive_stats_v1_2(primitives)
    return {
        "metrics_spec_version": METRICS_SPEC_VERSION,
        "definitions": DEFINITIONS,
        "headline_counts": {
            "solvers_found": sorted({str(row.get("solver", "unknown")) for row in attempts}),
            "n_solvers_found": len({str(row.get("solver", "unknown")) for row in attempts}),
            "n_attempts_all_committed": len(attempts),
            "n_public_attempts": len(public_attempts),
            "n_scored_attempts": len(primitives),
            "n_tasks_covered_all_committed": len({str(row.get("task_uuid")) for row in attempts}),
            "n_public_tasks_covered": len({str(row.get("task_uuid")) for row in public_attempts}),
            "n_scored_tasks": len({str(row["task_uuid"]) for row in primitives}),
            "task_class_counts": dict(sorted(Counter(row["task_class"] for row in task_classes).items())),
            "strata_populated": {
                key: sorted({str(row[key]) for row in primitives})
                for key in ("family", "tier", "size_band", "reference_threshold_stratum")
            },
        },
        "primitives": primitives,
        "panel_descriptive_stats": task_classes,
        "stratified_aggregation": stratified_aggregation_v1_2(
            primitives, bootstrap_iterations=bootstrap_iterations
        ),
        "agreement": agreement,
        "similarity": solver_similarity_v1_2(primitives),
        "attributions": {},
    }
