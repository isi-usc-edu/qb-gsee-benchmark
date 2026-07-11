"""Pure metric functions implementing ``METRICS_SPEC_v1`` version 1.8.

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

METRICS_SPEC_VERSION = "1.8"
VALID_REFERENCE_GRADES = frozenset(
    {"exact", "multiple_nearly_exact", "one_nearly_exact", "analytical"}
)
OUTCOMES = ("success", "miss", "indeterminate")
SIMILARITY_DISPLAY_FLOOR = 10
REFERENCE_UNCERTAINTY_EXCLUDED_FIELDS = (
    "features.qsz_afqmc_standard_error_hartree",
)
NORB_METADATA_FIELDS = (
    "features.num_orbitals",
    "features.hubbard_num_sites",
    "independent_parameters.num_sites",
    "independent_parameters.num_spatial_orbitals",
)

REFERENCE_UNCERTAINTY_FIELDS = (
    "reference_energy_uncertainty",
    "reference_energy_standard_error",
    "reference_energy_standard_error_hartree",
)
SIZE_BAND_LABELS = (
    "norb_le8",
    "norb_9_16",
    "norb_17_32",
    "norb_33_64",
    "norb_65_128",
    "norb_ge129",
)

DEFINITIONS: dict[str, dict[str, str]] = {
    "public_task": {
        "definition": (
            "A public task has curation_tier != test and joins to a committed "
            "problem-instance task_uuid; unjoinable attempts are never public."
        ),
        "spec_section": "METRICS_SPEC_v1.md sections 1 and 3; ME-2 audit D1/D3",
    },
    "size_band": {
        "definition": (
            "Size is stored NORB with no spin doubling, read consistently from "
            "features.num_orbitals, features.hubbard_num_sites, "
            "independent_parameters.num_sites, or "
            "independent_parameters.num_spatial_orbitals; bands are norb_le8, "
            "norb_9_16, norb_17_32, norb_33_64, norb_65_128, or norb_ge129."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 5 (v1.3)",
    },
    "reference_uncertainty": {
        "definition": (
            "Maximum Hartree value over all occurrences in task, requirements, "
            "and features of reference_energy_uncertainty (using its stored "
            "units), reference_energy_standard_error (Hartree), and "
            "reference_energy_standard_error_hartree (Hartree). The cross-check "
            "field features.qsz_afqmc_standard_error_hartree is deliberately "
            "excluded because it describes AFQMC cross-check uncertainty, not "
            "the local FCI reference anchor."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 3 (v1.4 rule 3)",
    },
    "not_attempted": {
        "definition": (
            "A record is coverage-only only when harness_status=not_attempted, "
            "attempted=false, and no runtime, exit, launch, traceback, or "
            "execution-bearing reason is present. Contradictory records are data "
            "errors and hard-fail ingest."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 4 (v1.8 rule 1)",
    },
    "governing_ci_annotation": {
        "definition": (
            "A zero-width multi-family governing success-rate interval whose "
            "success indicator is constant is annotated "
            "degenerate_constant_outcome."
        ),
        "spec_section": "METRICS_SPEC_v1.md section 5 (v1.6 rule 2)",
    },
    "solver_resource_ladders": {
        "definition": (
            "Declared solver members are ordered by a populated resource knob. "
            "For every earlier/later pair, nestedness violations count tasks where "
            "the earlier member succeeds and the later member does not over "
            "jointly-attempted reference-valid tasks."
        ),
        "spec_section": "METRICS_SPEC_v1.md v1.7 solver resource ladders",
    },
    "campaign_identity": {
        "definition": (
            "Every normalized solver record carries a campaign. Explicit G-39 "
            "campaign metadata is retained; pre-campaign records receive the "
            "deterministic label legacy:<solution-file-family>. Solver statistics, "
            "agreement, similarity, and ladders never pool across campaigns."
        ),
        "spec_section": "METRICS_SPEC_v1.md v1.8 rule 2",
    },
    "threshold_provenance": {
        "definition": (
            "All thresholds are read from committed task requirements after the "
            "G-38 O19 per-site regeneration (commit 6bbdb54); the metric layer "
            "does not derive or alter thresholds."
        ),
        "spec_section": "METRICS_SPEC_v1.md sections 2 and 11; ME-5(d)",
    },
    "g39_record_correction": {
        "definition": (
            "G-39 corrected 27 original ran-and-failed G-31 records, plus two "
            "diamond race records, from never-ran flags to attempted failed/timeout "
            "metadata without changing energies or reasons. Reconciliation is "
            "reported in diagnostics.record_correction."
        ),
        "spec_section": "METRICS_SPEC_v1.md v1.8 rule 1; ME-5(b,d)",
    },
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
            "full-cross family/tier/size/threshold strata plus across-family "
            "size-band, tier, and global marginal pools; each reports an "
            "instance interval and a governing family interval only when at "
            "least two families are present."
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
            "over jointly attempted reference-valid tasks; an empty joint failure "
            "union emits null with status no_joint_failures."
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
    value = task.get("reference_provenance_grade")
    return str(value) if value else "missing"


def _threshold(task: Mapping[str, Any]) -> float | None:
    return _finite_number(_requirements(task).get("absolute_accuracy_threshold"))


def _reference_energy(task: Mapping[str, Any]) -> float | None:
    return _finite_number(_requirements(task).get("reference_energy"))


def _reference_uncertainty(task: Mapping[str, Any]) -> float | None:
    values: list[float] = []
    containers = (task, _requirements(task), _features(task))
    for container in containers:
        for key in REFERENCE_UNCERTAINTY_FIELDS:
            value = _finite_number(container.get(key))
            if value is None:
                continue
            if key == "reference_energy_uncertainty":
                units = str(
                    container.get("reference_energy_uncertainty_units") or "Hartree"
                ).lower()
                if units in {"millihartree", "mhartree", "mha"}:
                    value /= 1000.0
                elif units not in {"hartree", "ha"}:
                    raise ValueError(f"unsupported reference uncertainty units: {units}")
            values.append(value)
    return max(values) if values else None


def _campaign(record: Mapping[str, Any]) -> str:
    campaign = str(record.get("campaign") or "")
    if not campaign:
        source = str(record.get("source") or "<unknown>")
        raise ValueError(f"record missing campaign identity: {source}")
    return campaign


def _record_is_not_attempted(record: Mapping[str, Any]) -> bool:
    attempted = record.get("attempted")
    status = record.get("harness_status")
    source = str(record.get("source") or "<unknown>")
    if status == "not_attempted":
        reason = str(record.get("not_attempted_reason") or "").lower()
        execution_reason = any(
            marker in reason
            for marker in (
                "exit code", "exited with code", "timeout", "timed out",
                "wall cap", "wall-cap",
            )
        )
        if attempted is not False or record.get("execution_evidence") or execution_reason:
            raise ValueError(f"contradictory not_attempted record: {source}")
        return True
    if attempted is False:
        raise ValueError(f"attempted=false without valid not_attempted status: {source}")
    if status is not None and attempted is not True:
        raise ValueError(f"harness status/attempted mismatch: {source}")
    if attempted is True and status is None:
        raise ValueError(f"attempted=true without harness status: {source}")
    return False


def _public_task(task: Mapping[str, Any]) -> bool:
    return str(task.get("curation_tier", "unspecified")) != "test"


def _reference_valid(task: Mapping[str, Any]) -> bool:
    return (
        _public_task(task)
        and _reference_grade(task) in VALID_REFERENCE_GRADES
        and _reference_energy(task) is not None
        and (_threshold(task) or 0.0) > 0.0
    )


def _norb(task: Mapping[str, Any]) -> int | None:
    value = _finite_number(task.get("metrics_norb"))
    if value is None:
        value = _finite_number(_features(task).get("num_orbitals"))
    if value is None or value < 0 or not float(value).is_integer():
        return None
    return int(value)


def _size_band(task: Mapping[str, Any]) -> str:
    norb = _norb(task)
    if norb is None:
        return "unspecified"
    if norb <= 8:
        return "norb_le8"
    if norb <= 16:
        return "norb_9_16"
    if norb <= 32:
        return "norb_17_32"
    if norb <= 64:
        return "norb_33_64"
    if norb <= 128:
        return "norb_65_128"
    return "norb_ge129"


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
        "size_band": _size_band(task),
        "reference_threshold_stratum": (
            "threshold_dominated_by_reference" if dominated else "reference_supported_threshold"
        ),
    }


def classify_outcome_v1_8(
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


def per_solver_task_primitives_v1_8(
    tasks: Mapping[str, Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return one scored primitive for each campaign-specific attempted pair."""

    rows: list[dict[str, Any]] = []
    for attempt in attempts:
        if _record_is_not_attempted(attempt):
            continue
        task_id = str(attempt.get("task_uuid", ""))
        task = tasks.get(task_id)
        if task is None:
            continue
        classified = classify_outcome_v1_8(attempt.get("energy"), task)
        if classified["metric_status"] != "ok":
            continue
        rows.append(
            {
                "solver": str(attempt.get("solver", "unknown")),
                "campaign": _campaign(attempt),
                "task_uuid": task_id,
                **_labels(task),
                **classified,
            }
        )
    return sorted(rows, key=lambda row: (row["solver"], row["campaign"], row["task_uuid"]))


