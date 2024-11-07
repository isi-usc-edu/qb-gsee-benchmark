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
import json


import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(args.log_file, mode="a") # mode "a" for append.
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler , file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)



import paramiko # for SSH/SFTP




def main(args):


    start_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"start time: {start_time}")
    logging.info(f"input directory: {args.input}")
    logging.info(f"output file: {args.output}")

    
    input_dir = args.input_dir


    problem_instance_files = os.listdir(input_dir)
    logging.info(f"parsing {len(problem_instance_files)} files in the input directory")

    for problem_instance_file_name in problem_instance_files:
        problem_instance_path = input_dir + problem_instance_file_name
        logging.info(f"parsing {problem_instance_path}")
        with open(problem_instance_path, "r") as jf:
            problem_instance = json.load(jf)
        
            problem_instance_uuid = problem_instance["problem_instance_uuid"]
            problem_instance_short_name = problem_instance["short_name"]
            logging.info(f"problem_instance UUID: {problem_instance_uuid}")
            logging.info(f"problem_instance short name: {problem_instance_short_name}")
            logging.info(f"contains {len(problem_instance["instance_data"])} associated Hamiltonians.")

            for i in range(len(problem_instance["instance_data"])):
                fcidump_uuid = problem_instance["instance_data"][i]["supporting_files"]["instance_data_object_uuid"]
                logging.info(f"supporting data file UUID: {fcidump_uuid}.")
                fcidump_url = problem_instance["instance_data"][i]["supporting_files"]["instance_data_object_url"]

                #TODO: hacky way to only grab FCIDUMP files:
                if "fcidump".lower() in fcidump_url.lower():
                    logging.info(f"assuming {fcidump_url} is an FCIDUMP file.")
                else:
                    logging.info(f"assuming {fcidump_url} is NOT an FCIDUMP file.  SKIPPING!")
                    continue

                # SFTP download the FCIDUMP file
                #===============================================================
                logging.info(f"SFTP downloading file {fcidump_url}...")
                logging.info(f"TODO!")


                # Calculate features of the FCIDUMP file
                #===============================================================
                logging.info(f"===============================================")
                logging.info(f"calculating Hamiltonian features...")
                logging.info(f"TODO!")                

                

    # Write out features .csv file
    #===============================================================
    output_file = args.output
    logging.info(f"===============================================")
    logging.info(f"writing data to features {output_file}")
    logging.info(f"TODO!")



    # Fin
    #===============================================================
    stop_time = datetime.datetime.now()
    logging.info(f"done.")
    logging.info(f"start time: {start_time}")
    logging.info(f"stop time: {stop_time}")
    logging.info(f"run time (seconds): {(stop_time - start_time).total_seconds()}")

    
    










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
        "--output_file",
        type=str,
        help="The name of the output .csv file."
    )

    parser.add_argument(
        "--sftp_username", 
        type=str, 
        help="username for SFTP server where FCIDUMP files are stored."
    )

    parser.add_argument(
        "--sftp_key_file", 
        type=str, 
        help="local/path/to/the/keyfile for the SFTP server (corresponding to sftp_username)"
    )

    args = parser.parse_args()
    main(args)