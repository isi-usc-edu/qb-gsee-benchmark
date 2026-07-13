import numpy as np

from qb_gsee_benchmark.features.mfproto_mp2 import (
    _denominator_features,
    _natural_occupation_features,
)


class _OutOfRangeMP2:
    def make_rdm1(self, *, t2):
        del t2
        return np.diag([2.0 + 4.0e-8, -4.0e-8])


def test_all_denominators_below_threshold_fail_closed() -> None:
    denominators = [np.array([5.0e-7, -9.0e-7])]
    masks = [np.array([True, True])]
    features = _denominator_features(denominators, masks)

    assert features["mp2_denominator_applicable"] is False
    assert features["mp2_denominator_reason"] == "all_denominators_below_threshold"
    assert features["mp2_denominator_masked_fraction"] == 1.0
    assert features["mp2_denominator_p50_hartree"] is None
    assert features["mp2_denominator_inverse_first_moment"] is None


def test_natural_occupation_out_of_range_fail_closed() -> None:
    features = _natural_occupation_features(_OutOfRangeMP2(), object(), nelec=2)

    assert features["mp2_natural_occupation_applicable"] is False
    assert (
        features["mp2_natural_occupation_reason"]
        == "natural_occupation_out_of_range"
    )
    assert features["mp2_natural_occupation_clipped_count"] is None
    assert features["mp2_natural_entropy"] is None
    assert features["mp2_natural_active_fraction"] is None
