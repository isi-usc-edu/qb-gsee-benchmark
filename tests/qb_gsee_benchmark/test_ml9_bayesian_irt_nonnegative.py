from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pymc as pm

from qb_gsee_benchmark.ml.bayesian_irt_nonnegative import nonnegative_factor_model
from qb_gsee_benchmark.ml.bayesian_irt_recovery import (
    factor_transform,
    verify_recovery_preregistration,
)
from qb_gsee_benchmark.ml.bayesian_irt_run import prepare_irt_data


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml9_bayesian_irt/recovery_preregistration_v3.json"


def test_ml9c_v3_preregistration_is_frozen_and_pinned() -> None:
    payload = verify_recovery_preregistration(ROOT, PREREGISTRATION)
    assert payload["artifact_id"] == "ml9c_nonnegative_recovery_preregistration_v3"
    assert payload["frozen_before_recovery_fit"] is True
    assert (
        payload["identified_factor_models"]["loading_sign_constraint"]
        == "all_free_loading_elements_are_nonnegative"
    )
    sampling = payload["exact_cross_validation"]["fit_sampling"]
    assert (sampling["tune"], sampling["draws"], sampling["target_accept"]) == (
        2000,
        2000,
        0.99,
    )
    assert not (ROOT / "analysis/ml9_bayesian_irt/final_v1").exists()


def test_ml9c_v3_factor_graph_is_nonnegative_with_pure_markers() -> None:
    payload = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    data = prepare_irt_data(ROOT, ROOT / payload["original_preregistration"]["path"])
    training = np.arange(12)
    transform = factor_transform(data.logit_quality, training)
    model = nonnegative_factor_model(
        transform.standardized[training],
        data.variant_ids,
        tuple(data.task_ids[index] for index in training),
        factors=2,
    )
    with model:
        prior = pm.sample_prior_predictive(draws=5, random_seed=20260801)
    loading = np.asarray(prior.prior["factor_loading"])
    assert loading.shape == (1, 5, 18, 2)
    assert np.all(loading >= 0.0)
    cpu_anchor = data.variant_ids.index("g50_bond_dimension_2048")
    ipie_anchor = data.variant_ids.index("uhf_trial_512_walkers_1000_blocks")
    assert np.all(loading[..., cpu_anchor, 1] == 0.0)
    assert np.all(loading[..., ipie_anchor, 0] == 0.0)
