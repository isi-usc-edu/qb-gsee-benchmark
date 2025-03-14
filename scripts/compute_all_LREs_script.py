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
import time

import pandas as pd
from pyLIQTR.utils.resource_analysis import estimate_resources

from qb_gsee_benchmark.qre import get_df_qpe_circuit
from qb_gsee_benchmark.utils import retrieve_fcidump_from_sftp
from qb_gsee_benchmark.utils import iso8601_timestamp
from qb_gsee_benchmark.utils import load_json_files

DOUBLE_FACTORIZED_ATTRIBUTES = [
    "L",
    "nL",
    "nXi",
    "nLXi",
    "phase_gradient_eps",
    "energy_error",
    "step_error",
    "bits_rot_givens",
    "keep_bitsize",
    "keep_bitsize_outer",
    "outer_prep_eps",
    "alpha",
]

logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler("compute_all_LREs_script.log.txt", delay=False)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler, file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)


def get_lqre(
    problem_instance: dict, username: str, ppk_path: str, config: dict
) -> dict[str, Any]:
    problem_instance_uuid = problem_instance["problem_instance_uuid"]
    problem_instance_short_name = problem_instance["short_name"]
    logging.info(f"problem_instance UUID: {problem_instance_uuid}")
    logging.info(f"problem_instance short name: {problem_instance_short_name}")
    num_hams = len(problem_instance["tasks"])
    logging.info(f"contains {num_hams} associated Hamiltonians.")

    if (
        "overlap" in config["algorithm_parameters"]
        and "overlap_csv" in config["algorithm_parameters"]
    ):
        raise ValueError("Config cannot specify both 'overlap' and 'overlap_csv'.")

    if config["algorithm_parameters"].get("overlap_csv"):
        overlap_df = pd.read_csv(config["algorithm_parameters"]["overlap_csv"])
        overlaps = {
            row["task_uuid"]: row["overlap"] for index, row in overlap_df.iterrows()
        }

    solution_data: list[dict[str, Any]] = []
    results: dict[str, Any] = {}

    for task in problem_instance["tasks"]:
        if not config["algorithm_parameters"].get("overlap") and not overlaps.get(
            task["task_uuid"]
        ):
            logging.info(
                f"Skipping task {task['task_uuid']} because no overlap was provided."
            )
            continue

        logging.info(f"Analyzing task {task['task_uuid']}...")

        num_supporting_files = len(task["supporting_files"])
        logging.info(f"number of supporting files: {num_supporting_files}")

        for supporting_file in task["supporting_files"]:
            # flush log buffer to log file
            file_handler.flush()

            fcidump_uuid = supporting_file["instance_data_object_uuid"]
            fcidump_url = supporting_file["instance_data_object_url"]
            logging.info(f"supporting data file UUID: {fcidump_uuid}.")
            logging.info(f"supporting data file URL: {fcidump_url}.")

            parsed_url = urlparse(fcidump_url)
            fcidump_file_name = parsed_url.path.split("/")[-1]

            # TODO: fix hacky way of only grabbing FCIDUMP files:
            if "fcidump".lower() in fcidump_file_name.lower():
                logging.info(f"assuming {fcidump_file_name} is an FCIDUMP file.")
            else:
                logging.info(
                    f"assuming {fcidump_file_name} is NOT an FCIDUMP file.  SKIPPING!"
                )
                continue

            # TODO: check to see if we have already processed this FCIDUMP file.
            sftp_attempt = 1
            max_sftp_attempts = 10
            while sftp_attempt <= max_sftp_attempts:
                try:
                    logging.info(f"SFTP downloading file {fcidump_url}...attempt {sftp_attempt}/{max_sftp_attempts}")
                    fci = retrieve_fcidump_from_sftp(
                        url=fcidump_url,
                        username=username,
                        ppk_path=ppk_path,
                        port=22,
                    )
                    break
                except Exception as e:
                    logging.error(f'Error: {e}', exc_info=True)
                    logging.info(f"Sleeping for 5 seconds and trying again...")
                    time.sleep(5)
                    sftp_attempt += 1
                    continue
            
            if sftp_attempt > max_sftp_attempts:
                logging.error(f"Error: failed to SFTP fetch file.")
                sys.exit(1)


            num_orbitals = fci["H1"].shape[0]
            if num_orbitals > config["algorithm_parameters"]["max_orbitals"]:
                logging.info(
                    f"Skipping Logical Resource Estimate because number of orbitals ({num_orbitals}) exceeds maximum specified in config ({config['algorithm_parameters']['max_orbitals']})."
                )
                continue

            logging.info(f"===============================================")
            logging.info(f"Calculating Logical Resource Estimate...")

            error_tolerance = task["requirements"]["absolute_accuracy_threshold"]
            failure_tolerance = 1 - task["requirements"]["probability_of_success"]

            overlap = (
                config["algorithm_parameters"].get("overlap")
                if config["algorithm_parameters"].get("overlap")
                else overlaps.get(task["task_uuid"])
            )
            circuit_generation_start_time = datetime.datetime.now()
            (
                circuit,
                num_shots,
                hardware_failure_tolerance_per_shot,
            ) = get_df_qpe_circuit(
                fci=fci,
                error_tolerance=error_tolerance,
                failure_tolerance=failure_tolerance,
                square_overlap=overlap**2,
                sf_threshold=config["algorithm_parameters"]["sf_threshold"],
                df_threshold=config["algorithm_parameters"]["df_threshold"],
            )
            circuit_generation_end_time = datetime.datetime.now()
            logging.info(
                f"Circuit initialization time: {(circuit_generation_end_time - circuit_generation_start_time).total_seconds()} seconds."
            )
            logging.info(f"Estimating logical resources...")
            resource_estimation_start_time = datetime.datetime.now()
            logical_resources = estimate_resources(circuit.circuit)
            resource_estimation_end_time = datetime.datetime.now()
            LRE_calc_time = (
                resource_estimation_end_time - resource_estimation_start_time
            ).total_seconds()
            logging.info(f"Resource estimation time (seconds): {LRE_calc_time}")

            block_encoding = circuit._block_encoding
            solution_data.append(
                {
                    "task_uuid": task["task_uuid"],
                    "error_bound": error_tolerance,
                    "confidence_level": 1 - failure_tolerance,
                    "quantum_resources": {
                        "logical": {
                            "num_logical_qubits": logical_resources["LogicalQubits"],
                            "num_T_gates_per_shot": logical_resources["T"],
                            "num_shots": math.ceil(num_shots),
                            "hardware_failure_tolerance_per_shot": hardware_failure_tolerance_per_shot,
                        }
                    },
                    "solution_details": {
                        "block_encoding_details": {
                            attribute: getattr(block_encoding, attribute)
                            for attribute in DOUBLE_FACTORIZED_ATTRIBUTES
                        },
                        "overlap": overlap,
                        "num_bits_precision_qpe": circuit._prec,
                    },
                    "run_time": {
                        "preprocessing_time": {
                            "wall_clock_start_time": circuit_generation_start_time.strftime(
                                "%Y-%m-%dT%H:%M:%S.%f"
                            )
                            + "+00:00",
                            "wall_clock_stop_time": circuit_generation_end_time.strftime(
                                "%Y-%m-%dT%H:%M:%S.%f"
                            )
                            + "+00:00",
                            "seconds": (
                                circuit_generation_end_time
                                - circuit_generation_start_time
                            ).total_seconds(),
                        },
                    },
                }
            )

    solver_details = {
        "solver_uuid": config["solver_uuid"],
        "solver_short_name": "DF_QPE",
        "compute_hardware_type": "quantum_computer",
        "algorithm_details": {
            "algorithm_description": config["algorithm_description"],
            "algorithm_parameters": config["algorithm_parameters"],
        },
        "software_details": [
            {"software_name": "pyLIQTR", "software_version": version("pyLIQTR")},
            {
                "software_name": "qb-gsee-benchmark",
                "software_version": version("qb-gsee-benchmark"),
            },
            {"software_name": "Python", "software_version": sys.version},
        ],
    }
    results = {
        "$schema": "https://raw.githubusercontent.com/isi-usc-edu/qb-gsee-benchmark/refs/heads/main/schemas/solution.schema.0.0.1.json",
        "solution_uuid": str(uuid4()),
        "problem_instance_uuid": problem_instance["problem_instance_uuid"],
        "creation_timestamp": iso8601_timestamp(),
        "is_resource_estimate": True,
        "contact_info": config["contact_info"],
        "solution_data": solution_data,
        "compute_hardware_type": "quantum_computer",
        "solver_details": solver_details,
        "digital_signature": None,
    }

    return results


