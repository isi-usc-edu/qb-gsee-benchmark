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

import pandas as pd

from qb_gsee_benchmark.qre_coverage import (
    add_task_metadata,
    coverage_by_category,
    coverage_by_solver,
    hardware_assumption_table,
    load_qre_solution_file,
    missing_thc_instances,
    qre_representation,
    task_coverage_matrix,
)


def _write_qre_solution(path, solver_short_name="THC_QPE_1mHa"):
    payload = {
        "is_resource_estimate": True,
        "problem_instance_uuid": "problem-1",
        "solution_uuid": "solution-1",
        "solver_details": {
            "solver_uuid": "solver-1",
            "solver_short_name": solver_short_name,
            "quantum_hardware_details": {
                "quantum_hardware_description": "test hardware",
                "quantum_hardware_parameters": {
                    "physical_error_rate": 0.001,
                    "cycle_time_microseconds": 1,
                    "num_factories": 4,
                    "parallelize_shots": False,
                },
            },
            "algorithm_details": {
                "algorithm_description": "test algorithm",
                "algorithm_parameters": {"df_threshold": 0.001, "max_orbitals": 70},
            },
        },
        "solution_data": [
            {
                "task_uuid": "task-1",
                "confidence_level": 0.99,
                "error_bound": 0.001,
                "quantum_resources": {
                    "logical": {
                        "num_logical_qubits": 10,
                        "num_T_gates_per_shot": 100,
                        "num_shots": 2,
                    },
                    "physical": {"num_physical_qubits": 1000, "data_code_distance": 11},
                },
                "run_time": {
                    "preprocessing_time": {"seconds": 5},
                    "algorithm_run_time": {"seconds": 10},
                    "overall_time": {"seconds": 15},
                },
                "solution_details": {
                    "overlap": 0.5,
                    "decomposition_l1_norm_hartree": 1.2,
                    "thc_rank": 7,
                },
            }
        ],
    }
    path.write_text(json.dumps(payload))


def _current_tasks():
    return pd.DataFrame(
        [
            {
                "task_uuid": "task-1",
                "problem_instance_uuid": "problem-1",
                "problem_instance_short_name": "h2_0",
                "category": "small_molecules",
                "family": "h2",
                "n_elec": 2,
                "n_orbs": 4,
            },
            {
                "task_uuid": "task-2",
                "problem_instance_uuid": "problem-2",
                "problem_instance_short_name": "f2_0",
                "category": "small_molecules",
                "family": "f2",
                "n_elec": 18,
                "n_orbs": 28,
            },
        ]
    )


def test_qre_representation_labels():
    assert qre_representation("DF_QPE") == "DF_QPE"
    assert qre_representation("THC_QPE_1mHa") == "THC_QPE"
    assert qre_representation("THC_BLISS_QPE_1mHa") == "THC_BLISS_QPE"
    assert qre_representation("TopQAD-D") == "TOPQAD"


def test_load_qre_solution_file_flattens_resources(tmp_path):
    path = tmp_path / "solution.json"
    _write_qre_solution(path)

    rows = load_qre_solution_file(path, solution_root=tmp_path)

    assert len(rows) == 1
    row = rows[0]
    assert row["representation"] == "THC_QPE"
    assert row["task_uuid"] == "task-1"
    assert row["num_logical_qubits"] == 10
    assert row["num_T_gates_per_shot"] == 100
    assert row["num_physical_qubits"] == 1000
    assert row["overall_time_seconds"] == 15
    assert row["decomposition_l1_norm_hartree"] == 1.2
    assert row["thc_rank"] == 7


def test_qre_coverage_tables(tmp_path):
    path = tmp_path / "solution.json"
    _write_qre_solution(path)
    qre_rows = pd.DataFrame(load_qre_solution_file(path, solution_root=tmp_path))
    current = _current_tasks()
    enriched = add_task_metadata(qre_rows, current)

    coverage = task_coverage_matrix(current, enriched)
    by_solver = coverage_by_solver(current, enriched)
    by_category = coverage_by_category(coverage)
    missing = missing_thc_instances(coverage)
    hardware = hardware_assumption_table(enriched)

    assert bool(coverage.set_index("task_uuid").loc["task-1", "has_thc_qpe"])
    assert not bool(coverage.set_index("task_uuid").loc["task-2", "has_thc_qpe"])
    assert by_solver.iloc[0]["current_tasks_covered"] == 1
    assert by_solver.iloc[0]["current_tasks_total"] == 2
    assert by_category[by_category["coverage_column"] == "has_thc_qpe"].iloc[0]["tasks_covered"] == 1
    assert missing.set_index("problem_instance_short_name").loc["f2_0", "needs_thc_qre"]
    assert hardware.iloc[0]["physical_error_rate"] == 0.001
