# Copyright 2026.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0

"""Regression coverage for FCIDUMP one-body symmetrization."""

from pathlib import Path

import numpy as np
from pyscf.tools import fcidump

from qb_gsee_benchmark.utils import read_fcidump


FIXTURES = Path(__file__).resolve().parent


def test_already_symmetric_h1_is_byte_identical():
    path = FIXTURES / "fcidump.h2_sto-3g"
    raw_h1 = fcidump.read(str(path), verbose=False)["H1"]
    normalized_h1 = read_fcidump(str(path))["H1"]

    assert raw_h1.dtype == normalized_h1.dtype
    assert raw_h1.shape == normalized_h1.shape
    assert raw_h1.tobytes() == normalized_h1.tobytes()


def test_benzene_mixed_triangle_h1_loads_correctly():
    """Exercise exact H1 entries from the released asymmetric benzene dump.

    The fixture maps source orbitals 1, 4, and 8 to 1, 2, and 3. Its values
    come from the released source FCIDUMP with SHA-256
    8ac25808d1cac9ab15edb79c4e69c6cd0aef585d412094541c7cf136d0886b3e.
    """

    path = FIXTURES / "fcidump.benzene_h1_mixed_triangle"
    raw_h1 = fcidump.read(str(path), verbose=False)["H1"]
    assert np.max(np.abs(raw_h1 - raw_h1.T)) == 0.228543156227

    normalized_h1 = read_fcidump(str(path))["H1"]
    expected = np.array(
        [
            [-9.604953425246, 0.228543156227, -0.01826612488529],
            [0.228543156227, -9.596482822317, 0.0],
            [-0.01826612488529, 0.0, -9.605671630884],
        ]
    )
    np.testing.assert_array_equal(normalized_h1, expected)
    np.testing.assert_array_equal(normalized_h1, normalized_h1.T)
