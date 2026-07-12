import numpy as np
import pytest

from qb_gsee_benchmark.features.fcidump_sparse import SparseFcidump
from qb_gsee_benchmark.features.mfproto_features import run_mean_field
from qb_gsee_benchmark.features.mfproto_stability import (
    lowest_davidson_root,
    run_stability,
    stability_feature_values,
)


def _noninteracting_data(norb=2, nelec=2, ms2=0) -> SparseFcidump:
    return SparseFcidump(
        norb=norb,
        nelec=nelec,
        ms2=ms2,
        h1=np.diag(np.linspace(-1.0, 1.0, norb)),
        eri_records={},
        ecore=0.0,
        one_body_duplicate_orientations=0,
        one_body_duplicate_max_abs_difference=0.0,
        one_body_duplicate_max_rel_difference=0.0,
        one_body_symmetry_conflict_records=0,
        two_body_input_records=0,
        two_body_duplicate_orientations=0,
        two_body_duplicate_max_abs_difference=0.0,
        two_body_duplicate_max_rel_difference=0.0,
        two_body_symmetry_conflict_records=0,
        container_format="plain",
        container_member=None,
        ms2_source="test",
    )


def test_davidson_root_uses_lowest_eigenpair_and_normalizes_vector() -> None:
    matrix = np.array([[3.0, 0.2, 0.0], [0.2, -0.5, 0.1], [0.0, 0.1, 1.0]])
    root = lowest_davidson_root(lambda vector: matrix @ vector, np.diag(matrix))
    expected = np.linalg.eigvalsh(matrix)[0]
    assert root.applicable
    assert root.eigenvalue == pytest.approx(expected, abs=1e-12)
    assert np.linalg.norm(root.vector) == pytest.approx(1.0, abs=1e-14)
    assert root.dimension == 3


def test_external_dimension_ceiling_masks_before_hessian_action() -> None:
    called = False

    def hop(vector):
        nonlocal called
        called = True
        return vector

    root = lowest_davidson_root(hop, np.arange(5.0), dimension_ceiling=4)
    assert not root.applicable
    assert root.reason == "external_dimension_ceiling"
    assert not called


def test_noninteracting_selected_state_is_stable_without_following() -> None:
    data = _noninteracting_data()
    mean_field = run_mean_field(data)
    stability = run_stability(data, data.dense_eri(), mean_field.selected)
    assert stability.internal_roots[0].applicable
    assert stability.internal_roots[0].eigenvalue > 0.0
    assert stability.follow_outcomes == []
    assert stability.final_branch is mean_field.selected
    features = stability_feature_values(stability)
    assert features["mf_stability_internal_marginal"] is False
    assert features["mf_stability_external_applicable"] is True
    assert features["mf_stability_external_dimension"] == 1
