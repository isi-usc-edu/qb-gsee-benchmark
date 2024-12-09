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
from pathlib import Path
import json
from urllib.parse import urlparse
import uuid
import sys
sys.path.append("../")
sys.path.append("../BubbleML/miniML")


# miniML methods from this repo:
# NOTE: renaming `main` function as `miniML` during import.
from miniML import main as miniML


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
    df = solver_list[solver_list["solver_uuid"] == solver_uuid]
    return df["solver_short_name"].iloc[0]


     



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
    
    # TODO: logging.info(f"the version of the ML metrics script is: {ml_metrics_version}")





    solution_list = load_json_files(search_dir=args.solution_file_dir)
    problem_instance_list = load_json_files(search_dir=args.problem_instance_dir)
    
    logging.info(f"number of problem_instance files: {len(problem_instance_list)}")
    logging.info(f"number of solution files: {len(solution_list)}")
    


    solver_list = identify_unique_participating_solvers(solution_list=solution_list)
    logging.info(f"number of unique solvers participating (submitting solution.json files): {len(solver_list)}")
    logging.info(f"solver list:  {solver_list}")


    aggregated_results_columns = [
        "solver_short_name",
        "solver_uuid",
        "solution_uuid",
        "problem_instance_short_name",
        "problem_instance_uuid",
        "task_uuid",
        "instance_data_object_uuid",
        "instance_data_object_url",
        "attempted",
        "solved_within_run_time",
        "solved_within_accuracy_requirement",
        "overall_run_time_seconds",
        "is_resource_estimate",
        "num_logical_qubits",
        "num_shots",
        "num_T_gates_per_shot",
        "submitted_by_calendar_due_date",
        "label" # label True/False, that the Hamiltonian was solved.
    ]
    aggregated_results = pd.DataFrame(columns=aggregated_results_columns)

    for problem_instance in problem_instance_list:
        problem_instance_uuid = problem_instance["problem_instance_uuid"]
        problem_instance_short_name = problem_instance["short_name"]
        
        for task in problem_instance["tasks"]:
            num_supporting_files = len(task["supporting_files"])
            logging.info(f"number of supporting files: {num_supporting_files}")

            task_uuid = task["task_uuid"]

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


                # determine if it's a resource estimate
                is_resource_estimate = None
                for solution in solution_list:
                    if solution["solution_uuid"] == solution_uuid:
                        is_resource_estimate = solution["is_resource_estimate"]
                        break



                # task-specific requirements
                time_limit_seconds = task["requirements"]["time_limit_seconds"]
                accuracy_tol = task["requirements"]["accuracy"]
                try:
                    reference_energy = task["requirements"]["reference_energy"]
                    # TODO:  account for differences in units.  E.g., Hartree vs. kCal/mol vs. other.
                except Exception as e:
                    logging.error(f'Error: {e}', exc_info=True)
                    logging.info(f"warning!  no reference_energy specified in task {task_uuid}")
                    reference_energy = None


                if results is None:
                    # the solver did NOT submit a solution file for the problem_instance or Hamiltonian.
                    # mark it as failed.  TODO:  do something more nuanced with non-attempted problems in the future.
                    is_resource_estimate = None
                    attempted = False
                    solved_within_run_time = False
                    solved_within_accuracy_requirement = False
                    label = False # overall:  solved==False
                    submitted_by_calendar_due_date = False
                    overall_run_time_seconds = None 
                else:
                    # calculate simple performance metrics for the solver against
                    # this Hamiltonian
                    attempted = True 

                    overall_run_time_seconds = results["run_time"]["overall_time"]["seconds"]
                    solved_within_run_time = overall_run_time_seconds <= time_limit_seconds

                    if is_resource_estimate:
                        num_logical_qubits = results["quantum_resources"]["logical"]["num_logical_qubits"]
                        num_shots = results["quantum_resources"]["logical"]["num_shots"]
                        num_T_gates_per_shot = results["quantum_resources"]["logical"]["num_T_gates_per_shot"]
                        solved_within_accuracy_requirement = True # always true.  assume LREs solve to accuracy.
                        submitted_by_calendar_due_date = None 
                    else:
                        # NOT a logical resource estimate.
                        num_logical_qubits = None
                        num_shots = None
                        num_T_gates_per_shot = None
    
                        reported_energy = results["energy"]
                        try:
                            solved_within_accuracy_requirement = bool(np.abs(reported_energy - reference_energy) < accuracy_tol)
                            # TODO:  account for differences in units.  E.g., Hartree vs. kCal/mol vs. other.
                        except Exception as e:
                            logging.error(f'Error: {e}', exc_info=True)
                            logging.info(f"warning!  no energy target specified in task {task_uuid}")
                            solved_within_accuracy_requirement = False
                        
                        calendar_due_date = problem_instance["calendar_due_date"]
                        if calendar_due_date is None: 
                            # no due date specified in problem_instance
                            submitted_by_calendar_due_date = True
                        else:
                            # TODO: issue-44.  handle case when more than one solution submitted by
                            # one solver.  for now assume solutions were submitted by due date.
                            submitted_by_calendar_due_date = True 
                        
                    label = solved_within_run_time and solved_within_accuracy_requirement
                        


                # new row for each solver_uuid/task_uuid
                new_row = pd.DataFrame([{
                    "solver_short_name":solver_short_name,
                    "solver_uuid":solver_uuid,
                    "solution_uuid":solution_uuid,
                    "problem_instance_short_name":problem_instance_short_name,
                    "problem_instance_uuid":problem_instance_uuid,
                    "task_uuid":task_uuid,
                    "instance_data_object_uuid":instance_data_object_uuid,
                    "instance_data_object_url":instance_data_object_url,
                    "attempted":attempted,
                    "solved_within_run_time":solved_within_run_time,
                    "solved_within_accuracy_requirement":solved_within_accuracy_requirement,
                    "overall_run_time_seconds":overall_run_time_seconds,
                    "is_resource_estimate":is_resource_estimate,
                    "num_logical_qubits":num_logical_qubits,
                    "num_shots":num_shots,
                    "num_T_gates_per_shot":num_T_gates_per_shot,
                    "submitted_by_calendar_due_date":submitted_by_calendar_due_date,
                    "label":label # label True/False, that the Hamiltonian was solved.
                }])
                logging.info(f"added a row for solver {solver_short_name}, task {task_uuid}")
                aggregated_results = pd.concat([aggregated_results, new_row], ignore_index=True)
                #aggregated_results.loc[len(aggregated_results)] = new_row # add to list of results.



    # we have completed filling out the aggregated_results DataFrame.
    # write results to .csv file
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
        solver_labels_file_name = f"solver_labels.{solver_short_name}.{solver_uuid}.csv"
        solver_labels.to_csv(solver_labels_file_name)

        
        try:
            logging.info(f"calculating ML scores for solver {solver_short_name}/{solver_uuid}...")

            ham_features_file="../Hamiltonian_features/experimental/fast_double_factorization_features/Hamiltonian_features.csv"
            solvability_ratio, f1_score = miniML(argparse.Namespace(
                ham_features_file=ham_features_file,
                config_file="../BubbleML/miniML/miniML_config.json",
                solver_uuid=solver_uuid,
                solver_labels_file=solver_labels_file_name,
                verbose=False
            ))
            ml_scores[solver_uuid] = {
                "solvability_ratio":solvability_ratio,
                "f1_score":list(f1_score),
                "ml_metrics_calculator_version":1
            }
        except Exception as e:
            logging.error(f'Error: {e}', exc_info=True)
            logging.info(f"bummer!  setting ml_scores to `None`.")
            ml_scores[solver_uuid] = {
                "solvability_ratio":None,
                "f1_score":None,
                "ml_metrics_calculator_version":1
            }



        



    

    # Write out a performance_metrics.uuid.json file for each solver
    # ===============================================================
    for solver_uuid in solver_list["solver_uuid"].values:
        solver_results_df = aggregated_results[aggregated_results["solver_uuid"]==solver_uuid]
        solver_short_name = get_solver_short_name(
            solver_uuid=solver_uuid,
            solver_list=solver_list
        )



        # Boilerplate metadata:
        # ===============================================================
        performance_metrics = {}
        performance_metrics["$schema"] = "https://raw.githubusercontent.com/isi-usc-edu/qb-gsee-benchmark/main/schemas/performance_metrics.schema.0.0.1.json"
        performance_metrics_uuid = str(uuid.uuid4())
        performance_metrics["performance_metrics_uuid"] = performance_metrics_uuid
        performance_metrics["solver_short_name"] = solver_short_name
        performance_metrics["solver_uuid"] = solver_uuid
        performance_metrics["creation_timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # ML metrics object:
        # ===============================================================
        performance_metrics["ml_metrics"] = ml_scores[solver_uuid] 

        
        # Top-level aggregated performance metrics:
        # ===============================================================
        # filter aggregated results to ONLY the solver we are currently working with:
        performance_metrics["top_level_results"] = {
                "number_of_problem_instances": aggregated_results["problem_instance_uuid"].nunique(),
                "number_of_problem_instances_attempted": None, #calculated below...
                "number_of_problem_instances_solved": None, #calculated below...
                "number_of_tasks": aggregated_results["task_uuid"].nunique(),
                "number_of_tasks_attempted": len(solver_results_df["attempted"]),
                "number_of_tasks_solved": len(solver_results_df["label"]),
                "number_of_tasks_solved_within_run_time_limit": len(solver_results_df["solved_within_run_time"]),
                "number_of_tasks_solved_within_accuracy_threshold": len(solver_results_df["solved_within_accuracy_requirement"]),
                "max_run_time_of_attempted_tasks": None, #calculated below...,
                "sum_of_run_time_of_attempted_tasks":None, #calculated below...,
        }
        
        
        # number_of_problem_instances_attempted...
        problem_instance_uuid_list = aggregated_results["problem_instance_uuid"].unique()
        count_number_problem_instances_attempted = 0
        for problem_instance_uuid in problem_instance_uuid_list:
            # filter df to only problem instance
            df_filtered = solver_results_df[solver_results_df["problem_instance_uuid"]==problem_instance_uuid]
            num_tasks = len(df_filtered)
            num_attempted_tasks = len(df_filtered["attempted"])
            # must attempt ALL task to "attempt" the problem_instance.
            if num_tasks == num_attempted_tasks:
                count_number_problem_instances_attempted += 1
        performance_metrics["top_level_results"]["number_of_problem_instances_attempted"] \
            = count_number_problem_instances_attempted


        # number_of_problem_instances_solved...
        problem_instance_uuid_list = aggregated_results["problem_instance_uuid"].unique()
        count_number_problem_instances_solved = 0
        for problem_instance_uuid in problem_instance_uuid_list:
            # filter df to only problem instance
            df_filtered = solver_results_df[solver_results_df["problem_instance_uuid"]==problem_instance_uuid]
            num_tasks = len(df_filtered)
            num_solved_tasks = len(df_filtered["label"])
            # must attempt ALL task to "attempt" the problem_instance.
            if num_tasks == num_solved_tasks:
                count_number_problem_instances_solved += 1
        performance_metrics["top_level_results"]["number_of_problem_instances_solved"] \
            = count_number_problem_instances_solved


        # max_run_time_of_attempted_tasks...
        # filter down to only task that were attempted:
        df_filtered = solver_results_df[solver_results_df["attempted"]]
        performance_metrics["top_level_results"]["max_run_time_of_attempted_tasks"] \
            = max(df_filtered["overall_run_time_seconds"])

        # sum_of_run_time_of_attempted_tasks...
        # filter down to only task that were attempted:
        df_filtered = solver_results_df[solver_results_df["attempted"]]
        performance_metrics["top_level_results"]["sum_of_run_time_of_attempted_tasks"] \
            = sum(df_filtered["overall_run_time_seconds"])











        # Performance metrics by problem_instance:
        # ===============================================================
        
        # init as empty list.
        performance_metrics["results_by_problem_instance"] = []
        
        problem_instance_uuid_list = aggregated_results["problem_instance_uuid"].unique()
        for problem_instance_uuid in problem_instance_uuid_list:
            df_filtered = solver_results_df[solver_results_df["problem_instance_uuid"]==problem_instance_uuid]
            logging.info(f"problem_instance_uuid: {problem_instance_uuid}")
            logging.info(f"number of tasks: {len(df_filtered)}")
            
            # TODO: PRIORITY:  issue #44: handle situation where one solver has more than one solution_uuid for a single problem_uuid
            assert df_filtered["solution_uuid"].nunique() <= 1, "issue #44:  we have more than one solution_uuid for a (solver_uuid,problem_uuid) pair."
            x = {
                "problem_instance_uuid":problem_instance_uuid,
                "solution_uuid": df_filtered["solution_uuid"].unique()[0], # should only be one solution_uuid.  see issue #44.
                "number_of_tasks": len(df_filtered),
                "number_of_tasks_attempted": len(df_filtered[df_filtered["attempted"]]),
                "number_of_tasks_solved_within_runtime_limit":len(df_filtered["solved_within_run_time"]),
                "number_of_tasks_solved_within_accuracy_requirement":len(df_filtered["solved_within_accuracy_requirement"]),
                "number_of_tasks_solved":len(df_filtered["label"]),
                "sum_of_run_time_of_attempted_tasks":None, # updated below...
                "max_run_time_of_attempted_tasks":None, # updated below...
                "solution_submitted_by_due_date":\
                    df_filtered["submitted_by_calendar_due_date"].values[0] # should only be one.  see issue #44.
                    
            }
            if len(df_filtered[df_filtered["attempted"]]) > 0:
                logging.info(f"number of attempted tasks: {len(df_filtered[df_filtered['attempted']])}")
                x["sum_of_run_time_of_attempted_tasks"] \
                    = sum(df_filtered[df_filtered["attempted"]]["overall_run_time_seconds"])
                
                x["max_run_time_of_attempted_tasks"] \
                    = max(df_filtered[df_filtered["attempted"]]["overall_run_time_seconds"])
            else:
                logging.info(f"it seems the solver did not attempt ANY of the tasks in problem_instance_uuid {problem_instance_uuid}")

            performance_metrics["results_by_problem_instance"].append(x)






        # Performance metrics by task:
        # ===============================================================
        # init as empty list.
        performance_metrics["results_by_task"] = []
        
        task_uuid_list = aggregated_results["task_uuid"].unique()
        for task_uuid in task_uuid_list:
            df_filtered = solver_results_df[solver_results_df["task_uuid"]==task_uuid]
            # TODO: issue #44:  handle case where more than one solution_uuid per (solver_uuid, task_uuid) present.
            assert df_filtered["solution_uuid"].nunique() <= 1, "issue #44:  we have more than one solution_uuid for a (solver_uuid,task_uuid) pair."
            assert len(df_filtered) == 1, "issue #44:  we have more than one solution_uuid for a (solver_uuid,task_uuid) pair."
            x = {
                "task_uuid":task_uuid,
                "problem_instance_uuid":df_filtered["problem_instance_uuid"].values[0], # should only be one...issue #44.
                "instance_data_object_uuid":df_filtered["instance_data_object_uuid"].values[0],
                "attempted":df_filtered["attempted"].values[0],
                "solved_within_run_time":df_filtered["solved_within_run_time"].values[0],
                "solved_within_accuracy_requirement":df_filtered["solved_within_accuracy_requirement"].values[0],
                "solved":df_filtered["label"].values[0],
                "overall_run_time_seconds":None #calculated below
            }
            if x["attempted"]:
                x["overall_run_time_seconds"] = df_filtered["overall_run_time_seconds"].values[0]
            performance_metrics["results_by_task"].append(x)



        # Write out performance_metrics.json file:
        # ===============================================================
        performance_metrics_file_name = args.performance_metrics_dir 
        performance_metrics_file_name += f"performance_metrics.{solver_short_name}.{solver_uuid}.{performance_metrics_uuid}.json"
        with open(performance_metrics_file_name, "w") as output_file:
            json.dump(performance_metrics, output_file, indent=4)
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


