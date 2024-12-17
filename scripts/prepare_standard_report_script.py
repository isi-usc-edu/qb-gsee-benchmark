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
import time
import pprint
from pathlib import Path
import json
from urllib.parse import urlparse
import uuid
import shutil
import sys
sys.path.append("../")
sys.path.append("../BubbleML/miniML")


import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import markdown
import weasyprint


import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(
    "prepare_standard_report_script.log.txt",
    delay=False
)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler , file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)





def load_json_files(search_dir) -> list:
    dict_list = []

    # this recurses through all subdirectories.
    for json_file in Path(search_dir).rglob("*.json"):
        with json_file.open("r") as file:
            try:
                data = json.load(file)
                dict_list.append(data)
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                continue # to next json file.
    return dict_list








def main(config):
   

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
    output_directory = f"standard_report_{timestamp}"
    os.mkdir(output_directory)


    overall_start_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"Starting to prepare the standard report...")
    logging.info(f"overall start time: {overall_start_time}")
    for k, v in config.items():
        logging.info(f"{k}: {v}")
    logging.info(f"Output directory: {output_directory}")

    performance_metrics_list = load_json_files(search_dir=config["performance_metrics_directory"])
    solutions_list = load_json_files(search_dir=config["solution_files_directory"])


    logging.info(f"merging Hamiltonian features and aggregated solver labels...")
    aggregated_solver_labels = pd.read_csv(config["aggregated_solver_labels_file"])
    logging.info(f"number of entries in {config['aggregated_solver_labels_file']}: {len(aggregated_solver_labels)}")
   
    num_tasks = aggregated_solver_labels["task_uuid"].nunique()
    logging.info(f"number tasks (unique Hamiltonians): {num_tasks}")


    Hamiltonian_features = pd.read_csv(config['hamiltonian_features_file'])
    num_features_calculated = len(Hamiltonian_features)
    logging.info(f"number of Hamiltonians we have features calculated for: {num_features_calculated}")
    
    
    # TODO: fix performance_metrics script so that `num_orbitals` is in the labels.csv file.
    # hacky workaround for now:
    aggregated_solver_labels = pd.merge(
        aggregated_solver_labels,
        pd.read_csv("num_orbitals_cheat_sheet.csv"),
        on="task_uuid",
        how="outer" # should throw a NaN in the sheet if this is incomplete.
    )



    if num_features_calculated != num_tasks:
        logging.warn(f"we have an inconsistency in the number of tasks and the number of features calculated!")
        logging.info(f"continuing...")
        

    data = pd.merge(
        aggregated_solver_labels,
        Hamiltonian_features,
        on="task_uuid",
        how="outer",
        suffixes=("", "_2") # some column headers may be duplicated.
    )
    
    data.to_csv(
        os.path.join(output_directory, f"data.csv"),
        index=False
    )



    # Histogram of number of orbitals
    #===============================================================
    plt.hist(
        data["num_orbitals"],
        bins=[10*x for x in range(int(max(data["num_orbitals"])/10+2))], # bin edges by 10
        edgecolor="black",
        alpha=0.7
    )
    plt.xlabel("Number of spatial orbitals")
    plt.ylabel("Number of Hamiltonians")
    plt.title("Histogram of Number of Spatial Orbitals")
    plt.savefig(os.path.join(output_directory,f"num_orbitals_histogram.png"))









    # Add content to standard report `output_directory/README.md`
    #===============================================================
    readme_file = os.path.join(output_directory, "README.md")
    with open(readme_file, "w") as file:
        file.write(f"# GSEE Benchmark Standard Report\n\n")
        file.write(f"Report created on {timestamp}\n\n")
        file.write(f"[https://github.com/isi-usc-edu/qb-gsee-benchmark](https://github.com/isi-usc-edu/qb-gsee-benchmark)\n\n")
        
        last_modified_time = time.ctime(os.path.getmtime(config["aggregated_solver_labels_file"]))
        file.write(f"Input data: {config['aggregated_solver_labels_file']}, last modified {last_modified_time}\n\n")
        
        last_modified_time = time.ctime(os.path.getmtime(config['hamiltonian_features_file']))
        file.write(f"Input data: {config['hamiltonian_features_file']}, last modified {last_modified_time}\n\n")
        if num_features_calculated < num_tasks:
            file.write(f"WARNING!  We only have features calculated for {num_features_calculated}/{num_tasks} Hamiltonians. This report is based on partial results!\n\n")
        TODO=999999
        file.write(f"## Problem Instance Summary Statistics\n\n")
        file.write(f"number of `problem_instances`: {data['problem_instance_uuid'].nunique()}\n\n")
        file.write(f"`problem_instance.json` with the most tasks: {TODO}\n\n")
        file.write(f"number of Hamiltonians (i.e., tasks): {num_tasks}\n\n")
        file.write(f"minimum number of orbitals: {np.min(data['num_orbitals'])}\n\n")
        file.write(f"median number of orbitals: {np.median(data['num_orbitals'])}\n\n")
        file.write(f"maximum number of orbitals: {np.max(data['num_orbitals'])}\n\n")
        file.write(f"![Number of orbitals histogram](num_orbitals_histogram.png)\n\n")
        


        file.write(f"## Solver Summary Statistics\n\n")
        file.write(f"number of unique participating solvers: {data['solver_uuid'].nunique()}\n\n")

        solver_uuid_list = data["solver_uuid"].unique()
        for solver_uuid in solver_uuid_list:

            # locate performance metrics for solver from list
            failed_to_locate_associated_performance_metrics_file = True
            for performance_metrics in performance_metrics_list:
                if performance_metrics["solver_uuid"] == solver_uuid:
                    failed_to_locate_associated_performance_metrics_file = False
                    break
            
            if failed_to_locate_associated_performance_metrics_file:
                file.write(f"### Solver {solver_uuid}\n\n")
                file.write(f"could not locate associated `performance_metrics.json` file.")
                continue # to next solver_uuid

            
            # we have located `performance_metrics.json` for solver_uuid
            write_out_fields = [
                "solver_short_name",
                "performance_metrics_uuid",
                "creation_timestamp",
                "top_level_results",
                "ml_metrics"                
            ]
            file.write(f"### Solver {performance_metrics['solver_short_name']}, {solver_uuid}\n\n")
            filtered_performance_metrics = {key: performance_metrics[key] for key in write_out_fields if key in performance_metrics}
            for k, v in filtered_performance_metrics.items():
                if not isinstance(v, dict):
                    file.write(f"{k}: {v}\n\n")
                else:
                    for kk, vv in v.items():
                        # only breaking out one more level of a dictionary
                        file.write(f"{kk}: {vv}\n\n")
            ## another option for writing out data:
            # file.write(f"```python\n")
            # file.write(pprint.pformat(filtered_performance_metrics, indent=4))
            # file.write(f"\n```\n")
                    
            file.write(f"TODO:  put some charts in here!")




    # convert README.md to an .html file and a .pdf file.
    #===============================================================
    with open(readme_file, "r") as md_file:
        md_content = md_file.read()

    readme_html_file = os.path.join(output_directory, "index.html")
    with open(readme_html_file, "w") as html_file:
        html_file.write(markdown.markdown(md_content))

    readme_pdf_file = os.path.join(
        output_directory,
        f"GSEE_benchmark_standard_report_{timestamp}.pdf"
    )
    weasyprint.HTML(readme_html_file).write_pdf(readme_pdf_file)
    



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
            A script to generate the standard report.  
            The report files are placed in a nearby directory 
            called `standard_report_<timestamp>`.
        """
    )
    
    parser.add_argument(
        "config_file", 
        type=str, 
        help="A JSON file that defines some input files and directories."
    )

    args = parser.parse_args()
    with open(args.config_file,"r") as file:
        config = json.load(file)

    main(config)


