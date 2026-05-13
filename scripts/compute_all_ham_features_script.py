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


from qb_gsee_benchmark.utils import fetch_file_from_sftp
from qb_gsee_benchmark.utils import load_json_files
from qb_gsee_benchmark.utils import download_file_via_https
from qb_gsee_benchmark.utils import compare_file_sha1sum
from qb_gsee_benchmark.utils import decompress_file
from qb_gsee_benchmark.utils import determine_url_protocol

import os
import argparse
import datetime
import gzip
import shutil
import json
import random
import copy
from urllib.parse import urlparse
import time
from pathlib import Path
import sys
sys.path.append("../")
sys.path.append("../Hamiltonian_features/experimental/fast_double_factorization_features")

from pyscf.tools import fcidump
import pandas as pd
from Hamiltonian_features.experimental.fast_double_factorization_features.fcidump_to_ham_features_csv import compute_ham_features_csv
# from Hamiltonian_features.experimental.fast_double_factorization_features.compute_ham_features import compute_hypergraph_ham_features



import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(
    "compute_all_ham_features_script.log.txt",
    delay=False
)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler , file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)










def read_in_csv_database(database_csv_file_name):
    if not os.path.exists(database_csv_file_name):
        logging.info(f"database file does not exist. A new file will be created.")
        df_database = None
    else:
        df_database = pd.read_csv(database_csv_file_name)
        logging.info(f"number of entries in {database_csv_file_name}:  {len(df_database)}")
    
    return df_database # may be None.




def append_to_csv_database(
        df: pd.DataFrame,
        csv_database_file_name: str
    ):

    df.to_csv(
        csv_database_file_name,
        mode="a", #append
        header=(not os.path.exists(csv_database_file_name)), # write headers if starting a new file.
        index=False
    )




def time_check(overall_start_time):
    t = datetime.datetime.now()
    logging.info(f"this script has been running for {(t - overall_start_time).total_seconds()/3600:.2f} hours.")













