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

from qb_gsee_benchmark.features.structure_features import (
    EDGE_ORDER_COEFFICIENT_OF_VARIATION,
    MAX_VERTEX_DEGREE_PER_ORBITAL,
    MEAN_VERTEX_DEGREE_PER_ORBITAL,
    ONE_NORM_PER_PAULI_TERM,
    PAULI_TERMS_PER_ORBITAL_QUARTIC,
    STRUCTURE_PROXY_FEATURE_COLUMNS,
    STRUCTURE_PROXY_VERSION,
    STRUCTURE_PROXY_VERSION_COLUMN,
    VERTEX_DEGREE_COEFFICIENT_OF_VARIATION,
    add_structure_proxy_columns_to_record,
    build_structure_proxy_category_coverage,
    enrich_hamiltonian_features_with_structure_proxies,
    structure_proxy_coverage,
    structure_proxy_metadata_dataframe,
)


def example_record():
    return {
        "n_orbs": 4,
        "number_of_terms": 256,
        "one_norm": 128.0,
        "mean_vertex_degree": 8.0,
        "max_vertex_degree": 16.0,
        "std_dev_vertex_degree": 2.0,
        "mean_edge_order": 4.0,
        "std_dev_edge_order": 1.0,
    }


def test_add_structure_proxy_columns_to_record():
    record = example_record()

    add_structure_proxy_columns_to_record(record)

    assert np.isclose(record[PAULI_TERMS_PER_ORBITAL_QUARTIC], 1.0)
    assert np.isclose(record[ONE_NORM_PER_PAULI_TERM], 0.5)
    assert np.isclose(record[MEAN_VERTEX_DEGREE_PER_ORBITAL], 2.0)
    assert np.isclose(record[MAX_VERTEX_DEGREE_PER_ORBITAL], 4.0)
    assert np.isclose(record[VERTEX_DEGREE_COEFFICIENT_OF_VARIATION], 0.25)
    assert np.isclose(record[EDGE_ORDER_COEFFICIENT_OF_VARIATION], 0.25)
    assert record[STRUCTURE_PROXY_VERSION_COLUMN] == STRUCTURE_PROXY_VERSION


def test_enrich_handles_zero_denominators_as_nan():
    df = pd.DataFrame(
        [
            {
                "n_orbs": 0,
                "number_of_terms": 0,
                "one_norm": 12.0,
                "mean_vertex_degree": 0.0,
                "max_vertex_degree": 5.0,
                "std_dev_vertex_degree": 1.0,
                "mean_edge_order": 0.0,
                "std_dev_edge_order": 1.0,
            }
        ]
    )

    enriched = enrich_hamiltonian_features_with_structure_proxies(df)

    for feature in STRUCTURE_PROXY_FEATURE_COLUMNS:
        assert np.isnan(enriched.loc[0, feature])


def test_structure_proxy_metadata_has_scaling_tags_and_representation():
    metadata = structure_proxy_metadata_dataframe().set_index("feature")

    assert metadata.loc[PAULI_TERMS_PER_ORBITAL_QUARTIC, "scaling_tag"] == "intensive"
    assert metadata.loc[PAULI_TERMS_PER_ORBITAL_QUARTIC, "representation"] == "qubit_pauli_proxy"
    assert metadata.loc[MEAN_VERTEX_DEGREE_PER_ORBITAL, "representation"] == "interaction_hypergraph_proxy"


def test_structure_proxy_coverage_and_category_coverage():
    df = pd.DataFrame(
        [
            {**example_record(), "category": "small"},
            {**example_record(), "number_of_terms": 0, "category": "large"},
        ]
    )
    enriched = enrich_hamiltonian_features_with_structure_proxies(df)

    coverage = structure_proxy_coverage(enriched).set_index("feature")
    category = build_structure_proxy_category_coverage(enriched).set_index(["feature", "category"])

    assert coverage.loc[PAULI_TERMS_PER_ORBITAL_QUARTIC, "present_tasks"] == 2
    assert coverage.loc[ONE_NORM_PER_PAULI_TERM, "present_tasks"] == 1
    assert category.loc[(ONE_NORM_PER_PAULI_TERM, "large"), "missing_tasks"] == 1
