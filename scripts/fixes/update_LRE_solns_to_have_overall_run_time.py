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
import requests

import logging
logging.basicConfig(level=logging.INFO)

import json
import sys
sys.path.append("../")
import os
import datetime

import time

# additional package(s)
import jsonschema



import json
import requests
import pprint

import sys
sys.path.append("../")


# additional package(s):
# import jsonschema






def main(args):
    input_directory = args.input_dir
    output_directory = args.output_dir

    logging.info(f"started at: {datetime.datetime.now().isoformat()}")
    logging.info(f"input directory: {input_directory}")
    logging.info(f"output directory: {output_directory}")

    
    json_files = os.listdir(input_directory)
    for json_file in json_files:
        json_file_path = input_directory + json_file
        logging.info(f"parsing {json_file_path}")
        with open(json_file_path, "r") as jf:
        
            # load data from file as a Python dictionary object:
            try:
                solution_file = json.load(jf)
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                continue # to next json file.

        ########################################################
        #### update the fields of the solution_file dict.


        logging.info(f"number of tasks reported: {len(solution_file['solution_data'])}")
        for task in solution_file["solution_data"]:
            num_T_gates_per_shot = task["quantum_resources"]["logical"]["num_T_gates_per_shot"]
            num_shots = task["quantum_resources"]["logical"]["num_shots"]

            
            conversion_fraction = 0.000020 # 20 microseconds per t_gate
            overall_time_seconds = conversion_fraction*num_T_gates_per_shot*num_shots
            task["run_time"]["overall_time"] = {}
            task["run_time"]["overall_time"]["seconds"] = overall_time_seconds
            task["run_time"]["overall_time"]["comments"] = {
                "comment_1": "seconds = (0.00002 seconds/t_gate)(num_T_gates_per_shot)(num_shots)",
                "comment_2": "20usec/t_gate based on the assumptions in the paper, including: 4 factories, 0.1percent physical error rate and AutoCCZ factories can support twice as many T-gates as Toffolis.",
                "reference": "https://journals.aps.org/prxquantum/abstract/10.1103/PRXQuantum.2.030305"
            }
            

        ########################################################
        #### write out the updated .json file

        output_json_file_path = output_directory + json_file
        with open(output_json_file_path, "w") as output_json_file:
            json.dump(solution_file, output_json_file)


    

    logging.info("done")
    




if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="a script to update LRE solution files with run time per 20usec/tgate estimate."
    )
    
    parser.add_argument(
        "-i", 
        "--input_dir", 
        type=str, 
        help="Specify directory for solution_files (.json files)"
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        help="The directory where updated .json files are moved to."
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
    else:
        main(args)

