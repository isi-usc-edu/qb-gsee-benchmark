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
from urllib.parse import urlparse
import uuid
import sys
sys.path.append("../")


# miniML methods from this repo:
# NOTE: renaming `main` function as `miniML` during import.
from BubbleML.miniML.miniML import main as miniML


import numpy as np
import pandas as pd


import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(
    "compute_all_performance_metrics_script.log.txt",
    delay=False
)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler , file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)





def load_json_files(search_dir) -> list:
    dict_list = []
    files = os.listdir(search_dir)
    for f in files:
        f_path = search_dir + f
        with open(f_path, "r") as json_file:
            try:
                dict_list.append(json.load(json_file))
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                continue # to next json file.
    return dict_list
    


def locate_solution_results_by_instance_data_object_uuid(
        instance_data_object_uuid,
        solution
    ) -> dict:
    for solution_datum in solution["solution_data"]:
        test_uuid = solution_datum["instance_data_object_uuid"]
        if test_uuid.lower() == instance_data_object_uuid.lower():
            return solution_datum
        
def locate_solution_results_by_task_uuid_and_solver_uuid(
        solver_uuid,
        task_uuid,
        solution_list
    ) -> tuple:
    results = None # init as None and update if we find it.
    solution_uuid = None # init as None and update if we find it.
    for solution in solution_list:
        test_solver_uuid = solution["solver_details"]["solver_uuid"]
        if test_solver_uuid.lower() == solver_uuid.lower():
            # we have matched on the solver...
            for solution_datum in solution["solution_data"]:
                test_task_uuid = solution_datum["task_uuid"]
                if test_task_uuid.lower() == task_uuid.lower():
                    # we have mached on task_uuid as well
                    results = solution_datum
                    solution_uuid = solution["solution_uuid"]
                    return results, solution_uuid

    # if the function has made it this far, we have not found a match
    # and (None, None) will be returned. 
    return results, solution_uuid
    



def identify_unique_participating_solvers(
        solution_list
    ) -> pd.DataFrame:
    solvers_list = pd.DataFrame(columns=["solver_short_name","solver_uuid"])
    for solution in solution_list:
        solver_uuid = solution["solver_details"]["solver_uuid"]
        if solver_uuid in solvers_list["solver_uuid"].values:
            # the solver (by UUID) is already in the list.
            continue
        else:
            # the solver (by UUID) is NOT in the list.  add it.
            solver_short_name = solution["solver_details"]["solver_short_name"]
            solvers_list.loc[len(solvers_list)] = [solver_short_name, solver_uuid]
    return solvers_list





def get_solver_short_name(solver_uuid, solver_list) -> str:
    return solver_list[solver_list["solver_uuid"] == solver_uuid].iloc[0]


     



def locate_problem_instance_by_UUID(
        problem_instance_uuid,
        problem_instances_list
    ) -> dict:
    for problem_instance in problem_instances_list:
        test_uuid = problem_instance["problem_instance_uuid"]
        if test_uuid.lower() == problem_instance_uuid.lower():
            return problem_instance





