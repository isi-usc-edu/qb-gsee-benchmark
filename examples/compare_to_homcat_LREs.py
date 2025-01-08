"""This script compares the logical resource estimates computed by the benchmark's
example QPE resource estimates with those reported in the September 2024 QB delivery."""

import json
import os
from collections import defaultdict

import matplotlib.cm as cm
import matplotlib.pyplot as plt
import pandas as pd

benchmark_results_dir = "resource_estimate_files_20250106"
september_results_dir = "september_results"
PROBLEM_INSTANCE_DIR = "../problem_instances"


def get_qre_from_dir(dir: str) -> dict:
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


def infer_september_style_task_id(row: pd.Series) -> str:
    for file in os.listdir(PROBLEM_INSTANCE_DIR):
        if row["instance_id"] in file:
            with open(os.path.join(PROBLEM_INSTANCE_DIR, file)) as f:
                data = json.load(f)
                for task in data["tasks"]:
                    if task["task_uuid"] == row["task_id"]:
                        return (
                            task["features"]["molecule_name"]
                            + "-"
                            + str(task["features"]["avas_no"])
                        )
    raise ValueError(f"Task {row['task_id']} not found")


def plot_logical_qubit_comparison(results: pd.DataFrame) -> plt.Axes:
    colormap = cm.get_cmap("tab10", len(results.groupby("instance_name_benchmark")))
    plt.figure()
    for index, (name, group) in enumerate(results.groupby("instance_name_benchmark")):
        group.plot.scatter(
            "Logical qubits (January 2025)",
            "Logical qubits (September 2024)",
            label=name,
            color=colormap(index),
            ax=plt.gca(),
        )
    plt.tight_layout()
    return plt.gca()


def plot_t_count_comparison(results: pd.DataFrame) -> plt.Axes:
    colormap = cm.get_cmap("tab10", len(results.groupby("instance_name_benchmark")))
    plt.figure()
    for index, (name, group) in enumerate(results.groupby("instance_name_benchmark")):
        group.plot.scatter(
            "T gates (January 2025)",
            "T gates (September 2024)",
            label=name,
            color=colormap(index),
            ax=plt.gca(),
        )
    plt.tight_layout()
    return plt.gca()


def main():
    benchmark_results = get_qre_from_dir(benchmark_results_dir)
    benchmark_results = pd.DataFrame(benchmark_results)
    benchmark_results["task_uuid"] = benchmark_results["task_id"]
    benchmark_results["task_id"] = benchmark_results.apply(
        infer_september_style_task_id, axis=1
    )

    september_results = get_qre_from_dir(september_results_dir)
    september_results = pd.DataFrame(september_results)

    results = pd.merge(
        benchmark_results,
        september_results,
        on="task_id",
        suffixes=("_benchmark", "_september"),
        how="left"
    )

    missing_rows = results[results["num_logical_qubits_benchmark"].isna()]
    if not missing_rows.empty:
        print("The following tasks are in the benchmark but not in the September results:")
        print(missing_rows[["task_id", "instance_name_september"]])
    else:
        print("All September tasks are in the benchmark results.")

    results = results.rename(
        columns={
            "task_uuid": "Task UUID",
            "num_T_gates_benchmark": "T gates (January 2025)",
            "num_T_gates_september": "T gates (September 2024)",
            "num_logical_qubits_benchmark": "Logical qubits (January 2025)",
            "num_logical_qubits_september": "Logical qubits (September 2024)",
        },
    )
    print(results.to_markdown(index=False))

    plot_logical_qubit_comparison(results)
    plt.show()

    plot_t_count_comparison(results)
    plt.show()


if __name__ == "__main__":
    main()
