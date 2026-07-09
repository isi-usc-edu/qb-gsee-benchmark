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

import numpy as np
import pandas as pd

from qb_gsee_benchmark.features.df_features import (
    DF_DECAY_EXPONENT,
    DF_DECAY_NPOINTS,
    DF_DECAY_R2,
    DF_DECAY_REASON,
    DF_RANK_PER_ORBITAL,
    FEATURES_VERSION,
    ONE_NORM_PER_ORBITAL,
    add_df_feature_columns_to_record,
    enrich_hamiltonian_features_dataframe,
    df_feature_metadata_dataframe,
    fit_df_eig_decay,
    parse_df_eigs,
)


def test_parse_df_eigs_from_multiline_numpy_string():
    parsed = parse_df_eigs("[1.0e-08 2.5e-02\n ... 0.0 -1.0 nan 3.0]")

    assert np.allclose(parsed, [1.0e-08, 2.5e-02, 3.0])


def test_fit_df_eig_decay_power_law():
    ranks = np.arange(1, 65, dtype=float)
    eigs = ranks ** -2.0

    result = fit_df_eig_decay(eigs, tail_fraction=0.5, min_points=8)

    assert result[DF_DECAY_REASON] == "ok"
    assert np.isclose(result[DF_DECAY_EXPONENT], 2.0)
    assert np.isclose(result[DF_DECAY_R2], 1.0)
    assert result[DF_DECAY_NPOINTS] == 32


def test_fit_df_eig_decay_too_few_points():
    result = fit_df_eig_decay([1.0, 0.5, 0.25], min_points=8)

    assert np.isnan(result[DF_DECAY_EXPONENT])
    assert np.isnan(result[DF_DECAY_R2])
    assert result[DF_DECAY_NPOINTS] == 3
    assert result[DF_DECAY_REASON] == "too_few_positive_eigs"


def test_add_df_feature_columns_to_record():
    record = {
        "df_eigs": np.arange(1, 33, dtype=float) ** -1.5,
        "one_norm": 20.0,
        "df_rank": 16,
        "n_orbs": 4,
    }

    add_df_feature_columns_to_record(record)

    assert np.isclose(record[DF_DECAY_EXPONENT], 1.5)
    assert np.isclose(record[ONE_NORM_PER_ORBITAL], 5.0)
    assert np.isclose(record[DF_RANK_PER_ORBITAL], 4.0)
    assert record[FEATURES_VERSION] == "b2a_df_features_v1"


def test_enrich_hamiltonian_features_dataframe():
    df = pd.DataFrame(
        [
            {
                "df_eigs": "[1.0 0.5 0.25 0.125 0.0625 0.03125 0.015625 0.0078125]",
                "one_norm": 12.0,
                "df_rank": 8,
                "n_orbs": 4,
            }
        ]
    )

    enriched = enrich_hamiltonian_features_dataframe(df)

    assert DF_DECAY_EXPONENT in enriched.columns
    assert ONE_NORM_PER_ORBITAL in enriched.columns
    assert enriched.loc[0, ONE_NORM_PER_ORBITAL] == 3.0
    assert enriched.loc[0, DF_RANK_PER_ORBITAL] == 2.0


def test_df_feature_metadata_has_scaling_tags():
    metadata = df_feature_metadata_dataframe()

    assert set(metadata["feature"]) >= {
        DF_DECAY_EXPONENT,
        ONE_NORM_PER_ORBITAL,
        DF_RANK_PER_ORBITAL,
    }
    assert metadata.set_index("feature").loc[DF_DECAY_EXPONENT, "scaling_tag"] == "intensive"
    assert metadata.set_index("feature").loc[ONE_NORM_PER_ORBITAL, "scaling_tag"] == "intensive"
