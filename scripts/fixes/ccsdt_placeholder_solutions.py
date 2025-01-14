#!/usr/bin/env python3


# Copyright 2025 L3Harris Technologies, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from qb_gsee_benchmark.utils import data_frame_vlookup
from qb_gsee_benchmark.utils import BenchmarkData
from qb_gsee_benchmark.utils import iso8601_timestamp
from qb_gsee_benchmark.utils import validate_json

import os
import json
import logging
import uuid
import shutil

import pandas as pd





benchmark_data = BenchmarkData(
    hamiltonian_features_csv_file_name="/home/labuser/Projects/qb-gsee-benchmark/scripts/Hamiltonian_features.csv",
    utility_estimation_csv_file_name="/home/labuser/Projects/qb-gsee-benchmark/scripts/GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv",
    problem_instances_directory="/home/labuser/Projects/qb-gsee-benchmark/problem_instances",
    solution_files_directory="/home/labuser/Projects/qb-gsee-benchmark/solution_files",
    performance_metrics_directory="/home/labuser/Projects/qb-gsee-benchmark/performance_metrics"
)
print(benchmark_data)




ccsdt = pd.read_csv("/home/labuser/Projects/qb-gsee-benchmark/scripts/fixes/ccsdt_results_with_task_uuid.csv")





output_directory = "temp_ccsdt_solutions"
try:
    shutil.rmtree(output_directory)
except Exception as e:
    logging.error(f'Error: {e}', exc_info=True)
    logging.error(f"attempted to remove the directory {output_directory}...")
os.mkdir(output_directory)
   


for problem_instance in benchmark_data.problem_instance_list:
    
    problem_instance_uuid = problem_instance["problem_instance_uuid"]
    solution_uuid = str(uuid.uuid4())
    creation_timestamp = iso8601_timestamp()
    problem_instance_short_name = problem_instance["short_name"]

    solution = {}
    solution = {
        "$schema": "https://raw.githubusercontent.com/isi-usc-edu/qb-gsee-benchmark/main/schemas/solution.schema.0.0.1.json",
        "problem_instance_uuid":problem_instance_uuid,
        "solution_uuid":solution_uuid,
        "creation_timestamp":creation_timestamp,
        "contact_info":[
            {
                "name": "placeholder",
                "email": "placeholder@placeholder.com",
                "institution": "placeholder"
            }
        ],
        "is_resource_estimate":False,
        "solution_data":[],
        "solver_details":{
                "solver_uuid":"fd13c864-baf1-44de-b52d-0e5dd69f647a",
                "solver_short_name": "CCSDT_PLACEHOLDER",
                "compute_hardware_type": "classical_computer",
                "classical_hardware_details": {
                    "cpu_description": "CCSDT_PLACEHOLDER_cpu_description"
                },
            "algorithm_details": "CCSDT_PLACEHOLDER_algorithm_details",
            "software_details": "CCSDT_PLACEHOLDER_software_details"
        },
        "digital_signature":None
    }


    for task in problem_instance["tasks"]:
        task_uuid = task["task_uuid"]

        # determine if CCSDT attempted the task_uuid
        ccsdt_task_result = ccsdt[ccsdt["task_uuid"]==task_uuid]
        assert len(ccsdt_task_result) <= 1, "should not have more than one result!"
        if len(ccsdt_task_result) == 0:
            # print(f"no CCSDT results for problem_instance {problem_instance_short_name}, task {task_uuid}")
            continue

        soln_datum = {
            "task_uuid":task_uuid,
            "energy":float(ccsdt_task_result["CCSDT"].iloc[0]),
            "run_time":{
                "overall_time":{
                    "seconds":3600 # fixed at one hour for this PLACEHOLDER solution.
                }
            }
        }
        solution["solution_data"].append(soln_datum)

    attempt_ratio = f"{len(solution['solution_data'])}/{len(problem_instance['tasks'])}"
    print(f"{attempt_ratio} tasks attempted for problem_instance {problem_instance_short_name}")
    if len(solution["solution_data"]) > 0:
        # if one or more tasks were attempted, then write out solution.json
        validate_json(solution)

        solution_file_name = f"solution.ccsdt_placeholder.{solution_uuid}.json"
        output_solution_json_path = os.path.join(output_directory, solution_file_name)
        with open(output_solution_json_path, "w") as output_json_file:
            json.dump(solution, output_json_file, indent=4)
        
        



print("done.")











