import pandas as pd

from qb_gsee_benchmark.benchmark_data import BenchmarkData


def taxonomy_fixture() -> BenchmarkData:
    benchmark_data = object.__new__(BenchmarkData)
    benchmark_data.hamiltonian_features = pd.DataFrame(
        [
            {"task_uuid": "task-expanded", "n_orbs": 4, "df_eigs": "[1.0]"},
            {"task_uuid": "task-test", "n_orbs": 2, "df_eigs": "[2.0]"},
        ]
    )
    benchmark_data.solvers_df = pd.DataFrame(
        [{"solver_short_name": "NoAttempt", "solver_uuid": "solver-no"}]
    )
    benchmark_data.solvers_dict = {"solver-no": {"solver_short_name": "NoAttempt"}}
    benchmark_data.problem_instance_category_by_short_name = {
        "fixture": "validation_instances"
    }
    benchmark_data.problem_instance_list = [
        {
            "problem_instance_uuid": "instance-1",
            "short_name": "fixture",
            "calendar_due_date": None,
            "tasks": [
                {
                    "task_uuid": "task-expanded",
                    "reference_provenance_grade": "exact",
                    "curation_tier": "expanded",
                    "reference_independence_from_solvers": True,
                    "model_hamiltonian_downfolded": False,
                    "source_defect_documented": False,
                    "requirements": {
                        "time_limit_seconds": 100,
                        "absolute_accuracy_threshold": 0.001,
                        "reference_energy": -1.0,
                    },
                    "supporting_files": [
                        {
                            "instance_data_object_uuid": "data-expanded",
                            "instance_data_object_url": "https://example.test/fcidump.expanded.gz",
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
                    },
                    "supporting_files": [
                        {
                            "instance_data_object_uuid": "data-test",
                            "instance_data_object_url": "https://example.test/fcidump.test.gz",
                        }
                    ],
                },
            ],
        }
    ]
    benchmark_data.solution_list = []

    def no_solution(solver_uuid: str, task_uuid: str):
        del solver_uuid, task_uuid
        return None, None

    benchmark_data.locate_solution_results_by_task_uuid_and_solver_uuid = no_solution
    return benchmark_data


def test_test_tier_is_excluded_from_scoring_and_ml_feature_map(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "qb_gsee_benchmark.benchmark_data.canonical_problem_family",
        lambda short_name, *, task_uuid: "fixture_family",
    )
    benchmark_data = taxonomy_fixture()

    labels = benchmark_data.calculate_solver_success_labels()

    assert set(labels["task_uuid"]) == {"task-expanded"}
    assert {
        "reference_provenance_grade",
        "curation_tier",
        "reference_independence_from_solvers",
        "model_hamiltonian_downfolded",
        "source_defect_documented",
        "planting_mechanism",
    }.issubset(labels.columns)
    assert labels.iloc[0]["reference_provenance_grade"] == "exact"
    assert labels.iloc[0]["curation_tier"] == "expanded"

    benchmark_data.aggregated_solver_labels_df = labels
    benchmark_data.write_data_for_bubble_ml_gui(str(tmp_path))

    assert set(benchmark_data.data_for_bubble_ml_df["task_uuid"]) == {
        "task-expanded"
    }
