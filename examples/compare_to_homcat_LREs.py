"""This script compares the logical resource estimates computed by the benchmark's
example QPE resource estimates with those reported in the September 2024 QB delivery."""

import json
import os
from collections import defaultdict

import pandas as pd

benchmark_results_dir = "../scripts/resource_estimate_files_20241210"
september_results_dir = "september_results"


def get_qre_from_dir(dir):
    result = defaultdict(list)
    files = os.listdir(dir)
    for file in files:
        if not file.endswith(".json"):
            continue
        with open(os.path.join(dir, file)) as f:
            qre = json.load(f)
            for task in qre["tasks"]:
                result["num_logical_qubits"].append(
                    task["logical-abstract"]["num_qubits"]
                )
                result["num_T_gates"].append(task["logical-abstract"]["t_count"])
                result["task_id"].append(task["id"])
                result["instance_id"].append(qre["id"])
                result["instance_name"].append(qre["name"])
    return result


def load_task_id_map():
    with open("task_id_map.csv") as f:
        task_ids = pd.read_csv(f)

    task_id_map = {}
    for _, row in task_ids.iterrows():
        task_id_map[row["september_task_id"]] = row["benchmark_task_id"]
    return task_id_map


def main():
    task_id_map = load_task_id_map()
    benchmark_results = get_qre_from_dir(benchmark_results_dir)
    september_results = get_qre_from_dir(september_results_dir)
    september_results["task_id"] = [
        task_id_map.get(task_id) for task_id in september_results["task_id"]
    ]

    benchmark_results = pd.DataFrame(benchmark_results)
    september_results = pd.DataFrame(september_results).dropna(subset=["task_id"])

    results = pd.merge(
        benchmark_results,
        september_results,
        on="task_id",
        suffixes=("_benchmark", "_september"),
    )

    print(results)


if __name__ == "__main__":
    main()