def main(args):

    overall_start_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"input directory: {args.input_dir}")
    logging.info(f"Hamiltonian features file: {args.ham_features_file}")

    
    input_dir = args.input_dir

    # create backup Hamiltonian_features.csv file
    if os.path.exists(args.ham_features_file):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
        back_up_file_name = args.ham_features_file + ".backup-" + timestamp + ".csv"
        logging.info(f"creating back up file {back_up_file_name}.")
        shutil.copy2(args.ham_features_file, back_up_file_name)


    problem_instance_list = load_json_files(args.input_dir)
    logging.info(f"loaded {len(problem_instance_list)} problem instances.")


    finished_all_hamiltonians = False # init
    max_num_orbitals = 20 # init.  we will complete the "small" Hamiltonians first
    # and increase the `max_num_orbitals` later to finish off the large Hamiltonians.
    
    while not finished_all_hamiltonians:
        max_num_orbitals += 10 # increase the size of Hamiltonians considered in each loop.
        finished_all_hamiltonians = True # reset... update to `False` if we skip one due to its large size.
        
        # random.shuffle(problem_instance_files) # randomize order of problem instances processed.

        for problem_instance in problem_instance_list:
            problem_instance_uuid = problem_instance["problem_instance_uuid"]
            problem_instance_short_name = problem_instance["short_name"]
            logging.info(f"problem_instance UUID: {problem_instance_uuid}")
            logging.info(f"problem_instance short name: {problem_instance_short_name}")
            num_tasks = len(problem_instance["tasks"])
            logging.info(f"contains {num_tasks} associated tasks (Hamiltonians).")

            for task in problem_instance["tasks"]:

                task_uuid = task["task_uuid"]
                logging.info(f"task UUID: {task_uuid}...")

                num_orbitals = None # reset

                try:
                    num_orbitals = task["features"]["num_orbitals"]
                except Exception as e:
                    logging.info(f"problem instance does not explicitly state the number of orbitals.")



                if num_orbitals is not None:
                    # try to update the num_orbitals_cheat_sheet
                    num_orbitals_df = read_in_csv_database("num_orbitals_cheat_sheet.csv") # assuming file exists.
                    if task_uuid not in num_orbitals_df["task_uuid"].values:
                        append_to_csv_database(
                            df=pd.DataFrame(
                                    [
                                        {
                                            "task_uuid":task_uuid,
                                            "num_orbitals":num_orbitals
                                        }
                                    ]
                                ),
                            csv_database_file_name="num_orbitals_cheat_sheet.csv"
                        )

                
                if num_orbitals is None:
                    # the problem_instance did not explicity state the number of orbitals
                    logging.info(f"checking the num_orbitals_cheat_sheet...")
                    num_orbitals_df = read_in_csv_database("num_orbitals_cheat_sheet.csv") # assuming file exists.
                    if task_uuid in num_orbitals_df["task_uuid"].values:
                        num_orbitals = num_orbitals_df.loc[num_orbitals_df["task_uuid"] == task_uuid, "num_orbitals"].values[0]
                

                if num_orbitals is None:
                    logging.info(f"we don't know how many orbitals are in this Hamiltonian yet...")
                else:
                    if num_orbitals > max_num_orbitals:
                        logging.info(f"number of orbitals:  {num_orbitals}")
                        logging.info(f"too many orbitals!  we are only considering max_num_orbitals {max_num_orbitals} at this stage.")
                        logging.info(f"skipping this Hamiltonian for now now.  We will revisit it later.")
                        finished_all_hamiltonians = False # reset this to False, so we increase max_num_orbitals and try again later.
                        logging.info(f"moving on ...")
                        continue
                    else:
                        logging.info(f"attempting to process the Hamiltonian...")
                   
                
                
                
                num_supporting_files = len(task["supporting_files"])
                logging.info(f"number of supporting files: {num_supporting_files}")
                for supporting_file in task["supporting_files"]:


                    file_handler.flush() # flush log buffer to log file

                    fcidump_uuid = supporting_file["instance_data_object_uuid"]
                    fcidump_url = supporting_file["instance_data_object_url"]
                    logging.info(f"supporting data file UUID: {fcidump_uuid}.")
                    logging.info(f"supporting data file URL: {fcidump_url}.")

                    if not supporting_file["is_fcidump_file"]:
                        logging.info("Supporting file is NOT an FCIDUMP file.  Moving to next file...")
                        continue


                    # check the see if we have already processed instance_data_object_uuid
                    # TODO: also compare version of the metrics calculation to see if we need to update.
                    #==============================================================

                    # re-read ham_features_df_database ... we may have updated it.
                    ham_features_df_database = read_in_csv_database(args.ham_features_file)
                    if ham_features_df_database is None:
                        # empty features database... we will process the FCIDUMP
                        logging.info(f"Hamiltonian features database is empty.")
                    else:
                        if fcidump_uuid in ham_features_df_database["instance_data_object_uuid"].values:
                            logging.info(f"instance_data_object_uuid {fcidump_uuid} is already in the feature database.  Skipping it!")
                            continue
                        else:
                            logging.info(f"did NOT find instance_data_object_uuid {fcidump_uuid} in database.")
                            
                    # proceed to process the FCIDUMP file...
                    time_check(overall_start_time)
                    logging.info(f"Processing instance_data_object_uuid {fcidump_uuid} ...")

                    # Download the file:            
                    protocol = determine_url_protocol(fcidump_url)
                    if protocol == "https":
                        fcidump_file_path = download_file_via_https(url=fcidump_url)
                    elif protocol == "sftp":
                        fcidump_file_path = os.path.basename(urlparse(fcidump_url).path)
                        fcidump_file_path = fetch_file_from_sftp(
                            url=fcidump_url,
                            local_path=fcidump_file_path,
                            ppk_path=sftp_key_file,
                            username=sftp_username
                        )
                    else:
                        raise Exception(f"Unsupported {protocol=}.  HTTPS and SFTP are supported.")
                    logging.info(f"downloaded FCIDUMP file {fcidump_file_path}.")

                    

                    # compare the sha1sum to that reported in the problem instance
                    if supporting_file["instance_data_checksum_type"] != "sha1sum":
                        raise Exception(f"Unsupported file checksum {supporting_file['instance_data_checksum_type']}.  `sha1sum` is supported.")
                    same_checksum = compare_file_sha1sum(
                        file_path=fcidump_file_path, 
                        comparison_hash=supporting_file["instance_data_checksum"]
                    )
                    if not same_checksum:
                        raise Exception(f"File sha1sum does not match that reported in the problem instance.")

                    # decompress the file
                    fcidump_file_path = decompress_file(fcidump_file_path)

                    # read the FCIDUMP file
                    data = fcidump.read(filename=fcidump_file_path)
                    
                    if num_orbitals is not None:
                        assert num_orbitals == data['NORB'], "Error: the number or orbitals listed in the FCIDUMP file doesn't match the number listed in the problem instance JSON file!";


                    
                    if num_orbitals is None:
                        # problem instance didn't specify... AND the cheat sheet
                        # didn't have the value... we will update the cheat sheet.

                        # set the value of num_orbitals to that listed in the FCIDUMP file
                        num_orbitals = data['NORB']
                        logging.info(f"num_orbitals: {num_orbitals}")    
                        
                        # update the cheat sheet
                        append_to_csv_database(
                            df=pd.DataFrame(
                                    [
                                        {
                                            "task_uuid":task_uuid,
                                            "num_orbitals":num_orbitals
                                        }
                                    ]
                                ),
                            csv_database_file_name="num_orbitals_cheat_sheet.csv"
                        )
                    
                    
                    # TODO:
                    # This is unfortunate. The FCIDUMP file for FeMoco-54e-54o
                    # published by Microsoft at https://aka.ms/fcidump/nitrogenase-54e-54o
                    # does not have the MS2 parameter in it.  So we have this
                    # hacky way of inserting it here.  C'est la vie.
                    if "nitrogenase-54e-54o.fcidump" in fcidump_file_path:
                        if "MS2" not in data.keys():
                            logging.warning("WARNING! we are updating the FCIDUMP for Femoco-54e-54o by inserting the MS2 parameter!!!")
                            text = Path(fcidump_file_path).read_text()

                            # MS2 is 2*M_S (The spin projection quantum number multiplied by 2)
                            # M_S = 1/2 (N_alpha - N_beta)
                            # N_alpha - N_beta is spin S.  
                            # from table 5 from the supplemental
                            # information:  https://www.pnas.org/action/downloadSupplement?doi=10.1073%2Fpnas.1619152114&file=pnas.1619152114.sapp.pdf
                            # we have that S=0.  So then M_S=0 and MS2=2*M_S=0.
                            if "MS2=0," not in text:
                                target = "NORB=54," # we will insert the "MS2=0," property after the "NORB=54," property
                                assert target in text, "Error trying to fixup FCIDUMP file for nitrogenase-54e-54o."
                                text = text.replace(target, target + "MS2=0,", 1)
                                Path(fcidump_file_path).write_text(text)
                                    


                    
                    # Calculate features of the FCIDUMP file
                    #===============================================================
                    logging.info(f"===============================================")
                    logging.info(f"calculating Hamiltonian features...")
                    ham_features = {}
                    ham_features_start_time = datetime.datetime.now()
                    ham_features = compute_ham_features_csv(
                        filename=fcidump_file_path,
                        save=False, # do not save
                        csv_filename="WE_ARE_NOT_SAVING_THE_FILE_HERE.csv",
                        verbose_logging=True
                    )
                    ham_features_stop_time = datetime.datetime.now()
                    ham_features_calc_time = (ham_features_stop_time - ham_features_start_time).total_seconds()
                    logging.info(f"Hamiltonian features calculation run time (seconds): {ham_features_calc_time}")



                    ham_features["problem_instance_uuid"] = problem_instance_uuid
                    ham_features["problem_instance_short_name"] = problem_instance_short_name
                    ham_features["task_uuid"] = task_uuid
                    ham_features["instance_data_object_uuid"] = fcidump_uuid
                    ham_features["instance_data_object_file_name"] =  os.path.basename(fcidump_file_path)
                    ham_features["instance_data_object_url"] = fcidump_url
                    ham_features["date_of_calculation"] = str(ham_features_stop_time)
                    ham_features["version_of_features_calculation_script"] = 1
                    ham_features["ham_features_calc_time"] = ham_features_calc_time


                    # Back up df_eigs to a file. 
                    # Sometimes the array is shortened in string representation...
                    # we want all the eigs!
                    df_eigs_file = f"df_eigs.{fcidump_uuid}.bin"
                    ham_features["df_eigs"].tofile(f"double_factorized_eigs.{fcidump_uuid}.bin")
                    logging.info(f"wrote df_eigs to file: {df_eigs_file}")


                    # Clean up
                    #===============================================================
                    logging.info(f"deleting file {fcidump_file_path}.")
                    os.remove(os.path.basename(fcidump_file_path))


                    # Append/Write out features .csv file
                    #===============================================================
                    logging.info(f"appending data to file {args.ham_features_file}")
                    append_to_csv_database(
                        df=pd.DataFrame([ham_features]),
                        csv_database_file_name=args.ham_features_file
                    )
                    
                    time_check(overall_start_time)
                    

                        


    
    # Print overall time.
    #===============================================================
    overall_stop_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"the overall script is done!")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"overall stop time: {overall_stop_time}")
    logging.info(f"run time (seconds): {(overall_stop_time - overall_start_time).total_seconds()}")
    logging.info(f"===============================================")
    
    
    










if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""A script to calculate the features of all 
            the Hamiltonians referenced in the problem_instance JSON files.  The output
            is the `Hamiltonian_features.csv` file.
        """
    )
    
    parser.add_argument(
        "-i", 
        "--input_dir", 
        type=str, 
        required=True,
        help="The directory that contains the problem_instance JSON files."
    )

    parser.add_argument(
        "--ham_features_file",
        type=str,
        required=True,
        help="""The file name of the Hamiltonian features (.csv) file.  If the 
           file already exists, new data rows will be added to it.
           A backup copy is also made at the beginning of the script."""
    )

    parser.add_argument(
        "--sftp_username", 
        type=str, 
        required=True,
        help="username for the SFTP server where FCIDUMP files are stored."
    )

    parser.add_argument(
        "--sftp_key_file", 
        type=str, 
        required=True,
        help="local/path/to/the/keyfile for the SFTP server corresponding to sftp_username."
    )

    args = parser.parse_args()
    main(args)


