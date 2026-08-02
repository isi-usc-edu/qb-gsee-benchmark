from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from qb_gsee_benchmark.ml.bayesian_irt_recovery import canonical_family_folds
from qb_gsee_benchmark.ml.pyscf_sparse_irt import (
    CPU_MARKER,
    SECOND_MARKER,
    prepare_sparse_irt_data,
    sparse_factor_model,
    sparse_factor_transform,
    sparse_response_model,
)


ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = ROOT / "analysis/ml10_pyscf_hardness/preregistration.json"


def test_ml10c_sparse_response_census_and_missingness() -> None:
    data = prepare_sparse_irt_data(ROOT, PREREGISTRATION)
    assert len(data.task_ids) == 96
    assert len(data.item_ids) == 23
    assert len(data.binary) == 96 * 18 + 357
    assert len(data.response_rows) == 96 * 23
    assert int(data.response_rows["response_observed"].sum()) == len(data.binary)
    assert tuple(data.item_ids[-5:]) == (
        "pyscf_hf", "pyscf_mp2", "pyscf_cisd", "pyscf_ccsd", "pyscf_ccsd_t"
    )
    assert set(data.solver_groups) == {"dmrg", "ipie_afqmc", "shci", "trimci", "pyscf_methods"}


def test_ml10c_folds_are_exact_and_family_blocked() -> None:
    data = prepare_sparse_irt_data(ROOT, PREREGISTRATION)
    first = canonical_family_folds(data, 5, 20260802)
    second = canonical_family_folds(data, 5, 20260802)
    assert np.array_equal(first, second)
    assert sorted(int(np.sum(first == fold)) for fold in range(5)) == [19, 19, 19, 19, 20]
    for family in set(data.task_families):
        indices = np.flatnonzero(np.asarray(data.task_families) == family)
        assert len(set(first[indices])) == 1


def test_ml10c_transform_uses_observed_training_cells_only() -> None:
    data = prepare_sparse_irt_data(ROOT, PREREGISTRATION)
    training = np.arange(1, 96)
    transform = sparse_factor_transform(data, training)
    changed = data.logit_quality.copy()
    changed[data.observation_task_index == 0] += 1000.0
    repeated = sparse_factor_transform(replace(data, logit_quality=changed), training)
    assert np.array_equal(transform.mean, repeated.mean)
    assert np.array_equal(transform.scale, repeated.scale)
    assert np.isfinite(transform.standardized[data.observation_task_index, data.observation_item_index]).all()


def test_ml10c_models_compile_and_markers_are_pure() -> None:
    data = prepare_sparse_irt_data(ROOT, PREREGISTRATION)
    binary = sparse_response_model(data, continuous=False)
    assert np.isfinite(float(binary.compile_logp()(binary.initial_point())))
    transform = sparse_factor_transform(data, np.arange(96))
    model = sparse_factor_model(transform.standardized, data.item_ids, data.task_ids, np.arange(96), 2)
    assert np.isfinite(float(model.compile_logp()(model.initial_point())))
    loading = model.named_vars["factor_loading"].eval()
    assert loading.shape == (23, 2)
    assert loading[data.item_ids.index(CPU_MARKER), 1] == 0.0
    assert loading[data.item_ids.index(SECOND_MARKER), 0] == 0.0


def test_ml10c_new_sources_avoid_prohibited_term() -> None:
    prohibited = "lega" + "cy"
    paths = [
        ROOT / "src/qb_gsee_benchmark/ml/pyscf_sparse_irt.py",
        ROOT / "src/qb_gsee_benchmark/ml/pyscf_sparse_irt_fit.py",
        ROOT / "src/qb_gsee_benchmark/ml/pyscf_sparse_irt_artifacts.py",
        ROOT / "analysis/ml10_bayesian_irt/run_finalization.py",
        ROOT / "analysis/ml10_bayesian_irt/verify_two_runs.py",
        ROOT / "pbs/ml10c_sparse_irt_v1.pbs",
    ]
    for path in paths:
        assert prohibited not in path.read_text(encoding="utf-8").lower()
