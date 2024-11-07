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
import copy
from urllib.parse import urlparse
import sys
sys.path.append("../")


import pandas as pd
from Hamiltonian_features.experimental.fast_double_factorization_features.fcidump_to_ham_features_csv import compute_ham_features_csv



import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler("compute_all_ham_features_script.log.txt")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler , file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)



import paramiko # for SSH/SFTP
def fetch_file_from_sftp(
        url=None,
        local_path=None,
        ppk_path=None,
        username=None,
        port=22
    ):
    """TODO: docstring

    Args:
        url (_type_, optional): _description_. Defaults to None.
        local_path (_type_, optional): _description_. Defaults to None.
        ppk_path (_type_, optional): _description_. Defaults to None.
        username (_type_, optional): _description_. Defaults to None.
        port (_type_, optional): _description_. Defaults to 22.
    """


    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    remote_path = parsed_url.path.lstrip("/")

    try:
        # Create an SSH client
        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect using the private key file (.ppk)
            client.connect(
                hostname=hostname, 
                port=port, 
                username=username, 
                key_filename=ppk_path
            )

            # Open an SFTP session
            with client.open_sftp() as sftp:
                sftp.get(remote_path, local_path)

        logging.info(f"File fetched successfully from {hostname}")
    except Exception as e:
        logging.error(f"Error: {e}")



























def main(args):


    overall_start_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"start time: {overall_start_time}")
    logging.info(f"input directory: {args.input}")
    logging.info(f"output file: {args.output}")

    
    input_dir = args.input_dir


    list_of_all_ham_features = []

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
                fcidump_url = problem_instance["instance_data"][i]["supporting_files"]["instance_data_object_url"]
                logging.info(f"supporting data file UUID: {fcidump_uuid}.")
                logging.info(f"supporting data file URL: {fcidump_url}.")

                parsed_url = urlparse(fcidump_url)
                fcidump_file_name = parsed_url.path.split("/")[-1]


                #TODO: hacky way to only grab FCIDUMP files:
                if "fcidump".lower() in fcidump_file_name.lower():
                    logging.info(f"assuming {fcidump_file_name} is an FCIDUMP file.")
                else:
                    logging.info(f"assuming {fcidump_file_name} is NOT an FCIDUMP file.  SKIPPING!")
                    continue

                # SFTP download the FCIDUMP file
                #===============================================================
                logging.info(f"SFTP downloading file {fcidump_url}...")
                fetch_file_from_sftp(
                    url=fcidump_url,
                    username=args.sftp_username,
                    ppk_path=args.sftp_key_file, 
                    local_path=fcidump_file_name,
                    port=22
                )
                



                # Calculate features of the FCIDUMP file
                #===============================================================
                logging.info(f"===============================================")
                logging.info(f"calculating Hamiltonian features...")
                ham_features = {}
                ham_features_start_time = datetime.datetime.now()
                ham_features = compute_ham_features_csv(
                    filename=fcidump_file_name,
                    save=False,
                    csv_filename=None,
                    verbose_logging=True
                )
                ham_features_stop_time = datetime.datetime.now()
                logging.info(f"run time (seconds): {(ham_features_stop_time - ham_features_start_time).total_seconds()}")



                ham_features["problem_instance_uuid"] = problem_instance_uuid
                ham_features["problem_instance_short_name"] = problem_instance_short_name
                ham_features["fcidump_file_name"] = fcidump_file_name
                ham_features["fcidump_uuid"] = fcidump_uuid
                ham_features["fcidump_url"] = fcidump_url
                list_of_all_ham_features.append(copy.deepcopy(ham_features))


                

                

                

    # Write out features .csv file
    #===============================================================
    logging.info(f"===============================================")
    logging.info(f"writing data to features {args.output_file}")
    df = pd.DataFrame(list_of_all_ham_features)
    df.to_csv(args.output_file, index=False)



    # Print overall time.
    #===============================================================
    overall_stop_time = datetime.datetime.now()
    logging.info(f"done.")
    logging.info(f"start time: {overall_start_time}")
    logging.info(f"stop time: {overall_stop_time}")
    logging.info(f"run time (seconds): {(overall_stop_time - overall_start_time).total_seconds()}")

    
    










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