def panel_descriptive_stats_v1_8(
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


def _family_governing_record(
    rows: Sequence[Mapping[str, Any]], seed: int, iterations: int
) -> dict[str, Any]:
    n_families = len({str(row["family"]) for row in rows})
    if n_families < 2:
        return {
            "status": "insufficient_data",
            "reason": "fewer_than_two_families",
            "annotation": None,
            "n_families": n_families,
            "interval": None,
        }
    interval = _bootstrap_interval(rows, "family", seed, iterations)
    success_indicators = {row["outcome"] == "success" for row in rows}
    annotation = (
        "degenerate_constant_outcome"
        if interval is not None
        and interval[0] == interval[1]
        and len(success_indicators) == 1
        else None
    )
    return {
        "status": "ok",
        "reason": None,
        "annotation": annotation,
        "n_families": n_families,
        "interval": interval,
    }


def stratified_aggregation_v1_8(
    primitives: Sequence[Mapping[str, Any]], *, bootstrap_iterations: int = 1000
) -> list[dict[str, Any]]:
    """Aggregate outcomes without pooling a solver across campaigns."""

    grouped: dict[
        tuple[str, str, str, str, str, str, str], list[Mapping[str, Any]]
    ] = defaultdict(list)
    for row in primitives:
        solver = str(row["solver"])
        campaign = str(row["campaign"])
        family = str(row["family"])
        tier = str(row["tier"])
        size_band = str(row["size_band"])
        threshold_stratum = str(row["reference_threshold_stratum"])
        keys = (
            (solver, campaign, "full_cross", family, tier, size_band, threshold_stratum),
            (solver, campaign, "size_band_marginal", "all", "all", size_band, "all"),
            (solver, campaign, "tier_marginal", "all", tier, "all", "all"),
            (solver, campaign, "global_marginal", "all", "all", "all", "all"),
        )
        for key in keys:
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
                "campaign": key[1],
                "stratum_scope": key[2],
                "stratum": {
                    "family": key[3],
                    "tier": key[4],
                    "size_band": key[5],
                    "reference_threshold_stratum": key[6],
                },
                "n_attempts": attempts,
                "n_families": len({str(row["family"]) for row in rows}),
                "outcome_counts": {name: counts[name] for name in OUTCOMES},
                "outcome_rates": {name: counts[name] / attempts for name in OUTCOMES},
                "success_rate_bootstrap_95": {
                    "instance_level": _bootstrap_interval(rows, None, seed, bootstrap_iterations),
                    "family_level_governing": _family_governing_record(
                        rows, seed + 1, bootstrap_iterations
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


def agreement_v1_8(
    tasks: Mapping[str, Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Compute agreement with campaign-specific solver identities."""

    by_task: dict[str, dict[tuple[str, str], float]] = defaultdict(dict)
    for attempt in attempts:
        if _record_is_not_attempted(attempt):
            continue
        task_id = str(attempt.get("task_uuid", ""))
        task = tasks.get(task_id)
        energy = _finite_number(attempt.get("energy"))
        if task is not None and _public_task(task) and energy is not None:
            identity = (str(attempt.get("solver", "unknown")), _campaign(attempt))
            by_task[task_id][identity] = energy
    per_task = []
    pair_values: dict[tuple[str, str, str, str, str, str, str, str], list[int]] = defaultdict(list)
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
                left[0], left[1], right[0], right[1], labels["family"],
                labels["tier"], labels["size_band"], labels["reference_threshold_stratum"],
            )
            pair_values[key].append(int(abs(energies[left] - energies[right]) <= threshold))
    aggregate = []
    for key, values in sorted(pair_values.items()):
        aggregate.append(
            {
                "solver_i": key[0], "campaign_i": key[1],
                "solver_j": key[2], "campaign_j": key[3],
                "stratum": {
                    "family": key[4], "tier": key[5], "size_band": key[6],
                    "reference_threshold_stratum": key[7],
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


def solver_similarity_v1_8(
    primitives: Sequence[Mapping[str, Any]], *, display_floor: int = SIMILARITY_DISPLAY_FLOOR
) -> list[dict[str, Any]]:
    by_solver: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in primitives:
        identity = (str(row["solver"]), str(row["campaign"]))
        by_solver[identity][str(row["task_uuid"])] = row
    output = []
    for left, right in combinations(sorted(by_solver), 2):
        common = sorted(set(by_solver[left]) & set(by_solver[right]))
        left_fail = {task for task in common if by_solver[left][task]["outcome"] != "success"}
        right_fail = {task for task in common if by_solver[right][task]["outcome"] != "success"}
        union = left_fail | right_fail
        completed = [
            task for task in common
            if by_solver[left][task]["outcome"] != "indeterminate"
            and by_solver[right][task]["outcome"] != "indeterminate"
        ]
        spearman = _pearson(
            _average_ranks([float(by_solver[left][task]["absolute_error"]) for task in completed]),
            _average_ranks([float(by_solver[right][task]["absolute_error"]) for task in completed]),
        )
        sufficient = len(common) >= display_floor
        if not sufficient:
            jaccard_status, jaccard = "insufficient_data", None
        elif not union:
            jaccard_status, jaccard = "no_joint_failures", None
        else:
            jaccard_status = "ok"
            jaccard = len(left_fail & right_fail) / len(union)
        output.append(
            {
                "solver_i": left[0], "campaign_i": left[1],
                "solver_j": right[0], "campaign_j": right[1],
                "n_jointly_attempted": len(common),
                "n_jointly_completed": len(completed),
                "display_floor": display_floor,
                "status": "ok" if sufficient else "insufficient_data",
                "failure_set_jaccard_status": jaccard_status,
                "failure_set_jaccard": jaccard,
                "absolute_error_spearman": spearman if sufficient else None,
            }
        )
    return output


def solver_resource_ladders_v1_8(
    primitives: Sequence[Mapping[str, Any]],
    declarations: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Recompute declared ladder success sets and nestedness from primitives."""

    by_member: dict[str, dict[str, dict[str, Mapping[str, Any]]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for row in primitives:
        by_member[str(row["solver"])][str(row["campaign"])][str(row["task_uuid"])] = row
    output = []
    for declaration in declarations:
        ladder_id = str(declaration.get("ladder_id") or "")
        members = sorted(
            declaration.get("members", []),
            key=lambda row: row.get("member_index", -1),
        )
        if not ladder_id or len(members) < 2:
            raise ValueError("invalid ladder declaration")
        if [row.get("member_index") for row in members] != list(range(len(members))):
            raise ValueError(f"non-contiguous member indexes for ladder {ladder_id}")
        labels = [str(row.get("label") or "") for row in members]
        if len(set(labels)) != len(labels) or any(not label for label in labels):
            raise ValueError(f"invalid member labels for ladder {ladder_id}")
        knob_names = {
            key for member in members for key in member
            if key not in {"label", "member_index"}
        }
        if len(knob_names) != 1:
            raise ValueError(f"ladder {ladder_id} must declare exactly one resource knob")
        knob_name = next(iter(knob_names))
        if any(_finite_number(member.get(knob_name)) is None for member in members):
            raise ValueError(f"ladder {ladder_id} has an unpopulated knob value")
        campaigns = []
        for label in labels:
            available = sorted(by_member.get(label, {}))
            if len(available) != 1:
                raise ValueError(f"ladder member {label} must resolve to exactly one campaign")
            campaigns.append(available[0])
        if len(set(campaigns)) != 1:
            raise ValueError(f"ladder {ladder_id} crosses campaigns")
        campaign = campaigns[0]
        success_sets = []
        for member, label in zip(members, labels):
            rows = by_member[label][campaign]
            successes = sorted(task for task, row in rows.items() if row["outcome"] == "success")
            success_sets.append(
                {
                    "member_index": int(member["member_index"]),
                    "label": label,
                    "knob_value": float(member[knob_name]),
                    "n_reference_valid_attempts": len(rows),
                    "n_success": len(successes),
                    "success_task_uuids": successes,
                }
            )
        pair_diagnostics = []
        total_joint, total_violations = 0, 0
        for left_index, right_index in combinations(range(len(members)), 2):
            left_label, right_label = labels[left_index], labels[right_index]
            left_rows = by_member[left_label][campaign]
            right_rows = by_member[right_label][campaign]
            common = sorted(set(left_rows) & set(right_rows))
            violations = sorted(
                task for task in common
                if left_rows[task]["outcome"] == "success"
                and right_rows[task]["outcome"] != "success"
            )
            total_joint += len(common)
            total_violations += len(violations)
            pair_diagnostics.append(
                {
                    "earlier_member": left_label,
                    "later_member": right_label,
                    "jointly_attempted_reference_valid_tasks": len(common),
                    "violations": len(violations),
                    "violation_rate": len(violations) / len(common) if common else None,
                    "violating_task_uuids": violations,
                }
            )
        output.append(
            {
                "ladder_id": ladder_id,
                "campaign": campaign,
                "method_axis": str(declaration.get("method_axis") or ""),
                "knob_name": knob_name,
                "members": success_sets,
                "nestedness": {
                    "definition": DEFINITIONS["solver_resource_ladders"],
                    "joint_task_member_pairs": total_joint,
                    "violations": total_violations,
                    "violation_rate": total_violations / total_joint if total_joint else None,
                    "pair_diagnostics": pair_diagnostics,
                },
            }
        )
    return sorted(output, key=lambda row: row["ladder_id"])


def _attempt_disposition(
    task: Mapping[str, Any] | None, attempt: Mapping[str, Any]
) -> str:
    if _record_is_not_attempted(attempt):
        return "not_attempted"
    if task is None:
        return "unjoinable"
    if not _public_task(task):
        return "excluded_test_tier"
    grade = _reference_grade(task)
    if grade == "missing":
        return "excluded_missing_taxonomy_grade"
    if grade not in VALID_REFERENCE_GRADES:
        return "excluded_invalid_reference_grade"
    if _reference_energy(task) is None:
        return "excluded_missing_reference_energy"
    if (_threshold(task) or 0.0) <= 0.0:
        return "excluded_missing_or_invalid_threshold"
    return "scored"


def _record_correction_reconciliation(
    tasks: Mapping[str, Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if metadata is None:
        return {
            "source": None,
            "campaign": None,
            "n_original_corrections_declared": 0,
            "n_original_corrections_present": 0,
            "n_original_corrections_attempted": 0,
            "n_diamond_corrections_declared": 0,
            "disposition_counts": {},
            "attempt_outcome_counts": {},
            "scored_outcome_counts": {},
            "original_correction_files": [],
            "identity": "no G-39 correction ledger supplied for this synthetic bundle",
        }
    files = [str(path) for path in metadata.get("original_corrections", [])]
    by_source = {str(row.get("source")): row for row in attempts}
    missing = sorted(set(files) - set(by_source))
    if missing:
        raise ValueError(f"G-39 correction records absent from ingest: {missing}")
    rows = [by_source[path] for path in files]
    dispositions = Counter(
        _attempt_disposition(tasks.get(str(row.get("task_uuid", ""))), row)
        for row in rows
    )
    attempt_outcomes = Counter(
        "indeterminate" if _finite_number(row.get("energy")) is None else "completed"
        for row in rows
    )
    scored_outcomes = Counter()
    for row in rows:
        task = tasks.get(str(row.get("task_uuid", "")))
        if _attempt_disposition(task, row) == "scored" and task is not None:
            scored_outcomes[classify_outcome_v1_8(row.get("energy"), task)["outcome"]] += 1
    return {
        "source": str(metadata.get("source") or "unknown"),
        "campaign": str(metadata.get("campaign") or "unknown"),
        "n_original_corrections_declared": len(files),
        "n_original_corrections_present": len(rows),
        "n_original_corrections_attempted": sum(
            not _record_is_not_attempted(row) for row in rows
        ),
        "n_diamond_corrections_declared": len(metadata.get("diamond_corrections", [])),
        "disposition_counts": dict(sorted(dispositions.items())),
        "attempt_outcome_counts": dict(sorted(attempt_outcomes.items())),
        "scored_outcome_counts": dict(sorted(scored_outcomes.items())),
        "original_correction_files": sorted(files),
        "identity": (
            "all 27 original G-39 corrections are attempted; reference-valid "
            "records reappear as indeterminate outcomes and other records retain "
            "their normal section-3 disposition"
        ),
    }


def diagnostics_v1_8(
    tasks: Mapping[str, Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    correction_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    dispositions = Counter()
    active_attempts = [row for row in attempts if not _record_is_not_attempted(row)]
    orphan_attempts: list[Mapping[str, Any]] = []
    joined_attempts = [row for row in active_attempts if row.get("joined_via_legacy_mapping")]
    pre_mapping_unjoinable = [
        row
        for row in active_attempts
        if str(row.get("original_task_uuid", row.get("task_uuid", ""))) not in tasks
    ]
    covered_task_ids = {str(row.get("task_uuid", "")) for row in active_attempts}
    for attempt in attempts:
        task_id = str(attempt.get("task_uuid", ""))
        task = tasks.get(task_id)
        disposition = _attempt_disposition(task, attempt)
        dispositions[disposition] += 1
        if task is None and disposition != "not_attempted":
            orphan_attempts.append(attempt)

    joinable_ids = covered_task_ids & set(tasks)
    test_ids = {task_id for task_id in joinable_ids if not _public_task(tasks[task_id])}
    public_ids = joinable_ids - test_ids
    missing_grade_ids = {
        task_id for task_id in public_ids if _reference_grade(tasks[task_id]) == "missing"
    }
    unspecified_size_ids = {
        task_id for task_id in public_ids if _size_band(tasks[task_id]) == "unspecified"
    }
    uncertainty_task_ids = {
        task_id
        for task_id, task in tasks.items()
        if _reference_uncertainty(task) is not None
    }
    dominated_task_ids = {
        task_id
        for task_id, task in tasks.items()
        if (_threshold(task) or 0.0) > 0.0
        and _reference_uncertainty(task) is not None
        and float(_reference_uncertainty(task)) > float(_threshold(task)) / 2.0
    }
    source_counts = Counter(
        str(tasks[task_id].get("metrics_norb_source", "unspecified"))
        for task_id in public_ids
    )
    solver_campaigns: dict[str, set[str]] = defaultdict(set)
    for row in attempts:
        solver_campaigns[str(row.get("solver", "unknown"))].add(_campaign(row))
    campaign_counts = Counter(_campaign(row) for row in attempts)
    campaign_source_counts = Counter(
        str(row.get("campaign_source") or "unknown") for row in attempts
    )
    correction = _record_correction_reconciliation(tasks, attempts, correction_metadata)
    return {
        "public_definition": DEFINITIONS["public_task"],
        "task_coverage": {
            "n_distinct_attempted_task_uuids": len(covered_task_ids),
            "n_public_task_uuids": len(public_ids),
            "n_test_tier_task_uuids": len(test_ids),
            "n_orphan_task_uuids": len(covered_task_ids - set(tasks)),
            "test_tier_task_uuids": sorted(test_ids),
            "identity": "attempted = public + test_tier + orphan",
        },
        "attempt_disposition": {
            "n_records_all_committed": len(attempts),
            "n_attempted_records": len(active_attempts),
            "n_not_attempted_records": dispositions["not_attempted"],
            "counts": dict(sorted(dispositions.items())),
            "identity": "all committed records = scored + not_attempted + excluded categories",
        },
        "campaign_identity": {
            "definition": DEFINITIONS["campaign_identity"],
            "campaign_record_counts": dict(sorted(campaign_counts.items())),
            "campaign_source_counts": dict(sorted(campaign_source_counts.items())),
            "campaigns_by_solver": {
                solver: sorted(campaigns) for solver, campaigns in sorted(solver_campaigns.items())
            },
            "n_solver_campaigns": sum(len(campaigns) for campaigns in solver_campaigns.values()),
        },
        "record_correction": correction,
        "threshold_provenance": DEFINITIONS["threshold_provenance"],
        "legacy_mapping": {
            "mapping_source": next(
                (str(row.get("legacy_mapping_source")) for row in joined_attempts), None
            ),
            "n_pre_mapping_unjoinable_attempts": len(pre_mapping_unjoinable),
            "n_joined_via_legacy_mapping": len(joined_attempts),
            "joined_via_legacy_mapping_by_solver": dict(
                sorted(
                    Counter(str(row.get("solver", "unknown")) for row in joined_attempts).items()
                )
            ),
            "n_still_unjoinable_attempts": len(orphan_attempts),
            "identity": "pre_mapping_unjoinable = joined_via_legacy_mapping + still_unjoinable",
        },
        "unjoinable_attempts": {
            "n_attempts": len(orphan_attempts),
            "by_solver": dict(
                sorted(
                    Counter(
                        str(row.get("solver", "unknown")) for row in orphan_attempts
                    ).items()
                )
            ),
            "by_solution_file_family": dict(
                sorted(
                    Counter(
                        str(row.get("solution_file_family", "unknown"))
                        for row in orphan_attempts
                    ).items()
                )
            ),
            "orphan_task_uuids": sorted(covered_task_ids - set(tasks)),
        },
        "size_band": {
            "metadata_fields_read": list(NORB_METADATA_FIELDS),
            "n_public_tasks": len(public_ids),
            "n_unspecified_public_tasks": len(unspecified_size_ids),
            "n_unspecified_public_attempts": sum(
                str(row.get("task_uuid", "")) in unspecified_size_ids for row in active_attempts
            ),
            "unspecified_public_task_uuids": sorted(unspecified_size_ids),
            "norb_source_counts": dict(sorted(source_counts.items())),
        },
        "reference_uncertainty": {
            "fields_read": list(REFERENCE_UNCERTAINTY_FIELDS),
            "fields_deliberately_excluded": list(REFERENCE_UNCERTAINTY_EXCLUDED_FIELDS),
            "excluded_field_occurrences": sum(
                "qsz_afqmc_standard_error_hartree" in _features(task)
                for task in tasks.values()
            ),
            "n_corpus_tasks_with_uncertainty": len(uncertainty_task_ids),
            "n_threshold_dominated_corpus_tasks": len(dominated_task_ids),
            "threshold_dominated_corpus_task_uuids": sorted(dominated_task_ids),
        },
        "taxonomy_grade": {
            "fallback_used": False,
            "n_public_attempted_tasks_missing_grade": len(missing_grade_ids),
            "public_attempted_task_uuids_missing_grade": sorted(missing_grade_ids),
            "n_corpus_tasks_missing_grade": sum(
                _reference_grade(task) == "missing" for task in tasks.values()
            ),
        },
    }


def coverage_v1_8(
    tasks: Mapping[str, Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Report coverage-only records separately from actual attempts."""

    attempted = [row for row in records if not _record_is_not_attempted(row)]
    not_attempted = [row for row in records if _record_is_not_attempted(row)]
    entries = []
    for row in not_attempted:
        task_id = str(row.get("task_uuid", ""))
        task = tasks.get(task_id)
        entry = {
            "solver": str(row.get("solver", "unknown")),
            "campaign": _campaign(row),
            "task_uuid": task_id,
            "original_task_uuid": str(row.get("original_task_uuid", task_id)),
            "reason": str(row.get("not_attempted_reason") or "unspecified"),
            "harness_status": (
                str(row.get("harness_status")) if row.get("harness_status") is not None else None
            ),
            "source": str(row.get("source", "unknown")),
        }
        if task is not None:
            entry.update({"family": _labels(task)["family"], "tier": _labels(task)["tier"]})
        entries.append(entry)
    entries.sort(
        key=lambda row: (row["solver"], row["campaign"], row["task_uuid"], row["source"])
    )
    return {
        "definition": DEFINITIONS["not_attempted"],
        "n_records_all_committed": len(records),
        "n_attempted_records": len(attempted),
        "n_not_attempted_records": len(not_attempted),
        "attempted_by_solver": dict(
            sorted(Counter(str(row.get("solver", "unknown")) for row in attempted).items())
        ),
        "not_attempted_by_solver": dict(
            sorted(Counter(str(row.get("solver", "unknown")) for row in not_attempted).items())
        ),
        "attempted_by_solver_campaign": dict(
            sorted(
                Counter(
                    f"{row.get('solver', 'unknown')}@{_campaign(row)}"
                    for row in attempted
                ).items()
            )
        ),
        "not_attempted_by_solver_campaign": dict(
            sorted(
                Counter(
                    f"{row.get('solver', 'unknown')}@{_campaign(row)}"
                    for row in not_attempted
                ).items()
            )
        ),
        "not_attempted_reason_counts": dict(
            sorted(
                Counter(
                    str(row.get("not_attempted_reason") or "unspecified")
                    for row in not_attempted
                ).items()
            )
        ),
        "not_attempted": entries,
        "identity": "all_committed_records = attempted_records + not_attempted_records",
    }


def build_bundle_v1_8(
    tasks: Mapping[str, Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    *,
    bootstrap_iterations: int = 1000,
    ladder_declarations: Sequence[Mapping[str, Any]] = (),
    correction_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the complete serializable v1.8 bundle from normalized records."""

    active_attempts = [row for row in attempts if not _record_is_not_attempted(row)]
    public_attempts = [
        attempt
        for attempt in active_attempts
        if str(attempt.get("task_uuid", "")) in tasks
        and _public_task(tasks[str(attempt.get("task_uuid", ""))])
    ]
    primitives = per_solver_task_primitives_v1_8(tasks, active_attempts)
    agreement = agreement_v1_8(tasks, active_attempts)
    task_classes = panel_descriptive_stats_v1_8(primitives)
    diagnostics = diagnostics_v1_8(tasks, attempts, correction_metadata)
    solver_campaigns = sorted(
        {(str(row.get("solver", "unknown")), _campaign(row)) for row in attempts}
    )
    scored_solver_campaigns = sorted(
        {(str(row["solver"]), str(row["campaign"])) for row in primitives}
    )
    return {
        "metrics_spec_version": METRICS_SPEC_VERSION,
        "definitions": DEFINITIONS,
        "headline_counts": {
            "solvers_found": sorted({str(row.get("solver", "unknown")) for row in attempts}),
            "n_solvers_found": len({str(row.get("solver", "unknown")) for row in attempts}),
            "n_scored_solvers": len({str(row["solver"]) for row in primitives}),
            "solver_campaigns_found": [
                {"solver": solver, "campaign": campaign}
                for solver, campaign in solver_campaigns
            ],
            "n_solver_campaigns_found": len(solver_campaigns),
            "n_scored_solver_campaigns": len(scored_solver_campaigns),
            "n_records_all_committed": len(attempts),
            "n_attempts_all_committed": len(active_attempts),
            "n_not_attempted_records": len(attempts) - len(active_attempts),
            "n_public_attempts": len(public_attempts),
            "n_scored_attempts": len(primitives),
            "n_tasks_covered_all_committed": len({str(row.get("task_uuid")) for row in attempts}),
            "n_public_tasks_covered": len({str(row.get("task_uuid")) for row in public_attempts}),
            "n_scored_tasks": len({str(row["task_uuid"]) for row in primitives}),
            "task_class_counts": dict(
                sorted(Counter(row["task_class"] for row in task_classes).items())
            ),
            "strata_populated": {
                key: sorted({str(row[key]) for row in primitives})
                for key in ("family", "tier", "size_band", "reference_threshold_stratum")
            },
        },
        "coverage": coverage_v1_8(tasks, attempts),
        "primitives": primitives,
        "panel_descriptive_stats": task_classes,
        "stratified_aggregation": stratified_aggregation_v1_8(
            primitives, bootstrap_iterations=bootstrap_iterations
        ),
        "agreement": agreement,
        "similarity": solver_similarity_v1_8(primitives),
        "diagnostics": diagnostics,
        "ladders": solver_resource_ladders_v1_8(primitives, ladder_declarations),
        "attributions": {},
    }
