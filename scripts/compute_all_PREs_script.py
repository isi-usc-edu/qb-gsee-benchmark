#!/usr/bin/env python3

# Copyright 2024 L3Harris Technologies, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import argparse
import copy
import datetime
import json
import logging
import math
import os
import sys
from importlib.metadata import version
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from pyLIQTR.utils.resource_analysis import estimate_resources
from qualtran.surface_code.algorithm_summary import AlgorithmSummary
from qualtran.surface_code.ccz2t_cost_model import (
    get_ccz2t_costs_from_grid_search,
    iter_ccz2t_factories,
)

from qb_gsee_benchmark.qre import get_df_qpe_circuit
from qb_gsee_benchmark.utils import retrieve_fcidump_from_sftp


class NoFactoriesFoundError(Exception):
    pass


logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler("compute_all_QREs_scripts.log.txt", delay=False)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler, file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)


def get_physical_cost(
    num_logical_qubits: int,
    num_T_gates: int,
    hardware_failure_tolerance_per_shot: float,
    n_factories: int,
    physical_error_rate: float,
) -> tuple[float, int]:
    n_magic = AlgorithmSummary(t_gates=num_T_gates)
    try:
        best_cost, best_factory, best_data_block = get_ccz2t_costs_from_grid_search(
            n_magic=n_magic,
            n_algo_qubits=num_logical_qubits,
            error_budget=hardware_failure_tolerance_per_shot,
            phys_err=physical_error_rate,
            factory_iter=iter_ccz2t_factories(n_factories=n_factories),
            cost_function=(lambda pc: pc.duration_hr),
        )
        return best_cost.duration_hr * 60 * 60, best_cost.footprint
    except TypeError:
        raise NoFactoriesFoundError(
            f"No factories found that meet the performance requirements."
        )


def get_pqre(solution_lre: dict, config: dict) -> dict[str, Any]:
    logging.info(f"solution UUID: {solution_lre['solution_uuid']}")

    solution_pre = copy.deepcopy(solution_lre)

    for task_solution_data in solution_pre["solution_data"]:
        logging.info(f"Analyzing task {task_solution_data['task_uuid']}...")
        try:
            physical_resource_estimation_start = datetime.datetime.now()
            algorithm_runtime_seconds, num_physical_qubits = get_physical_cost(
                num_logical_qubits=task_solution_data["quantum_resources"]["logical"][
                    "num_logical_qubits"
                ],
                num_T_gates=task_solution_data["quantum_resources"]["logical"][
                    "num_T_gates_per_shot"
                ],
                hardware_failure_tolerance_per_shot=task_solution_data[
                    "quantum_resources"
                ]["logical"]["hardware_failure_tolerance_per_shot"],
                n_factories=config["quantum_hardware_parameters"]["num_factories"],
                physical_error_rate=config["quantum_hardware_parameters"][
                    "physical_error_rate"
                ],
            )
            physical_resource_estimation_end = datetime.datetime.now()
            logging.info(
                f"Physical resource estimation time: {(physical_resource_estimation_end - physical_resource_estimation_start).total_seconds()} seconds."
            )
            task_solution_data["run_time"]["algorithm_run_time"] = (
                {
                    "seconds": algorithm_runtime_seconds,
                },
            )
            task_solution_data["run_time"]["overall_time"] = {
                task_solution_data["run_time"]["preprocessing"]["seconds"]
                + algorithm_runtime_seconds
            }
            task_solution_data["quantum_resources"]["physical"] = {
                "num_physical_qubits": num_physical_qubits,
            }
        except NoFactoriesFoundError:
            logging.info(
                f"No factories found that meet the performance requirements. Skipping physical cost estimation."
            )

    solution_uuid = str(uuid4())
    current_time = datetime.datetime.now(datetime.timezone.utc)
    current_time_string = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

    solution_pre["solution_uuid"] = solution_uuid
    solution_pre["creation_timestamp"] = current_time_string
    solution_pre["contact_info"] = config["contact_info"]
    solution_pre["solver_details"]["software_details"].append(
        {
            "software_name": "qualtran",
            "software_version": version("qualtran"),
        }
    )

    solution_pre["solver_details"]["quantum_hardware_details"] = {
        "quantum_hardware_description": config["quantum_hardware_description"],
        "quantum_hardware_parameters": config["quantum_hardware_parameters"],
    }
    solution_pre["solver_details"]["solver_uuid"] = config["solver_uuid"]
    solution_pre["digital_signature"] = None

    return solution_pre


def main(args: argparse.Namespace) -> None:

    config = json.load(open(args.QRE_config_file, "r"))

    overall_start_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"input directory: {args.input_dir}")

    input_dir = args.input_dir

    solution_lre_files = os.listdir(input_dir)
    logging.info(f"parsing {len(solution_lre_files)} files in the input directory")
    for s in solution_lre_files:
        logging.info(f"file: {s}")

    for solution_lre_file_name in solution_lre_files:
        solution_lre_path = os.path.join(input_dir, solution_lre_file_name)
        logging.info(f"parsing {solution_lre_path}")
        with open(solution_lre_path, "r") as jf:
            solution_lre = json.load(jf)

            resource_estimate = get_pqre(solution_lre=solution_lre, config=config)
            if len(resource_estimate["solution_data"]) > 0:
                with open(
                    os.path.join(
                        args.output_dir,
                        f"{resource_estimate['problem_instance_uuid']}_sol_{resource_estimate['solution_uuid']}.json",
                    ),
                    "w",
                ) as f:
                    json.dump(resource_estimate, f, indent=4)

    # Print overall time.
    # ===============================================================
    overall_stop_time = datetime.datetime.now()
    logging.info(f"done.")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"overall stop time: {overall_stop_time}")
    logging.info(
        f"run time (seconds): {(overall_stop_time - overall_start_time).total_seconds()}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="a script to calculate Physical Resource Estimates (PREs) for all solution files containing Logical Resource Estimates (LREs).  Outputs are solution.uuid.json files."
    )

    parser.add_argument(
        "-i",
        "--input_dir",
        type=str,
        required=True,
        help="Specify directory for solution logical resource estiamtes (.json files)",
    )

    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=True,
        help="Specify directory to save physical resource estimates to (.json files)",
    )

    parser.add_argument(
        "--PRE_config_file",
        type=str,
        required=True,
        help="A JSON file with configuration options and hyperparameters for PRE and a `solver` UUID.",
    )

    args = parser.parse_args()
    main(args)
