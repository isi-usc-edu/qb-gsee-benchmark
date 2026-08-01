from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from qb_gsee_benchmark.ml.bayesian_irt_recovery import (
    CPU_FACTOR_ANCHOR,
    canonical_family_folds,
    factor_transform,
    identified_factor_model,
    verify_recovery_preregistration,
)
from qb_gsee_benchmark.ml.bayesian_irt_run import (
    IPIE_FACTOR_ANCHOR,
    prepare_irt_data,
)
from qb_gsee_benchmark.ml.core_set import sha256_file


ROOT = Path(__file__).resolve().parents[2]
RECOVERY = ROOT / "analysis/ml9_bayesian_irt/recovery_preregistration_v2.json"
ORIGINAL = ROOT / "analysis/ml9_bayesian_irt/preregistration.json"


def test_ml9c_recovery_is_separately_frozen_and_pinned() -> None:
    payload = verify_recovery_preregistration(ROOT, RECOVERY)
    assert payload["artifact_id"] == "ml9c_identified_recovery_preregistration_v2"
    assert payload["frozen_before_recovery_fit"] is True
    assert payload["binary_rasch"]["posterior_change"] is False
    assert payload["continuous_beta"]["model_source"].endswith("unchanged")
    assert (
        payload["identified_factor_models"]["one_factor"]["positive_marker"]
        == CPU_FACTOR_ANCHOR
    )
    assert (
        payload["identified_factor_models"]["two_factor"]["ipie_axis_positive_marker"]
        == IPIE_FACTOR_ANCHOR
    )
    assert payload["exact_cross_validation"]["fold_count"] == 5
    assert payload["diagnostics"]["maximum_rhat"] == 1.01


def test_ml9c_recovery_source_handoff_is_unchanged() -> None:
    payload = json.loads(RECOVERY.read_text(encoding="utf-8"))
    source = ROOT / payload["retained_v1_evidence"]["binary_difficulty_handoff"]["path"]
    assert sha256_file(source) == payload["binary_rasch"]["required_handoff_sha256"]
    assert not (ROOT / "analysis/ml9_bayesian_irt/final_v1").exists()


def test_ml9c_recovery_folds_are_balanced_and_family_blocked() -> None:
    data = prepare_irt_data(ROOT, ORIGINAL)
    first = canonical_family_folds(data, 5, 20260801)
    second = canonical_family_folds(data, 5, 20260801)
    assert np.array_equal(first, second)
    assert [int((first == fold).sum()) for fold in range(5)] == [20, 19, 19, 19, 19]
    for family in set(data.task_families):
        indices = np.asarray(
            [index for index, value in enumerate(data.task_families) if value == family]
        )
        assert len(set(first[indices])) == 1


def test_ml9c_recovery_transform_fits_training_rows_only() -> None:
    data = prepare_irt_data(ROOT, ORIGINAL)
    training = np.arange(1, len(data.task_ids))
    transform = factor_transform(data.logit_quality, training)
    assert transform.standardized.shape == (96, 18)
    assert np.allclose(transform.standardized[training].mean(axis=0), 0.0, atol=1e-12)
    assert np.allclose(transform.standardized[training].std(axis=0, ddof=1), 1.0)
    perturbed = data.logit_quality.copy()
    perturbed[0] += 1000.0
    repeated = factor_transform(perturbed, training)
    assert np.array_equal(transform.mean, repeated.mean)
    assert np.array_equal(transform.scale, repeated.scale)


def test_ml9c_recovery_identified_model_constraints() -> None:
    data = prepare_irt_data(ROOT, ORIGINAL)
    transform = factor_transform(data.logit_quality, np.arange(96))
    cpu_index = data.variant_ids.index(CPU_FACTOR_ANCHOR)
    ipie_index = data.variant_ids.index(IPIE_FACTOR_ANCHOR)
    for factors in (1, 2):
        model = identified_factor_model(
            transform.standardized, data.variant_ids, data.task_ids, factors
        )
        assert np.isfinite(float(model.compile_logp()(model.initial_point())))
        assert model.named_vars["factor_loading"].eval().shape == (
            (18,) if factors == 1 else (18, 2)
        )
        if factors == 2:
            loading = model.named_vars["factor_loading"].eval()
            assert loading[cpu_index, 1] == 0.0
            assert loading[ipie_index, 0] == 0.0
