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



import argparse
import requests

import logging
logging.basicConfig(level=logging.INFO)

import datetime

import json
import sys
sys.path.append("../")
import os

import pandas as pd

import json
import requests

from qb_gsee_benchmark.utils import iso8601_timestamp





def main(args):
    input_directory = args.input_dir
    output_directory = args.output_dir

    logging.info(f"started at: {iso8601_timestamp()}")
    logging.info(f"input directory: {input_directory}")
    logging.info(f"output directory: {output_directory}")

    
    json_files = os.listdir(input_directory)
    for json_file in json_files:
        json_file_path = input_directory + json_file
        if os.path.isfile(json_file_path):
            logging.info(f"parsing {json_file_path}")
            with open(json_file_path, "r") as jf:

                # load data from file as a Python dictionary object:
                try:
                    data = json.load(jf)
                except Exception as e:
                    logging.error(f'Error: {e}', exc_info=True)
                
            for k, v in data.items():
                try:
                    timestamp = pd.to_datetime(v)
                    if timestamp.tz is None:
                        # no timezone....add it.
                        timestamp = timestamp.to_pydatetime()
                        timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
                        new_v = timestamp.isoformat()

                        logging.info(f"about to replace a value...")
                        logging.info(f"old value:  {v}")
                        logging.info(f"new value: {new_v}")
                        choice = input(f"type 'k' to proceed.  any other input to stop.")
                        if choice == "k":
                            v = new_v
                        else:
                            logging.info("user has decided to exit script early.")
                            sys.exit(1)
                    else:
                        logging.info(f"found a valid timestamp:  {k}:{v}")
                        

                except Exception as e:
                    logging.error(f'Error: {e}', exc_info=True)
                    logging.info(f"attempted to convert {v} into a timestamp.")


                
                        

        
            #### write out the updated .json file
            output_json_file_path = output_directory + json_file
            with open(output_json_file_path, "w") as output_json_file:
                json.dump(data, output_json_file)


    

    logging.info("done")
    




if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="a script to update lots of JSON files at once."
    )
    
    parser.add_argument(
        "-i", 
        "--input_dir", 
        type=str, 
        required=True,
        help="Specify directory for problem_instances (.json files)"
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        required=True,
        help="The directory where updated .json files are moved to."
    )

    args = parser.parse_args()
    main(args)

