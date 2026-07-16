# Copyright 2026.
#
# Licensed under the Apache License, Version 2.0.

import pandas as pd

from qb_gsee_benchmark.benchmark_data import BenchmarkData


def test_calculate_solver_success_labels_accuracy_boundary_is_inclusive(monkeypatch):
    monkeypatch.setattr(
        "qb_gsee_benchmark.benchmark_data.canonical_problem_family",
        lambda short_name, *, task_uuid: "fixture_family",
    )
    benchmark_data = object.__new__(BenchmarkData)
    benchmark_data.hamiltonian_features = pd.DataFrame(
        [{"task_uuid": "task-boundary", "n_orbs": 4}]
    )
    benchmark_data.solvers_df = pd.DataFrame(
        [{"solver_short_name": "Boundary", "solver_uuid": "solver-boundary"}]
    )
    benchmark_data.problem_instance_category_by_short_name = {
        "boundary_case": "validation_instances"
    }
    benchmark_data.problem_instance_list = [
        {
            "problem_instance_uuid": "instance-boundary",
            "short_name": "boundary_case",
            "calendar_due_date": None,
            "tasks": [
                {
                    "task_uuid": "task-boundary",
                    "requirements": {
                        "time_limit_seconds": 100,
                        "absolute_accuracy_threshold": 0.25,
                        "reference_energy": 0.0,
                    },
                    "supporting_files": [
                        {
                            "instance_data_object_uuid": "data-boundary",
                            "instance_data_object_url": "sftp://example/boundary.fcidump.gz",
                        }
                    ],
                }
            ],
        }
    ]
    benchmark_data.solution_list = [
        {
            "solution_uuid": "solution-boundary",
            "is_resource_estimate": False,
        }
    ]

    def locate_solution_results_by_task_uuid_and_solver_uuid(solver_uuid, task_uuid):
        return {
            "run_time": {"overall_time": {"seconds": 10}},
            "energy": 0.25,
        }, "solution-boundary"

    benchmark_data.locate_solution_results_by_task_uuid_and_solver_uuid = (
        locate_solution_results_by_task_uuid_and_solver_uuid
    )

    labels = benchmark_data.calculate_solver_success_labels()
    solved = labels.iloc[0]

    assert solved["solved_within_accuracy_requirement"] is True
    assert solved["label"] is True
    assert solved["outcome"] == "solved"
