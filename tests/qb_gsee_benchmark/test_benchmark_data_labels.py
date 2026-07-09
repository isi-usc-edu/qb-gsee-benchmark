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

import pytest

from qb_gsee_benchmark.benchmark_data import (
    canonical_problem_family,
    problem_instance_category_by_short_name,
    solver_outcome,
)


@pytest.mark.parametrize(
    "short_name, expected_family",
    [
        ("cl2_0", "cl2"),
        ("blue_dimer", "blue_dimer"),
        ("Fe_0", "Fe"),
        ("Fe_1", "Fe"),
        ("FeO_0", "Fe"),
        ("CuO_0", "Cu"),
        ("planted_solution_0007", "planted_solution"),
    ],
)
def test_canonical_problem_family(short_name, expected_family):
    assert canonical_problem_family(short_name) == expected_family


@pytest.mark.parametrize(
    "attempted, solved_accuracy, solved_runtime, expected_outcome",
    [
        (False, False, False, "not-attempted"),
        (True, True, True, "solved"),
        (True, False, True, "failed-accuracy"),
        (True, False, False, "failed-accuracy"),
        (True, True, False, "failed-runtime"),
    ],
)
def test_solver_outcome(attempted, solved_accuracy, solved_runtime, expected_outcome):
    assert solver_outcome(attempted, solved_accuracy, solved_runtime) == expected_outcome


def test_problem_instance_category_by_short_name(tmp_path):
    category_dir = tmp_path / "transition_metals"
    category_dir.mkdir()
    problem_instance_path = category_dir / "problem_instance.Fe_0.example.json"
    problem_instance_path.write_text(json.dumps({"short_name": "Fe_0"}))

    mapping = problem_instance_category_by_short_name(str(tmp_path))

    assert mapping == {"Fe_0": "transition_metals"}


