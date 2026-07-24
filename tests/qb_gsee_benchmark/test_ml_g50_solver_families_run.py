from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from qb_gsee_benchmark.ml.g50_solver_families import (
    canonical_family_map,
    g50_variant_rows,
    load_preregistration,
    resolve_input_path,
)
from qb_gsee_benchmark.ml.g50_solver_families_run import (
    build_size_sector_frame,
    load_rung_recovery_amendment,
    load_size_sector_amendment,
    load_trimci_bounded_rung_amendment,
    lofo_knn_probabilities,
    normalize_g50_outcomes,
    variant_eligibility,
    verify_and_promote_two_runs,
)

ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml_g50_solver_families/preregistration.json"
AMENDMENT = ROOT / "analysis/ml_g50_solver_families/amendment_size_sector_backfill.json"
RUNG_AMENDMENT = (
    ROOT / "analysis/ml_g50_solver_families/amendment_rung_ledger_recovery.json"
)
TRIMCI_AMENDMENT = (
    ROOT
    / "analysis/ml_g50_solver_families/amendment_trimci_bounded_rung_semantics.json"
)


def _inputs() -> tuple[dict, dict[str, str], list[dict]]:
    preregistration = load_preregistration(PREREGISTRATION)
    taxonomy = json.loads(
        resolve_input_path(
            ROOT, preregistration["inputs"]["canonical_families"]
        ).read_text(encoding="utf-8")
    )
    variants = g50_variant_rows(
        resolve_input_path(ROOT, preregistration["inputs"]["solver_family_catalog"])
    )
    return preregistration, canonical_family_map(taxonomy), variants


def test_g50_size_sector_amendment_resolves_exact_null_set() -> None:
    preregistration = load_preregistration(PREREGISTRATION)
    _, backfill = load_size_sector_amendment(ROOT, AMENDMENT, PREREGISTRATION)
    features = pd.read_csv(
        resolve_input_path(ROOT, preregistration["inputs"]["feature_table"]),
        low_memory=False,
    )
    frame = build_size_sector_frame(features, backfill)
    assert frame.shape == (718, 4)
    assert np.isfinite(frame.to_numpy(dtype=float)).all()
    assert len(backfill) == 127


def test_g50_outcome_normalization_applies_bounded_trimci_failures() -> None:
    preregistration, canonical, variants = _inputs()
    _, rung_recovery = load_rung_recovery_amendment(ROOT, RUNG_AMENDMENT)
    _, trimci_recovery = load_trimci_bounded_rung_amendment(
        ROOT, TRIMCI_AMENDMENT, PREREGISTRATION
    )
    observations, coverage = normalize_g50_outcomes(
        ROOT,
        preregistration,
        variants,
        canonical,
        rung_recovery,
        trimci_recovery,
    )
    assert len(observations) == 1728
    assert len(coverage) == 1728
    assert {row["observed_outcome"] for row in observations} == {"fail", "success"}
    assert (
        sum(
            row["observation_source"] == "trimci_all_parent_checkpoint"
            for row in observations
        )
        == 388
    )
    trimci_failures = [
        row
        for row in observations
        if row["observation_source"] == "trimci_bounded_milestone_failure"
    ]
    assert len(trimci_failures) == 284
    assert {row["observed_outcome"] for row in trimci_failures} == {"fail"}
    assert {row["metric_outcome_annotation"] for row in trimci_failures} == {
        "indeterminate"
    }
    assert {row["metric_status_annotation"] for row in trimci_failures} == {
        "indeterminate"
    }
    assert {row["energy_hartree"] for row in trimci_failures} == {None}
    assert (
        sum(row["observation_source"] == "dmrg_rung_ledger" for row in observations)
        == 285
    )
    assert (
        sum(row["observation_source"] == "shci_rung_ledger" for row in observations)
        == 229
    )
    assert sum(row["coverage_status"] == "observed_rung" for row in coverage) == 514
    assert (
        sum(row["coverage_status"] == "missing_attempted_rung" for row in coverage)
        == 254
    )
    assert (
        sum(row["coverage_status"] == "bounded_failure_unreached" for row in coverage)
        == 284
    )
    assert (
        sum(row["coverage_status"] == "observed_checkpoint" for row in coverage) == 166
    )
    assert (
        sum(
            row["coverage_status"] == "observed_parent_completed_below_cap"
            for row in coverage
        )
        == 222
    )
    eligibility = variant_eligibility(
        pd.DataFrame(observations),
        variants,
        preregistration["model_eligibility_floor"],
    )
    assert len(eligibility) == 18
    assert all(
        row["model_status"] == "eligible" and row["n_labels"] == 96
        for row in eligibility
        if row["solver_short_name"].startswith("TrimCI_ndet_")
    )


def test_g50_knn_excludes_query_family() -> None:
    tasks = [f"task-{index}" for index in range(6)]
    families = np.asarray(["A", "A", "B", "B", "C", "C"], dtype=object)
    distance = np.abs(np.subtract.outer(np.arange(6), np.arange(6))).astype(float)
    indices = np.arange(6)
    labels = np.asarray([0, 1, 0, 0, 1, 1])
    first = lofo_knn_probabilities(distance, indices, labels, families, tasks, k=2)
    changed = labels.copy()
    changed[:2] = [1, 0]
    second = lofo_knn_probabilities(distance, indices, changed, families, tasks, k=2)
    assert np.array_equal(first[:2], second[:2])


def test_g50_two_run_verifier_requires_byte_identity(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "artifact_manifest.json").write_text("same\n", encoding="utf-8")
    (second / "artifact_manifest.json").write_text("same\n", encoding="utf-8")
    report = verify_and_promote_two_runs(
        first,
        second,
        tmp_path / "promoted",
        tmp_path / "identity.json",
    )
    assert report["byte_identical"] is True
    assert report["file_count"] == 1
