#!/usr/bin/env python3


# Copyright 2023 L3Harris Technologies, Inc.

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



def move_errored_file(current_file_path: str, errored_files_directory: str):
    current_file_name = current_file_path.split("/")[-1]
    new_file_name = current_file_name + f".{time.time()}.ERROR" # append linux timestamp and .ERROR
    new_file_path = errored_files_directory + "/" + new_file_name
    logging.info(f"moving file to {new_file_path}")
    os.rename(current_file_path, new_file_path)





def main(args):
    input_directory = args.input
    errored_files_directory = args.errored_files_directory

    logging.info(f"started at: {datetime.datetime.utcnow().isoformat()}")
    logging.info(f"input directory: {input_directory}")
    logging.info(f"errored_files_directory file: {errored_files_directory}")

    
    json_files = os.listdir(input_directory)
    for json_file in json_files:
        json_file_path = input_directory + "/" + json_file
        logging.info(f"parsing {json_file_path}")
        with open(json_file_path, "r") as jf:
        
            # load data from file as a Python dictionary object:
            try:
                problem_instance = json.load(jf)
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                logging.info("moving file to errored files directory.")
                move_errored_file(
                    current_file_path=json_file_path,
                    errored_files_directory=errored_files_directory
                )
                continue # to next json file.
                        
            # pull out the $schema field as specified in the JSON file:
            try:
                schema_url = problem_instance["$schema"]
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                move_errored_file(
                    current_file_path=json_file_path,
                    errored_files_directory=errored_files_directory
                )
                continue # to next json file.
            
            # fetch the schema from the URL (https request):
            try:
                response = requests.get(schema_url)
                schema = response.json()
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                move_errored_file(
                    current_file_path=json_file_path,
                    errored_files_directory=errored_files_directory
                )
                continue # to next json file.

            # validate ... no output implies success!
            try:
                jsonschema.validate(
                    instance=problem_instance, 
                    schema=schema
                )
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                move_errored_file(
                    current_file_path=json_file_path,
                    errored_files_directory=errored_files_directory
                )
                continue # to next json file.



    logging.info("done")
    




if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate JSON schema for a set of .json files in a directory"
    )
    
    parser.add_argument(
        "-i", 
        "--input", 
        type=str, 
        help="Specify directory for problem_instances (.json files)"
    )
    parser.add_argument(
        "-e",
        "--errored_files_directory",
        type=str,
        help="The directory where errored files are moved to"
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
    else:
        main(args)

