"""Focused tests for the ML-8D UQ solvability estimator."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from qb_gsee_benchmark.ml.solvability_uq import (
    PREREGISTRATION_ID,
    brier_decomposition,
    calibration_slope_intercept,
    design_based_interval,
    evaluate_calibration_gate,
    expected_calibration_error,
    isotonic_fallback_probabilities,
    joint_latent_samples,
    laplace_gp_fit,
    laplace_gp_predict,
    load_uq_preregistration,
    mackay_probability,
    project_to_psd,
    reliability_bins,
)

PREREGISTRATION = Path("analysis/ml_solvability_uq/preregistration.json")


def test_preregistration_is_frozen_gated_and_supersedes_nothing():
    payload = load_uq_preregistration(PREREGISTRATION)
    assert payload["artifact_id"] == PREREGISTRATION_ID
    assert payload["frozen_before_any_estimator_fit"] is True
    assert payload["supersedes"] is None
    assert payload["gate"]["satisfied"] is True
    assert payload["scope"] == "gradeable tasks only, both tracks"
    assert payload["design_based_track"]["role"] == "ratio_of_record"
    assert payload["design_based_track"]["may_be_displaced_by_model_output"] is False
    assert payload["design_based_track"]["bootstrap"]["primary"] == "family_grouped"
    assert payload["calibration_gate"]["nature"] == "calibration_not_discrimination"
    assert (
        payload["calibration_gate"]["thresholds_frozen_before_any_value_computed"]
        is True
    )
    assert payload["model_based_ratio"]["weighted"] is False
    assert payload["held_state"]["validated_predictor_claim"] is False
    assert payload["stop_at"]["no_validated_predictor_rule_stands"] is True
    assert payload["miscalibration_reference_of_record"]["both_knn_quantities_required"]


def test_preregistration_pins_the_ml8a_and_ml8c_artifacts_it_consumes():
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    census = json.loads(
        Path("analysis/ml_gradeability_census/held_v1/artifact_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    by_path = {record["path"]: record["sha256"] for record in census["files"]}
    assert payload["inputs"]["gradeability_census"]["sha256"] == by_path["census.csv"]
    annex = json.loads(
        Path(
            "analysis/ml_g50_solver_families/sensitivity_gradeable_mask_v1/artifact_manifest.json"
        ).read_text(encoding="utf-8")
    )
    annex_by_path = {record["path"]: record["sha256"] for record in annex["files"]}
    for key, name in (
        ("masked_observations", "masked_observations.csv"),
        ("gradeable_selection_weights", "gradeable_selection_weights.csv"),
        ("knn_predictions", "predictions.csv"),
        ("ml8c_report", "report.json"),
    ):
        assert payload["inputs"][key]["sha256"] == annex_by_path[name], key


def test_design_bootstrap_brackets_the_point_estimate_and_is_deterministic():
    weights = np.asarray([10.0, 5.0, 1.0, 4.0], dtype=float)
    success = np.asarray([1.0, 0.0, 1.0, 1.0], dtype=float)
    families = ["a", "a", "b", "c"]
    point = float((weights * success).sum() / weights.sum())
    first = design_based_interval(
        weights, success, families, grouping="family_grouped", draws=200, seed=7
    )
    second = design_based_interval(
        weights, success, families, grouping="family_grouped", draws=200, seed=7
    )
    assert first == second
    assert first["lower_95"] <= point <= first["upper_95"]
    assert first["accepted_draws"] == 200
    assert first["attempted_draws"] >= 200
    center = design_based_interval(
        weights, success, families, grouping="center_level", draws=200, seed=7
    )
    assert center["lower_95"] <= point <= center["upper_95"]


def test_design_bootstrap_is_degenerate_when_every_center_succeeds():
    weights = np.asarray([3.0, 2.0], dtype=float)
    success = np.asarray([1.0, 1.0], dtype=float)
    result = design_based_interval(
        weights, success, ["a", "b"], grouping="family_grouped", draws=50, seed=1
    )
    assert result["lower_95"] == pytest.approx(1.0)
    assert result["upper_95"] == pytest.approx(1.0)


def test_psd_projection_reports_the_correction_it_makes():
    indefinite = np.asarray([[1.0, 2.0], [2.0, 1.0]])
    projected, diagnostics = project_to_psd(indefinite, tolerance=-1e-10, jitter=1e-8)
    assert diagnostics["projection_applied"] is True
    assert diagnostics["min_eigenvalue_before_projection"] == pytest.approx(-1.0)
    assert diagnostics["frobenius_norm_of_correction"] > 0.0
    assert np.linalg.eigvalsh(projected).min() >= -1e-9
    definite = np.asarray([[1.0, 0.1], [0.1, 1.0]])
    _, clean = project_to_psd(definite, tolerance=-1e-10, jitter=1e-8)
    assert clean["projection_applied"] is False
    assert clean["frobenius_norm_of_correction"] == 0.0


def test_laplace_gp_separates_a_clean_one_dimensional_problem():
    positions = np.linspace(0.0, 1.0, 12)
    distance = np.abs(positions[:, None] - positions[None, :])
    kernel, _ = project_to_psd(
        np.exp(-(distance**2) / (2.0 * 0.25**2)), tolerance=-1e-10, jitter=1e-8
    )
    y = (positions > 0.5).astype(float)
    fit = laplace_gp_fit(kernel, y, max_iterations=100, tolerance=1e-9)
    assert fit["converged"] is True
    assert fit["iterations"] <= 100
    # latent mean should order with the label
    assert fit["latent"][0] < 0.0 < fit["latent"][-1]
    predicted = laplace_gp_predict(fit, kernel, kernel)
    probability = mackay_probability(predicted["mean"], predicted["variance"])
    assert probability[0] < 0.5 < probability[-1]
    assert np.all(predicted["variance"] >= 0.0)


def test_laplace_gp_raises_rather_than_silently_not_converging():
    kernel = np.eye(4)
    y = np.asarray([0.0, 1.0, 0.0, 1.0])
    with pytest.raises(ValueError, match="did not converge"):
        laplace_gp_fit(kernel, y, max_iterations=1, tolerance=1e-30)


def test_joint_latent_samples_are_seeded_and_match_their_moments():
    mean = np.asarray([0.5, -0.25])
    covariance = np.asarray([[1.0, 0.5], [0.5, 1.0]])
    first = joint_latent_samples(mean, covariance, draws=20000, seed=11, jitter=1e-10)
    second = joint_latent_samples(mean, covariance, draws=20000, seed=11, jitter=1e-10)
    assert np.array_equal(first, second)
    assert first.shape == (20000, 2)
    assert np.allclose(first.mean(axis=0), mean, atol=0.05)
    empirical = np.cov(first, rowvar=False)
    assert np.allclose(empirical, covariance, atol=0.05)


def test_reliability_bins_partition_the_sample_and_ece_is_zero_when_perfect():
    probability = np.asarray([0.0] * 5 + [1.0] * 5)
    y = np.asarray([0.0] * 5 + [1.0] * 5)
    rows = reliability_bins(probability, y, bins=5)
    assert sum(row["n_tasks"] for row in rows) == 10
    assert expected_calibration_error(probability, y, bins=5) == pytest.approx(0.0)
    # Fully inverted predictions. Equal-count binning puts 2 tasks per bin, so
    # the bin straddling the p=0/p=1 boundary holds one of each and cancels
    # (mean predicted 0.5, observed 0.5); the other four bins each contribute a
    # gap of 1. ECE is therefore 4/5, not 1 -- a property of quantile bins, and
    # the frozen instrument is the quantile-binned one.
    inverted = np.asarray([1.0] * 5 + [0.0] * 5)
    assert expected_calibration_error(inverted, y, bins=5) == pytest.approx(0.8)
    bins = reliability_bins(inverted, y, bins=5)
    assert [row["absolute_gap"] for row in bins] == pytest.approx([1.0, 1.0, 0.0, 1.0, 1.0])


def test_calibration_slope_is_one_for_self_consistent_probabilities():
    rng = np.random.default_rng(3)
    probability = rng.uniform(0.05, 0.95, size=4000)
    y = (rng.uniform(size=4000) < probability).astype(float)
    slope, intercept = calibration_slope_intercept(probability, y, clip=1e-6)
    assert slope == pytest.approx(1.0, abs=0.15)
    assert intercept == pytest.approx(0.0, abs=0.15)


def test_calibration_slope_returns_none_on_a_single_class():
    probability = np.asarray([0.2, 0.4, 0.6])
    assert calibration_slope_intercept(probability, np.zeros(3), clip=1e-6) == (
        None,
        None,
    )


def test_brier_decomposition_matches_the_direct_brier_score():
    probability = np.asarray([0.1, 0.4, 0.6, 0.9, 0.5, 0.2])
    y = np.asarray([0.0, 0.0, 1.0, 1.0, 1.0, 0.0])
    parts = brier_decomposition(probability, y, bins=3)
    assert parts["brier"] == pytest.approx(float(np.mean((probability - y) ** 2)))
    assert parts["brier_uncertainty"] == pytest.approx(
        float(np.mean(y)) * (1.0 - float(np.mean(y)))
    )
    assert parts["brier_reliability"] >= 0.0
    assert parts["brier_resolution"] >= 0.0


def test_gate_requires_both_conditions():
    assert evaluate_calibration_gate(
        ece=0.05, slope_lower=0.8, slope_upper=1.3, ece_threshold=0.10
    )["calibration_gate_passed"] is True
    assert evaluate_calibration_gate(
        ece=0.15, slope_lower=0.8, slope_upper=1.3, ece_threshold=0.10
    )["calibration_gate_passed"] is False
    assert evaluate_calibration_gate(
        ece=0.05, slope_lower=1.2, slope_upper=1.9, ece_threshold=0.10
    )["calibration_gate_passed"] is False
    absent = evaluate_calibration_gate(
        ece=0.05, slope_lower=None, slope_upper=None, ece_threshold=0.10
    )
    assert absent["slope_interval_contains_one"] is False
    assert absent["calibration_gate_passed"] is False


def test_gate_boundary_is_inclusive_exactly_as_frozen():
    verdict = evaluate_calibration_gate(
        ece=0.10, slope_lower=1.0, slope_upper=1.0, ece_threshold=0.10
    )
    assert verdict["ece_condition_met"] is True
    assert verdict["slope_interval_contains_one"] is True
    assert verdict["calibration_gate_passed"] is True


def test_isotonic_fallback_is_monotone_and_bounded():
    train = np.asarray([0.1, 0.3, 0.5, 0.7, 0.9])
    y = np.asarray([0.0, 0.0, 1.0, 1.0, 1.0])
    out = isotonic_fallback_probabilities(train, y, np.asarray([0.0, 0.4, 0.6, 1.0]))
    assert np.all((out >= 0.0) & (out <= 1.0))
    assert np.all(np.diff(out) >= -1e-12)
