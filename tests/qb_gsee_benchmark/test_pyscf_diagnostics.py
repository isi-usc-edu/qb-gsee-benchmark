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

import json

import numpy as np
import pandas as pd

from qb_gsee_benchmark.features.pyscf_diagnostics import (
    CCSD_D1_DIAGNOSTIC,
    CCSD_MAX_T2,
    CCSD_T1_DIAGNOSTIC,
    HOMO_LUMO_GAP,
    MP2_CORR_ENERGY,
    MP2_CORR_ENERGY_PER_ELECTRON,
    PYSCF_DIAGNOSTICS_VERSION,
    PYSCF_DIAGNOSTICS_VERSION_COLUMN,
    UHF_S2,
    build_pyscf_feature_category_coverage,
    enrich_hamiltonian_features_with_pyscf_diagnostics,
    find_numeric_detail,
    load_pyscf_solution_directory,
    normalize_method_name,
)


def _write_solution(solution_dir, method, task_rows):
    payload = {
        "problem_instance_uuid": "problem-1",
        "solution_uuid": f"solution-{method}",
        "solver_details": {"solver_short_name": method},
        "solution_data": task_rows,
    }
    safe_method = method.replace("(", "_").replace(")", "")
    path = solution_dir / f"solution.{safe_method}.json"
    path.write_text(json.dumps(payload))
    return path


def _task_row(task_uuid, energy, details=None):
    return {
        "task_uuid": task_uuid,
        "energy": energy,
        "energy_units": "hartree",
        "run_time": {"overall_time": {"seconds": 1.5}},
        "run_time_cpu": {"overall_time": {"seconds": 2.5}},
        "solution_details": details or {},
    }


def test_normalize_method_name():
    assert normalize_method_name("HF") == "hf"
    assert normalize_method_name("CCSD(T)") == "ccsd_t"
    assert normalize_method_name("UHF") == "hf"


def test_find_numeric_detail_requires_matching_key():
    details = {"unrelated": 999.0, "nested": {"homo_lumo_gap": {"value": 0.42}}}

    assert find_numeric_detail(details, {"homo_lumo_gap"}) == 0.42
    assert find_numeric_detail({"unrelated": 999.0}, {"homo_lumo_gap"}) is None


def test_enrich_pyscf_diagnostics_when_details_present(tmp_path):
    _write_solution(
        tmp_path,
        "HF",
        [
            _task_row(
                "task-1",
                -1.00,
                {
                    "orbitals": {"HOMO-LUMO gap": {"value": 0.25}},
                    "spin_squared": "0.75",
                },
            )
        ],
    )
    _write_solution(tmp_path, "MP2", [_task_row("task-1", -1.08)])
    _write_solution(
        tmp_path,
        "CCSD",
        [
            _task_row(
                "task-1",
                -1.10,
                {
                    "diagnostics": {
                        "t1_diagnostic": 0.012,
                        "d1_diagnostic": 0.03,
                        "max_abs_t2": {"value": 0.20},
                    }
                },
            )
        ],
    )
    features = pd.DataFrame(
        [{"task_uuid": "task-1", "n_elec": 4, "problem_instance_short_name": "h2_0"}]
    )

    solution_rows = load_pyscf_solution_directory(tmp_path)
    enriched = enrich_hamiltonian_features_with_pyscf_diagnostics(
        features,
        solution_rows=solution_rows,
    )
    row = enriched.iloc[0]

    assert np.isclose(row[MP2_CORR_ENERGY], -0.08)
    assert np.isclose(row[MP2_CORR_ENERGY_PER_ELECTRON], -0.02)
    assert np.isclose(row[HOMO_LUMO_GAP], 0.25)
    assert np.isclose(row[UHF_S2], 0.75)
    assert np.isclose(row[CCSD_T1_DIAGNOSTIC], 0.012)
    assert np.isclose(row[CCSD_D1_DIAGNOSTIC], 0.03)
    assert np.isclose(row[CCSD_MAX_T2], 0.20)
    assert row[f"{HOMO_LUMO_GAP}_reason"] == "ok"
    assert row[PYSCF_DIAGNOSTICS_VERSION_COLUMN] == PYSCF_DIAGNOSTICS_VERSION


def test_enrich_pyscf_diagnostics_missing_values_have_reasons(tmp_path):
    _write_solution(tmp_path, "HF", [_task_row("task-1", -1.00)])
    features = pd.DataFrame(
        [{"task_uuid": "task-1", "n_elec": 2, "problem_instance_short_name": "h2_0"}]
    )

    enriched = enrich_hamiltonian_features_with_pyscf_diagnostics(
        features,
        solution_dir=tmp_path,
    )
    row = enriched.iloc[0]

    assert np.isnan(row[MP2_CORR_ENERGY])
    assert row[f"{MP2_CORR_ENERGY}_reason"] == "missing_mp2_solution"
    assert np.isnan(row[HOMO_LUMO_GAP])
    assert row[f"{HOMO_LUMO_GAP}_reason"] == "not_present_in_solution_json"
    assert np.isnan(row[CCSD_T1_DIAGNOSTIC])
    assert row[f"{CCSD_T1_DIAGNOSTIC}_reason"] == "missing_ccsd_solution"


def test_build_pyscf_feature_category_coverage():
    enriched = pd.DataFrame(
        [
            {"category": "small", HOMO_LUMO_GAP: 0.1, f"{HOMO_LUMO_GAP}_reason": "ok"},
            {
                "category": "small",
                HOMO_LUMO_GAP: np.nan,
                f"{HOMO_LUMO_GAP}_reason": "not_present_in_solution_json",
            },
        ]
    )
    for feature in [
        UHF_S2,
        MP2_CORR_ENERGY,
        MP2_CORR_ENERGY_PER_ELECTRON,
        CCSD_T1_DIAGNOSTIC,
        CCSD_D1_DIAGNOSTIC,
        CCSD_MAX_T2,
    ]:
        enriched[feature] = np.nan
        enriched[f"{feature}_reason"] = "not_present_in_solution_json"

    coverage = build_pyscf_feature_category_coverage(enriched)
    gap_row = coverage[
        (coverage["feature"] == HOMO_LUMO_GAP)
        & (coverage["category"] == "small")
    ].iloc[0]

    assert gap_row["present_tasks"] == 1
    assert gap_row["total_tasks"] == 2
    assert np.isclose(gap_row["coverage_fraction"], 0.5)
