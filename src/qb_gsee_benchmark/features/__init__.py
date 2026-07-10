# Copyright 2026.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Feature post-processing helpers for QB-GSEE benchmark data."""

from .fragment_features import (
    FRAGMENT_FEATURE_COLUMNS,
    compute_fragment_features,
    infer_equal_size_fragment_partition,
)
from .pair_structure_features import (
    PAIR_STRUCTURE_FEATURE_COLUMNS,
    compute_pair_structure_features,
)
from .representation_features import (
    REPRESENTATION_FEATURE_COLUMNS,
    compute_representation_features,
)
from .sign_free_features import (
    SIGN_FREE_FEATURE_COLUMNS,
    detect_hubbard_task,
    detect_sign_free_features,
)

__all__ = [
    "FRAGMENT_FEATURE_COLUMNS",
    "PAIR_STRUCTURE_FEATURE_COLUMNS",
    "REPRESENTATION_FEATURE_COLUMNS",
    "SIGN_FREE_FEATURE_COLUMNS",
    "compute_fragment_features",
    "compute_pair_structure_features",
    "compute_representation_features",
    "detect_hubbard_task",
    "detect_sign_free_features",
    "infer_equal_size_fragment_partition",
]
