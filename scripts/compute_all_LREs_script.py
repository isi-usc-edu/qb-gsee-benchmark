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
import os
import time
from datetime import UTC
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from pyLIQTR.utils.resource_analysis import estimate_resources

from qb_gsee_benchmark.qre import get_df_qpe_circuit
from qb_gsee_benchmark.utils import retrieve_fcidump_from_sftp

logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler("compute_all_LREs_scripts.log.txt", delay=False)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler, file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)


def get_lqre(problem_instance: dict, username: str, ppk_path: str, config: dict) -> None:
    problem_instance_uuid = problem_instance["problem_instance_uuid"]
    problem_instance_short_name = problem_instance["short_name"]
    logging.info(f"problem_instance UUID: {problem_instance_uuid}")
    logging.info(f"problem_instance short name: {problem_instance_short_name}")
    num_hams = len(problem_instance["instance_data"])
    logging.info(f"contains {num_hams} associated Hamiltonians.")

    solution_data: list[dict[str, Any]] = []
    results = {}

    for task in problem_instance["instance_data"]:
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

            # check the see if we have already processed FCIDUMP_UUID and have a resource estimate for it.
            # ==============================================================
            # TODO... may need some ephemeral file output for incomplete/restarted work.

            # SFTP download the FCIDUMP file
            # ===============================================================
            logging.info(f"SFTP downloading file {fcidump_url}...")
            fci = retrieve_fcidump_from_sftp(
                url=fcidump_url,
                username=args.sftp_username,
                ppk_path=args.sftp_key_file,
                port=22,
            )

            # Calculate logical resource estimate for the FCIDUMP file
            # ===============================================================
            logging.info(f"===============================================")
            logging.info(f"calculating Logical Resource Estimate...")

            LRE_start_time = datetime.datetime.now()
            start = time.time()
            (
                circuit,
                num_shots,
                hardware_failure_tolerance_per_shot,
            ) = get_df_qpe_circuit(
                fci=fci,
                error_tolerance=1.6e-3, # TODO: extract this from problem instance
                failure_tolerance=1e-2, # TODO: extract this from problem instance
                square_overlap=config["algorithm_parameters"]["square_overlap"],
                df_threshold=config["algorithm_parameters"]["df_threshold"],
            )
            preprocessing_time = time.time() - start
            logging.info(f"Initialized circuit in {preprocessing_time} seconds.")
            logging.info(f"Estimating logical resources...")
            logical_resources = estimate_resources(circuit.circuit)

            solution_data.append(
                {
                    # "task_uuid": task["task_uuid"],
                    "num_logical_qubits": logical_resources["LogicalQubits"],
                    "num_t": logical_resources["T"],
                    "preprocessing_time": preprocessing_time,
                    "num_shots": num_shots,
                    "hardware_failure_tolerance_per_shot": hardware_failure_tolerance_per_shot,
                }
            )
            LRE_stop_time = datetime.datetime.now()
            LRE_calc_time = (LRE_stop_time - LRE_start_time).total_seconds()
            logging.info(f"LRE calculation run time (seconds): {LRE_calc_time}")

            # Clean up
            # ===============================================================
            logging.info(f"deleting file {fcidump_file_name}.")
            os.remove(fcidump_file_name)

        solution_uuid = str(uuid4())
        current_time = datetime.datetime.now(UTC)
        current_time_string = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

        compute_details = {
            "description": "Double factorized QPE resource estimates based on methodology of arXiv:2406.06335. Uses PyLIQTR logical resource estimates with BenchQ footprint analysis. Ground-state overlap assumed to be 0.8 and double-factorized truncation threshold to be 1e-3 Ha. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time."
        }
        results = {
            "$schema": "https://raw.githubusercontent.com/zapatacomputing/qb-gsee-benchmark/refs/heads/main/instances/schemas/solution.schema.0.0.1.json",
            "solution_uuid": solution_uuid,
            "problem_instance_uuid": problem_instance["problem_instance_uuid"],
            "creation_timestamp": current_time_string,
            "short_name": "QPE",
            "is_resource_estimate": True,
            "contact_info": config["contact_info"],
            "solution_data": solution_data,
            "compute_hardware_type": "quantum_computer",
            "compute_details": compute_details,
            "digital_signature": None,
        }

        return results


def main(args:argparse.Namespace) -> None:

    config = json.load(open(args.LRE_config_file, "r"))

    overall_start_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"input directory: {args.input_dir}")

    input_dir = args.input_dir

    problem_instance_files = os.listdir(input_dir)
    logging.info(f"parsing {len(problem_instance_files)} files in the input directory")
    for p in problem_instance_files:
        logging.info(f"file: {p}")

    for problem_instance_file_name in problem_instance_files:
        problem_instance_path = os.path.join(input_dir, problem_instance_file_name)
        logging.info(f"parsing {problem_instance_path}")
        with open(problem_instance_path, "r") as jf:

            # load data from file as a Python dictionary object:
            # Try... because we may have non-JSON files that we will skip.
            try:
                problem_instance = json.load(jf)
            except Exception as e:
                logging.error(f"Error: {e}", exc_info=True)
                continue  # to next json file.

            resource_estimate = get_lqre(
                problem_instance, args.sftp_username, args.sftp_key_file, config=config
            )
            # TODO: include solver id in filename
            with open(f"lqre-{problem_instance['problem_instance_uuid']}.json", "w") as f:
                json.dump(resource_estimate, f)

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