def get_solved_problem_uuids(config: dict[str, Any], output_dir: str) -> set[str]:
    existing_output_files = os.listdir(args.output_dir)
    print(output_dir)
    print(existing_output_files)
    logging.info(f"parsing {len(existing_output_files)} files in the output directory")
    solved_problem_uuids = []
    for s in existing_output_files:
        with (open(os.path.join(args.output_dir, s), "r")) as f:
            solution = json.load(f)
            if (
                solution["solver_details"]["solver_uuid"] == config["solver_uuid"]
                and json.dumps(
                    solution["solver_details"]["algorithm_details"][
                        "algorithm_description"
                    ],
                    sort_keys=True,
                )
                == json.dumps(config["algorithm_description"], sort_keys=True)
                and json.dumps(
                    solution["solver_details"]["algorithm_details"][
                        "algorithm_parameters"
                    ],
                    sort_keys=True,
                )
                == json.dumps(config["algorithm_parameters"], sort_keys=True)
            ):
                solved_problem_uuids.append(solution["problem_instance_uuid"])
    logging.info(
        f"found {len(solved_problem_uuids)} existing solutions for this solver."
    )
    return set(solved_problem_uuids)


def main(args: argparse.Namespace) -> None:

    config = json.load(open(args.LRE_config_file, "r"))

    overall_start_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"input directory: {args.input_dir}")

    input_dir = args.input_dir

    problem_instances = load_json_files(input_dir)
    logging.info(f"parsing {len(problem_instances)} files in the input directory")
    for p in problem_instances:
        short_name = p["short_name"]
        problem_instance_uuid = p["problem_instance_uuid"]
        logging.info(f"problem instance: {short_name}, {problem_instance_uuid}")

    solved_problem_uuids = get_solved_problem_uuids(config, args.output_dir)

    for problem_instance in problem_instances:
        short_name = p["short_name"]
        problem_instance_uuid = p["problem_instance_uuid"]
        logging.info(f"parsing: {short_name}, {problem_instance_uuid}")
        
        if problem_instance["problem_instance_uuid"] in solved_problem_uuids:
            logging.info(
                f"skipping {problem_instance['problem_instance_uuid']} because it already has a solution with the same solver UUID and algorithm details."
            )
            continue
        
        resource_estimate = get_lqre(
            problem_instance, 
            args.sftp_username, 
            args.sftp_key_file, 
            config=config
        )
        if len(resource_estimate["solution_data"]) > 0:
            with open(
                os.path.join(
                    args.output_dir,
                    f"{problem_instance['problem_instance_uuid']}_sol_{resource_estimate['solution_uuid']}.json",
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
        description="a script to calculate Logical Resource Estimates (LREs) for all problem_instance files.  Outputs are solution.uuid.json files."
    )

    parser.add_argument(
        "-i",
        "--input_dir",
        type=str,
        required=True,
        help="Specify directory for problem_instances (.json files)",
    )

    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=True,
        help="Specify directory to save resource estimates to (.json files)",
    )

    parser.add_argument(
        "--LRE_config_file",
        type=str,
        required=True,
        help="A JSON file with configuration options and hyperparameters for LRE and a `solver` UUID.",
    )

    parser.add_argument(
        "--sftp_username",
        type=str,
        required=True,
        help="username for SFTP server where FCIDUMP files are stored.",
    )

    parser.add_argument(
        "--sftp_key_file",
        type=str,
        required=True,
        help="local/path/to/the/keyfile for the SFTP server (corresponding to sftp_username)",
    )

    args = parser.parse_args()
    main(args)
