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


import os
import argparse
import datetime
from pathlib import Path
import json
from urllib.parse import urlparse
import uuid
import sys

import numpy as np
import pandas as pd



import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(
    "compute_sponsor_json_resource_estimates.log.txt",
    delay=False
)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler , file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)





def main(args):
   


    overall_start_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"Starting compute_sponsor_json_resource_estimates...")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"aggregated labels: {args.aggregated_solver_labels}")
    logging.info(f"utility estimate file: {args.utility_estimate_xlsx}")
    logging.info(f"solver UUID: {args.solver_uuid}")
    solver_uuid = args.solver_uuid


    logging.info(f"reading in: {args.aggregated_solver_labels}")
    aggregated_solver_labels = pd.read_csv(args.aggregated_solver_labels)
    
    logging.info(f"reading in: {args.utility_estimate_xlsx}")
    try:
        utility_estimate_xlsx = pd.read_excel(args.utility_estimate_xlsx)
    except Exception as e:
        logging.error(f'Error: {e}', exc_info=True)
        logging.info(f"attempting to read the file as .csv... ")
        utility_estimate_xlsx = pd.read_csv(args.utility_estimate_xlsx)

    utility_estimate_xlsx["task_uuid"] = utility_estimate_xlsx["task_uuid"].str.strip()
    logging.info(f"{len(utility_estimate_xlsx)} lines in the excel sheet.")

    # filter 
    solver_labels = aggregated_solver_labels[aggregated_solver_labels["solver_uuid"]==solver_uuid]
    solver_labels["task_uuid"] = solver_labels["task_uuid"].str.strip()

    logging.info(f"number of entries in solver labels (for the solver): {len(solver_labels)}")
    
    
    # Inner join on the utility estimate xlsx and aggregated_solver_labels
    #===============================================================
    data = pd.merge(
        solver_labels,
        utility_estimate_xlsx,
        on="task_uuid",
        how="inner"
        # how=inner only match rows that by task_uuid that exist in either file (possibly fewer rows).
        # how=outer fill in NaN when merging if uuids missing from either file.
    )
    data.to_csv("artifact.resource_estimate_data.csv", index=False)



    # Create a resource_estimate.json file for each problem_instance
    #===============================================================
    problem_instance_uuid_list = data["problem_instance_uuid"].unique()
    for problem_instance_uuid in problem_instance_uuid_list:
        resource_estimate = {} # init
        resource_estimate["id"] = problem_instance_uuid
        resource_estimate["category"] = "industrial"
        resource_estimate["size"] = None # TODO: number of orbitals?
        resource_estimate["task"] = "ground_state_energy_estimation"
        
        
        
        df_filtered = data[data["problem_instance_uuid"]==problem_instance_uuid]
        
        
        problem_instance_short_name = df_filtered["problem_instance_short_name"].iloc[0]
        logging.info(f"problem_instance_short_name: {problem_instance_short_name}")
        logging.info(f"problem_instance_uuid: {problem_instance_uuid}")
        resource_estimate["name"] = problem_instance_short_name

        aggregate_value = 0 # init
        aggregate_value_min = 0 # init
        aggregate_value_max = 0 # init

        resource_estimate["tasks"] = [] # init
        task_uuid_list = df_filtered["task_uuid"].values
        for task_uuid in task_uuid_list:
            logging.info(f"task_uuid: {task_uuid}")

            df_filtered = data[data["task_uuid"]==task_uuid]
            assert len(df_filtered) == 1, "possible issue #44:  may have more than one task_uuid in sheet."
            
            
            task_results = {} # init
            task_results["id"] =  task_uuid
            task_results["name"] = df_filtered["instance_data_object_url"].values[0]

            task_results["value"] = df_filtered["Utility NPV $"].values[0]
            task_results["value_ci"] = []
            task_results["value_ci"].append(df_filtered["Utility NVP lower bound $"].values[0])
            task_results["value_ci"].append(df_filtered["Utility NVP upper bound $"].values[0])
            
            logging.info(f"value: {task_results['value']}")
            aggregate_value += task_results["value"]
            aggregate_value_min += task_results["value_ci"][0]
            aggregate_value_max += task_results["value_ci"][1]


            task_results["implementation"] = "Qubitized QPE with double factorization"

            if df_filtered["attempted"].values[0]:
                task_results["repetitions"] = df_filtered["num_shots"].values[0]
                task_results["logical-abstract"] = {}
                task_results["logical-abstract"]["num_qubits"] = df_filtered["num_logical_qubits"].values[0]
                task_results["logical-abstract"]["t_count"] = df_filtered["num_T_gates_per_shot"].values[0]
            else:
                # did not attempt resource estimation.  probably due to number of orbitals.
                task_results["comment"] = "did not attempt resource estimation for this task."
                task_results["repetitions"] = None
                task_results["logical-abstract"] = {}
                task_results["logical-abstract"]["num_qubits"] = None
                task_results["logical-abstract"]["t_count"] = None

            
            # add to building list of all tasks for the problem_instance
            resource_estimate["tasks"].append(task_results)

        
        # write out JSON for each problem_instance
        resource_estimate["value"] = aggregate_value
        resource_estimate["value_ci"] = [aggregate_value_min, aggregate_value_max]

        resource_estimate_file_name = f"resource_estimate.gsee.{problem_instance_short_name}.{problem_instance_uuid}.json"
        with open(resource_estimate_file_name, "w") as output_file:
            json.dump(resource_estimate, output_file, indent=4)
        logging.info(f"wrote file: {resource_estimate_file_name}")
        

        




    

    
    # Print overall time.
    #===============================================================
    overall_stop_time = datetime.datetime.now()
    logging.info(f"done.")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"overall stop time: {overall_stop_time}")
    logging.info(f"run time (seconds): {(overall_stop_time - overall_start_time).total_seconds()}")

    
    










if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
            a script to calculate `resource_estimate.json` file per the 
            sponsor-requested schema.
            outputs of the `performance_metrics` script:  `aggregated_solver_labels_<date>.csv`
            and a `utility_estimation.xlsx` spreadsheet.
            F
        """
    )
    
    parser.add_argument(
        "--aggregated_solver_labels", 
        type=str, 
        required=True,
        help="Typically `aggregated_solver_labels_<date>.csv`, which is an ephemeral output from the `performance_metrics` script."
    )

    parser.add_argument(
        "--utility_estimate_xlsx", 
        type=str, 
        required=True,
        help="The excel sheet with the latest utility estimate figures."
    )

    parser.add_argument(
        "--solver_uuid", 
        type=str, 
        required=True,
        help="""
            The UUID of the resource estimation software.
        """
    )

    args = parser.parse_args()
    main(args)


