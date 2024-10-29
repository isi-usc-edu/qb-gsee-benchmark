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
import jsonschema






def main(args):
    input_directory = args.input_dir
    output_directory = args.output_dir

    logging.info(f"started at: {datetime.datetime.utcnow().isoformat()}")
    logging.info(f"input directory: {input_directory}")
    logging.info(f"output directory: {output_directory}")

    
    json_files = os.listdir(input_directory)
    for json_file in json_files:
        json_file_path = input_directory + json_file
        logging.info(f"parsing {json_file_path}")
        with open(json_file_path, "r") as jf:
        
            # load data from file as a Python dictionary object:
            try:
                problem_instance = json.load(jf)
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                continue # to next json file.

        ########################################################
        #### update the fields of the problem_instance dict.

        for i in range(len(problem_instance["instance_data"])):
            uid = problem_instance["instance_data"][i]["instance_data_object_uuid"]
            url = problem_instance["instance_data"][i]["instance_data_object_url"]
            cksum = problem_instance["instance_data"][i]["instance_data_checksum"]
            cksum_type = problem_instance["instance_data"][i]["instance_data_checksum_type"]

            problem_instance["instance_data"][i]["supporting_files"]=[
                {
                    "instance_data_object_uuid": uid,
                    "instance_data_object_url": url,
                    "instance_data_checksum": cksum,
                    "instance_data_checksum_type": cksum_type
                }
            ]

            del problem_instance["instance_data"][i]["instance_data_object_uuid"]
            del problem_instance["instance_data"][i]["instance_data_object_url"]
            del problem_instance["instance_data"][i]["instance_data_checksum"]
            del problem_instance["instance_data"][i]["instance_data_checksum_type"]
            





        ########################################################
        #### write out the updated .json file

        output_json_file_path = output_directory + json_file
        with open(output_json_file_path, "w") as output_json_file:
            json.dump(problem_instance, output_json_file)


    

    logging.info("done")
    




if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="a script to update all problem_instance files at once."
    )
    
    parser.add_argument(
        "-i", 
        "--input_dir", 
        type=str, 
        help="Specify directory for problem_instances (.json files)"
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

