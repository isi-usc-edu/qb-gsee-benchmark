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
import gzip
import shutil
import json
import copy
from urllib.parse import urlparse
import time
import sys
sys.path.append("../")



import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(
    "compute_all_LREs_scripts.log.txt",
    delay=False
)
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

    print("TODO: write this script!")
    script_is_finished=False
    assert script_is_finished, "this script needs work!"


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
        problem_instance_path = input_dir + problem_instance_file_name
        logging.info(f"parsing {problem_instance_path}")
        with open(problem_instance_path, "r") as jf:
            
            # load data from file as a Python dictionary object:
            # Try... because we may have non-JSON files that we will skip.
            try:
                problem_instance = json.load(jf)
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                continue # to next json file.


            problem_instance_uuid = problem_instance["problem_instance_uuid"]
            problem_instance_short_name = problem_instance["short_name"]
            logging.info(f"problem_instance UUID: {problem_instance_uuid}")
            logging.info(f"problem_instance short name: {problem_instance_short_name}")
            num_hams = len(problem_instance["instance_data"])
            logging.info(f"contains {num_hams} associated Hamiltonians.")

            for i in range(num_hams):
                num_supporting_files = len(problem_instance["instance_data"][i]["supporting_files"])
                logging.info(f"number of supporting files: {num_supporting_files}")

                for j in range(num_supporting_files):
                    # flush log buffer to log file
                    file_handler.flush()


                    fcidump_uuid = problem_instance["instance_data"][i]["supporting_files"][j]["instance_data_object_uuid"]
                    fcidump_url = problem_instance["instance_data"][i]["supporting_files"][j]["instance_data_object_url"]
                    logging.info(f"supporting data file UUID: {fcidump_uuid}.")
                    logging.info(f"supporting data file URL: {fcidump_url}.")

                    parsed_url = urlparse(fcidump_url)
                    fcidump_file_name = parsed_url.path.split("/")[-1]


                    #TODO: fix hacky way of only grabbing FCIDUMP files:
                    if "fcidump".lower() in fcidump_file_name.lower():
                        logging.info(f"assuming {fcidump_file_name} is an FCIDUMP file.")
                    else:
                        logging.info(f"assuming {fcidump_file_name} is NOT an FCIDUMP file.  SKIPPING!")
                        continue


                    # check the see if we have already processed FCIDUMP_UUID and have a resource estimate for it.
                    #==============================================================
                    # TODO... may need some ephemeral file output for incomplete/restarted work.




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
                    

                    # Decompress the FCIDUMP file (if detected)
                    #===============================================================
                    # TODO: fix hacky way of detecting the file is compressed:
                    if ".gz".lower() in fcidump_file_name.lower():
                        logging.info(f"decompressing file {fcidump_file_name}...")
                        fcidump_file_name_gz = fcidump_file_name
                        fcidump_file_name = fcidump_file_name.split(".gz")[0] # update file name with no .gz
                        
                        with gzip.open(fcidump_file_name_gz, "rb") as f_in:
                            with open(fcidump_file_name, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        os.remove(fcidump_file_name_gz)
                    else:
                        logging.info(f"assuming file {fcidump_file_name} is NOT compressed.")




                    # Calculate logical resource estimate for the FCIDUMP file
                    #===============================================================
                    logging.info(f"===============================================")
                    logging.info(f"calculating Logical Resource Estimate...")
                    LRE_start_time = datetime.datetime.now()
                    logging.info(f"TODO:  calculate the LRE!!!!!")
                    LRE_stop_time = datetime.datetime.now()
                    LRE_calc_time = (LRE_stop_time - LRE_start_time).total_seconds()
                    logging.info(f"LRE calculation run time (seconds): {LRE_calc_time}")


                    
                    # Clean up
                    #===============================================================
                    logging.info(f"deleting file {fcidump_file_name}.")
                    os.remove(fcidump_file_name)


                    # Append/Write out features .csv file
                    #===============================================================
                    # TODO
                    logging.info(f"TODO:  write data to somewhere... maybe solution file.")
                    

                    


    
    # Print overall time.
    #===============================================================
    overall_stop_time = datetime.datetime.now()
    logging.info(f"done.")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"overall stop time: {overall_stop_time}")
    logging.info(f"run time (seconds): {(overall_stop_time - overall_start_time).total_seconds()}")

    
    










if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="a script to calculate Logical Resource Estimates (LREs) for all problem_instance files.  Outputs are solution.uuid.json files."
    )
    
    parser.add_argument(
        "-i", 
        "--input_dir", 
        type=str, 
        required=True,
        help="Specify directory for problem_instances (.json files)"
    )

    parser.add_argument(
        "--LRE_config_file", 
        type=str, 
        required=True,
        help="A JSON file with configuration options and hyperparameters for LRE and a `solver` UUID."
    )

    parser.add_argument(
        "--sftp_username", 
        type=str, 
        required=True,
        help="username for SFTP server where FCIDUMP files are stored."
    )

    parser.add_argument(
        "--sftp_key_file", 
        type=str, 
        required=True,
        help="local/path/to/the/keyfile for the SFTP server (corresponding to sftp_username)"
    )

    args = parser.parse_args()
    main(args)