def main(args):
   



    overall_start_time = datetime.datetime.now()
    logging.info(f"===============================================")
    logging.info(f"Starting to calculate all performance metrics...")
    logging.info(f"overall start time: {overall_start_time}")
    logging.info(f"problem_instance directory: {args.problem_instance_dir}")
    logging.info(f"solution_file directory: {args.solution_file_dir}")
    logging.info(f"performance_metrics directory: {args.performance_metrics_dir}")
    logging.info(f"the version of the ML metrics script is: {ml_metrics_version}")





    solution_list = load_json_files(search_dir=args.solution_file_dir)
    problem_instance_list = load_json_files(search_dir=args.problem_instance_dir)


    solver_list = identify_unique_participating_solvers(solution_list=solution_list)
    logging.info(f"number of unique solvers participating (submitting solution.json files): {len(solver_list)}")
    logging.info(f"solver list:  {solver_list}")


    aggregated_results = pd.DataFrame(columns=[
        "solver_short_name",
        "solver_uuid",
        "solution_uuid",
        "problem_instance_uuid",
        "task_uuid",
        "instance_data_object_uuid",
        "instance_data_object_url"
        "attempted",
        "solved_within_run_time",
        "solved_within_accuracy_requirement",
        "label" # label True/False, that the Hamiltonian was solved.
    ])

    for problem_instance in problem_instance_list:
        problem_instance_uuid = problem_instance["problem_instance_uuid"]
        
        for task in problem_instance["tasks"]:
            num_supporting_files = len(task["supporting_files"])
            logging.info(f"number of supporting files: {num_supporting_files}")

            task_uuid = problem_instance["task"]

            for supporting_file in task["supporting_files"]:
            
                instance_data_object_uuid = supporting_file["instance_data_object_uuid"]
                instance_data_object_url = supporting_file["instance_data_object_url"]
                logging.info(f"supporting data file UUID: {instance_data_object_uuid}.")
                logging.info(f"supporting data file URL: {instance_data_object_url}.")
                parsed_url = urlparse(instance_data_object_url)
                instance_data_object_file_name = parsed_url.path.split("/")[-1]


                #TODO: improve hacky way of only grabbing FCIDUMP files:
                if "fcidump".lower() in instance_data_object_file_name.lower():
                    logging.info(f"assuming {instance_data_object_file_name} is THE FCIDUMP file.")
                    # TODO: note we are assuming there is ONLY ONE FCIDUMP file for the Hamiltonian.
                    break
                else:
                    logging.info(f"assuming {instance_data_object_file_name} is NOT an FCIDUMP file.  SKIPPING!")
                    # NOTE: this may be different type of file... such as a checkpoint CHK file.
                    continue

            for solver_uuid in solver_list["solver_uuid"].values:
                solver_short_name = get_solver_short_name(solver_uuid, solver_list)

                results, solution_uuid = locate_solution_results_by_task_uuid_and_solver_uuid(
                    solver_uuid=solver_uuid,
                    task_uuid=task_uuid,
                    solution_list=solution_list
                )
                if results is None:
                    # the solver did NOT submit a solution file for the problem_instance or Hamiltonian.
                    # mark it as failed.  TODO:  do something more nuanced with non-attempted problems in the future.
                    attempted=False
                    solved_within_run_time=False
                    solved_within_accuracy_requirement=False
                    label=False # solved=False
                else:
                    # calculate simple performance metrics for the solver against
                    # this Hamiltonian
                    attempted = True

                    overall_run_time_seconds = results["run_time"]["overall_time"]["seconds"]
                    time_limit_seconds = task["time_limit_seconds"]
                    solved_within_run_time = overall_run_time_seconds <= time_limit_seconds

                    reported_energy = results["energy"]
                    accuracy_tol = task["accuracy"]
                    energy_target = task["energy_target"]
                    solved_within_accuracy_requirement = np.abs(reported_energy - energy_target) < accuracy_tol
                    
                    label = solved_within_run_time and solved_within_accuracy_requirement
                        


            
            new_row = [
                solver_short_name,
                solver_uuid,
                solution_uuid,
                problem_instance_uuid,
                task_uuid,
                instance_data_object_uuid,
                instance_data_object_url,
                attempted,
                solved_within_run_time,
                solved_within_accuracy_requirement,
                label # label True/False, that the Hamiltonian was solved.
            ]
            logging.info(f"{pd.DataFrame(new_row)}") # just for printout.
            aggregated_results.loc[len(aggregated_results)] = new_row # add to list of results.




    # interim results output to .csv file
    # ==============================================================
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
    aggregated_labels_file_name = f"aggregated_solver_labels_{timestamp}.csv"
    aggregated_results.to_csv(aggregated_labels_file_name)
    logging.info(f"wrote interim output to {aggregated_labels_file_name}")
    logging.info(f"=============================================")
    





    # Calculate ML scores for each solver
    # ===============================================================
    ml_scores = {}
    for solver_uuid in solver_list["solver_uuid"].values:
        solver_short_name = get_solver_short_name(
            solver_uuid=solver_uuid,
            solver_list=solver_list
        )
        # filter aggregated results to ONLY the solver (by solver_uuid)
        solver_labels = aggregated_results[aggregated_results["solver_uuid"]==solver_uuid]
        
        # write out the labels to a .csv file... one file for each solver.
        solver_labels_file_name = f"solver.{solver_short_name}.{solver_uuid}.labels.csv"
        solver_labels.to_csv(solver_labels_file_name)

        logging.info(f"calculating ML scores for solver {solver_short_name}/{solver_uuid}...")
        ml_solvability_score, f1_score = miniML(argparse.Namespace(
            ham_features_file="../Hamiltonian_features/experimental/Hamiltonian_features.csv",
            config_file="../BubbleML/miniML/miniML_config.json",
            solver_uuid=solver_uuid,
            solver_labels_file=solver_labels_file_name,
            verbose=False
        ))
        ml_scores[solver_uuid] = {
            "ml_solvability_score":ml_solvability_score,
            "f1_score":f1_score    
        }



        



    

    # Write out a performance_metrics.uuid.json file for each solver
    # ===============================================================
    for solver_uuid in solver_list["solver_uuid"].values:
        solver_short_name = get_solver_short_name(
            solver_uuid=solver_uuid,
            solver_list=solver_list
        )

        # Boilerplate metadata:
        # ===============================================================
        performance_metrics = {}
        performance_metrics["$schema"] = "https://raw.githubusercontent.com/isi-usc-edu/qb-gsee-benchmark/main/schemas/performance_metrics.schema.0.0.1.json"
        performance_metrics["performance_metrics_uuid"] = str(uuid.uuid4())
        performance_metrics["solver_short_name"] = solver_short_name
        performance_metrics["solver_uuid"] = solver_uuid
        performance_metrics["creation_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # ML metrics object:
        # ===============================================================
        performance_metrics["ml_metrics"] = {
            "ml_metrics_calculator_version": 1, # TODO, update this programmatically
            "solvability_ratio": ml_scores[solver_uuid]["ml_solvability_score"],
            "f1_score": ml_scores[solver_uuid]["f1_score"]    
        }
        performance_metrics["aggregate_metrics"] = {} # TODO
        performance_metrics["metrics_for_each_problem_instance"] = {} # TODO

        # Top-level aggregated performance metrics:
        # ===============================================================
        # TODO


        # Performance metrics by problem_instance:
        # ===============================================================
        # TODO


        # Performance metrics by task:
        # ===============================================================
        # TODO


        # Write out performance_metrics.json file:
        # ===============================================================
        performance_metrics_file_name = args.performance_metrics_dir 
        performance_metrics_file_name += f"performance_metrics.{solver_short_name}.{solver_uuid}.json"
        with open(performance_metrics_file_name, "w") as jo:
            json.dump(performance_metrics, jo, indent=4)
        logging.info(f"wrote file: {performance_metrics_file_name}")





    
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
            a script to calculate performance metrics for all solvers 
            represented in solution.json files.  (The solver must have submitted
            a solution.json file to be included in this output.)
        """
    )
    
    parser.add_argument(
        "--problem_instance_dir", 
        type=str, 
        required=True,
        help="Specify directory for problem_instances (.json files).  This is input."
    )

    parser.add_argument(
        "--solution_file_dir", 
        type=str, 
        required=True,
        help="Specify directory for solution.json files.  This is input."
    )

    parser.add_argument(
        "--performance_metrics_dir", 
        type=str, 
        required=True,
        help="""
            Specify directory for performance_metrics.json files.  
            Freshly calculated performance_metrics.json files will be 
            placed here.
        """
    )

    args = parser.parse_args()
    main(args)


