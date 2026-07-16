"""Metrics v1.9 headline source selection over v1.8 scoring semantics."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .v1_8 import build_bundle_v1_8

METRICS_SPEC_VERSION = "1.9"
HISTORICAL_IPIE_CAMPAIGNS = frozenset(
    {"ipie_swing_2026-07", "ipie_swing_envfix_2026-07"}
)


def _validated_designation(
    designation: Mapping[str, Any],
) -> tuple[str, frozenset[str], int, int, Mapping[str, int]]:
    source = designation.get("designation")
    approval = designation.get("pi_approval")
    scope = designation.get("scope")
    outcome_counts = designation.get("outcome_counts")
    solver_uuids = designation.get("solver_uuids")
    if not all(
        isinstance(item, Mapping)
        for item in (source, approval, scope, outcome_counts, solver_uuids)
    ):
        raise ValueError("metrics v1.9 designation is incomplete")
    if (
        source.get("effective") is not True
        or source.get("status") != "effective"
        or approval.get("status") != "approved"
    ):
        raise ValueError("metrics v1.9 designation is not effective")
    if source.get("pool_campaigns") is not False:
        raise ValueError("metrics v1.9 forbids campaign pooling")
    if source.get("legacy_fallback_allowed") is not False:
        raise ValueError("metrics v1.9 forbids task-level legacy fallback")
    campaign = str(designation.get("campaign_id") or "")
    if not campaign or source.get("headline_source_after_approval") != campaign:
        raise ValueError("metrics v1.9 campaign binding is inconsistent")
    solvers = frozenset(str(key) for key in solver_uuids)
    expected_solver_count = int(scope.get("solver_count", -1))
    expected_task_count = int(scope.get("task_count", -1))
    expected_pair_count = int(scope.get("task_solver_pair_count", -1))
    if (
        len(solvers) != expected_solver_count
        or min(expected_task_count, expected_pair_count) < 1
    ):
        raise ValueError("metrics v1.9 designation scope is inconsistent")
    expected_outcomes = {
        str(key): int(value)
        for key, value in outcome_counts.items()
        if str(key) in {"completed", "failed", "timeout", "not_attempted"}
    }
    if sum(expected_outcomes.values()) != expected_pair_count:
        raise ValueError("metrics v1.9 outcome counts do not cover the scope")
    return (
        campaign,
        solvers,
        expected_task_count,
        expected_pair_count,
        expected_outcomes,
    )


def select_headline_attempts_v1_9(
    attempts: Sequence[Mapping[str, Any]],
    designation: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select headline records without pooling or legacy fallback."""

    (
        campaign,
        designated_solvers,
        expected_task_count,
        expected_pair_count,
        expected_outcomes,
    ) = _validated_designation(designation)
    designated = [
        dict(row)
        for row in attempts
        if str(row.get("solver")) in designated_solvers
        and str(row.get("campaign")) == campaign
    ]
    if len(designated) != expected_pair_count:
        raise ValueError(
            f"designated campaign has {len(designated)} rows, "
            f"expected {expected_pair_count}"
        )
    if len({str(row.get("task_uuid")) for row in designated}) != expected_task_count:
        raise ValueError("designated campaign task count does not match its scope")
    pairs = [(str(row.get("solver")), str(row.get("task_uuid"))) for row in designated]
    if len(set(pairs)) != len(pairs):
        raise ValueError("designated campaign contains duplicate solver/task pairs")
    per_task = Counter(task_uuid for _, task_uuid in pairs)
    if set(per_task.values()) != {len(designated_solvers)}:
        raise ValueError("designated campaign is not a complete solver-by-task panel")
    actual_outcomes = Counter(str(row.get("harness_status")) for row in designated)
    normalized_actual_outcomes = {
        status: actual_outcomes.get(status, 0) for status in expected_outcomes
    }
    if normalized_actual_outcomes != expected_outcomes:
        raise ValueError(
            f"designated campaign outcome counts differ: {dict(actual_outcomes)}"
        )

    selected: list[dict[str, Any]] = []
    excluded = Counter()
    for raw in attempts:
        row = dict(raw)
        solver = str(row.get("solver"))
        row_campaign = str(row.get("campaign"))
        if solver in designated_solvers:
            if row_campaign != campaign:
                excluded["superseded_designated_solver_campaign"] += 1
                continue
        elif solver == "ipie_uhf_trial" and row_campaign in HISTORICAL_IPIE_CAMPAIGNS:
            excluded["historical_ipie_campaign"] += 1
            continue
        selected.append(row)

    return selected, {
        "metrics_spec_version": METRICS_SPEC_VERSION,
        "designated_campaign": campaign,
        "designated_solvers": sorted(designated_solvers),
        "designated_outcome_counts": dict(sorted(normalized_actual_outcomes.items())),
        "legacy_campaign": str(designation["designation"].get("legacy_campaign") or ""),
        "legacy_fallback_allowed": False,
        "pool_campaigns": False,
        "excluded_record_counts": dict(sorted(excluded.items())),
        "historical_ipie_campaigns_excluded": sorted(HISTORICAL_IPIE_CAMPAIGNS),
        "legacy_retention": {
            "role": "versioned_agreement_audit_only",
            "adjudication_sha256": str(
                designation.get("supporting_bindings", {}).get(
                    "adjudication_sha256", ""
                )
            ),
        },
    }


def build_bundle_v1_9(
    tasks: Mapping[str, Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    designation: Mapping[str, Any],
    *,
    bootstrap_iterations: int = 1000,
    ladder_declarations: Sequence[Mapping[str, Any]] = (),
    correction_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build v1.9 using v1.8 scoring after headline source selection."""

    selected, source_selection = select_headline_attempts_v1_9(attempts, designation)
    bundle = build_bundle_v1_8(
        tasks,
        selected,
        bootstrap_iterations=bootstrap_iterations,
        ladder_declarations=ladder_declarations,
        correction_metadata=correction_metadata,
    )
    bundle["metrics_spec_version"] = METRICS_SPEC_VERSION
    bundle["source_selection"] = source_selection
    return bundle