def test_calculate_solver_success_labels_adds_b1_columns():
    from qb_gsee_benchmark.benchmark_data import BenchmarkData
    import pandas as pd

    benchmark_data = object.__new__(BenchmarkData)
    benchmark_data.hamiltonian_features = pd.DataFrame(
        [
            {"task_uuid": "task-1", "n_orbs": 8},
            {"task_uuid": "task-test", "n_orbs": 2},
        ]
    )
    benchmark_data.solvers_df = pd.DataFrame(
        [
            {"solver_short_name": "NoAttempt", "solver_uuid": "solver-no"},
            {"solver_short_name": "Accurate", "solver_uuid": "solver-yes"},
        ]
    )
    benchmark_data.problem_instance_category_by_short_name = {"FeO_0": "transition_metals"}
    benchmark_data.problem_instance_list = [
        {
            "problem_instance_uuid": "instance-1",
            "short_name": "FeO_0",
            "calendar_due_date": None,
            "tasks": [
                {
                    "task_uuid": "task-1",
                    "reference_provenance_grade": "exact",
                    "curation_tier": "expanded",
                    "reference_independence_from_solvers": True,
                    "model_hamiltonian_downfolded": False,
                    "source_defect_documented": False,
                    "requirements": {
                        "time_limit_seconds": 100,
                        "absolute_accuracy_threshold": 0.001,
                        "reference_energy": -1.0,
                        "reference_energy_source": "https://example.test/ref",
                        "reference_energy_method": "example exact diagonalization",
                        "reference_energy_provenance": "exact",
                        "reference_energy_cross_validation_methods": ["ED"],
                        "reference_energy_independent_of_shci_family": True,
                        "reference_energy_note": "synthetic fixture reference",
                    },
                    "supporting_files": [
                        {
                            "instance_data_object_uuid": "data-1",
                            "instance_data_object_url": "sftp://example/fcidump.test.gz",
                        }
                    ],
                },
                {
                    "task_uuid": "task-test",
                    "reference_provenance_grade": "exact",
                    "curation_tier": "test",
                    "reference_independence_from_solvers": True,
                    "model_hamiltonian_downfolded": False,
                    "source_defect_documented": False,
                    "requirements": {
                        "time_limit_seconds": 100,
                        "absolute_accuracy_threshold": 0.001,
                        "reference_energy": -2.0,
                        "reference_energy_source": "https://example.test/ref-test",
                        "reference_energy_method": "example exact diagonalization",
                        "reference_energy_provenance": "exact",
                        "reference_energy_independent_of_shci_family": True,
                    },
                    "supporting_files": [
                        {
                            "instance_data_object_uuid": "data-test",
                            "instance_data_object_url": "sftp://example/fcidump.test-tier.gz",
                        }
                    ],
                },
            ],
        }
    ]
    benchmark_data.solution_list = [
        {
            "solution_uuid": "solution-yes",
            "is_resource_estimate": False,
        }
    ]

    def locate_solution_results_by_task_uuid_and_solver_uuid(solver_uuid, task_uuid):
        if solver_uuid == "solver-yes" and task_uuid == "task-1":
            return {
                "run_time": {"overall_time": {"seconds": 10}},
                "energy": -1.0001,
            }, "solution-yes"
        return None, None

    benchmark_data.locate_solution_results_by_task_uuid_and_solver_uuid = (
        locate_solution_results_by_task_uuid_and_solver_uuid
    )

    labels = benchmark_data.calculate_solver_success_labels()

    assert set(labels["task_uuid"]) == {"task-1"}
    assert {
        "family",
        "category",
        "outcome",
        "reference_provenance_grade",
        "curation_tier",
        "reference_independence_from_solvers",
        "model_hamiltonian_downfolded",
        "source_defect_documented",
        "planting_mechanism",
    }.issubset(labels.columns)

    not_attempted = labels[labels["solver_uuid"] == "solver-no"].iloc[0]
    assert not_attempted["family"] == "Fe"
    assert not_attempted["category"] == "transition_metals"
    assert not_attempted["attempted"] is False
    assert not_attempted["outcome"] == "not-attempted"
    assert not_attempted["label"] is False

    solved = labels[labels["solver_uuid"] == "solver-yes"].iloc[0]
    assert solved["attempted"] is True
    assert solved["solved_within_run_time"] is True
    assert solved["solved_within_accuracy_requirement"] is True
    assert solved["outcome"] == "solved"
    assert solved["label"] is True
    assert solved["reference_energy_source"] == "https://example.test/ref"
    assert solved["reference_energy_method"] == "example exact diagonalization"
    assert solved["reference_energy_provenance"] == "exact"
    assert solved["reference_energy_cross_validation_methods"] == ["ED"]
    assert solved["reference_energy_independent_of_shci_family"] is True
    assert solved["reference_energy_note"] == "synthetic fixture reference"
    assert solved["reference_provenance_grade"] == "exact"
    assert solved["curation_tier"] == "expanded"
    assert solved["reference_independence_from_solvers"] is True
    assert solved["model_hamiltonian_downfolded"] is False
    assert solved["source_defect_documented"] is False


def test_write_data_for_bubble_ml_gui_excludes_test_tier_tasks(tmp_path):
    from qb_gsee_benchmark.benchmark_data import BenchmarkData
    import pandas as pd

    benchmark_data = object.__new__(BenchmarkData)
    benchmark_data.hamiltonian_features = pd.DataFrame(
        [
            {"task_uuid": "task-1", "n_orbs": 8, "df_eigs": "[1.0]"},
            {"task_uuid": "task-test", "n_orbs": 2, "df_eigs": "[2.0]"},
        ]
    )
    benchmark_data.problem_instance_list = [
        {
            "tasks": [
                {"task_uuid": "task-1", "curation_tier": "expanded"},
                {"task_uuid": "task-test", "curation_tier": "test"},
            ]
        }
    ]
    benchmark_data.solvers_dict = {
        "solver-yes": {"solver_short_name": "Accurate"},
    }
    benchmark_data.aggregated_solver_labels_df = pd.DataFrame(
        [
            {"solver_uuid": "solver-yes", "task_uuid": "task-1", "label": True},
        ]
    )

    benchmark_data.write_data_for_bubble_ml_gui(output_directory=str(tmp_path))

    assert set(benchmark_data.data_for_bubble_ml_df["task_uuid"]) == {"task-1"}
    assert "df_eigs" not in benchmark_data.data_for_bubble_ml_df.columns
    written = pd.read_csv(tmp_path / "data_for_BubbleML.csv")
    assert set(written["task_uuid"]) == {"task-1"}
