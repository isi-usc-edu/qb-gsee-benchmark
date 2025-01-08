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


import gzip
import os
import shutil
from urllib.parse import urlparse

from typing import Any
import logging
import json
import datetime
from pathlib import Path

import pandas as pd
import numpy as np

import paramiko
from pyscf.tools import fcidump


def _fetch_file_from_sftp(
    url: str, local_path: str, ppk_path: str, username: str, port=22
):

    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    remote_path = parsed_url.path.lstrip("/")

    with paramiko.SSHClient() as client:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=hostname,
            port=port,
            username=username,
            key_filename=ppk_path,
        )

        with client.open_sftp() as sftp:
            print(f"Downloading {remote_path} to {local_path}...")
            sftp.get(remote_path, local_path)


def retrieve_fcidump_from_sftp(url: str, username: str, ppk_path: str, port=22) -> dict:
    filename = os.path.basename(urlparse(url).path)
    _fetch_file_from_sftp(
        url=url, username=username, ppk_path=ppk_path, local_path=filename, port=port
    )
    fcidump_filename = filename.replace(".gz", "")
    with gzip.open(filename, "rb") as f_in:
        with open(fcidump_filename, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    fci = fcidump.read(filename=fcidump_filename)
    os.remove(filename)
    os.remove(fcidump_filename)
    return fci




def iso8601_timestamp() -> str:
    """Returns the current UTC time as an ISO 8601 formatted string.

    Returns:
        str: The current UTC time in ISO 8601 format.

    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()






def load_json_files(search_dir: str) -> list:
    """Searches through `search_dir` and subdirectories to read in all JSON files.

    Args:
        search_dir (str): relative/path/to/directory

    Returns:
        list: A list of Python `dict` objects from each JSON file read in.
    """

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
    




def data_frame_vlookup(df: pd.DataFrame, 
        lookup_value: Any,
        lookup_value_column_header: str,
        find_value_column_header: str
    ) -> Any:
    """A simple `vlookup` operation for a Pandas `DataFrame`.

    Args:
        df (pd.DataFrame): _description_
        lookup_value (Any): The value to find.
        lookup_value_column_header (str): The column to find `lookup_value` in.
        find_value_column_header (str): The column to locate the corresponding value in.

    Returns:
        Any: The corresponding value in the `find_value_column_header` column.
    """
    assert len(df[df[lookup_value_column_header]==lookup_value]) == 1, \
        f"Found zero or more than one instance of `{lookup_value}` in column `{lookup_value_column_header}`."
    
    return df.loc[df[lookup_value_column_header]==lookup_value, find_value_column_header].values[0]









class BenchmarkData:
    def __init__(self,
            hamiltonian_features_csv_file_name: str,
            utility_estimation_csv_file_name: str,
            problem_instances_directory: str,
            solution_files_directory: str,
            performance_metrics_directory: str
        ):
        """Initializes a `BenchmarkData` object that collates the data currently in the repository.

        Args:
            hamiltonian_features_csv_file_name (str): relative/path/to/hamiltonian_features.csv
            utility_estimation_csv_file_name (str): relative/path/to/utility_estimation.csv
            problem_instances_directory (str): relative/path/to/problem_instance directory
            solution_files_directory (str): relative/path/to/solution_files directory
            performance_metrics_directory (str): relative/path/to/performance_metrics directory
            output_csv_file_name (str, optional): if specified, the data will be written out as a .csv file.
        """

        self.hamiltonian_features = pd.read_csv(hamiltonian_features_csv_file_name)
        self.utility_estimation_data = pd.read_csv(utility_estimation_csv_file_name)
        self.problem_instance_list = load_json_files(search_dir=problem_instances_directory)
        self.solution_list = load_json_files(search_dir=solution_files_directory)
        self.performance_metrics_list = load_json_files(search_dir=performance_metrics_directory)
        self.solver_df = self.identify_unique_participating_solvers()
        self.aggregated_solver_labels_df = self.calculate_solver_success_labels()     


    def __repr__(self) -> str:
        return f"benchmark data with {len(self.problem_instance_list)} problem instances, and {len(self.solution_list)} solutions, submitted by {len(self.solver_df)} solvers."
        

    def identify_unique_participating_solvers(self) -> pd.DataFrame:
        """Returns a `pd.DataFrame` of solvers participating.  The columns are `solver_uuid` and `solver_short_name`. 
        
        Depends:
            `BenchmarkData.solution_list` (list): A list of solutions (dictionary objects), most likely produced by `load_json_files()`. 

        Returns:
            pd.DataFrame: Columns are `solver_uuid` and `solver_short_name`.  Each unique `solver_uuid` only appears once.
        """


        solvers_list = pd.DataFrame(columns=["solver_short_name","solver_uuid"])
        for solution in self.solution_list:
            solver_uuid = solution["solver_details"]["solver_uuid"]
            if solver_uuid in solvers_list["solver_uuid"].values:
                # the solver (by UUID) is already in the list.
                continue
            else:
                # the solver (by UUID) is NOT in the list.  add it.
                solver_short_name = solution["solver_details"]["solver_short_name"]
                solvers_list.loc[len(solvers_list)] = [solver_short_name, solver_uuid]
        return solvers_list
    
    

    def locate_solution_results_by_task_uuid_and_solver_uuid(self,
            solver_uuid: str,
            task_uuid: str,
        ) -> tuple:
        """Search `BenchmarkData.solution_list` for specific results object by `solver_uuid` and `task_uuid`

        Depends:
            BenchmarkData.solution_list (list): A list of solutions (dictionary objects), most likely produced by `load_json_files()`. 

        Args:
            solver_uuid (str): UUID in 8-4-4-4-12 format as a string.
            task_uuid (str): UUID in 8-4-4-4-12 format as a string.

        Returns:
            tuple: (results: dict, solution_uuid: str)
        """
        results = None # init as None and update if we find it.
        solution_uuid = None # init as None and update if we find it.
        for solution in self.solution_list:
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






    def flatten_benchmark_data(
            self,
            output_csv_file_name: str = None
        ) -> pd.DataFrame:
        """Return a pd.DataFrame object with collated benchmark data from the various sources.

        Depends:
            on almost all of the attributes of BenchmarkData.

        Args:
            output_csv_file_name (str, optional): If specified, the data will be written to file. Defaults to None.

        Returns:
            pd.DataFrame: a large, flat data frame containing collated data by `task_uuid` from all JSON files and other inputs.
        """

        util_est_cols = ["task_uuid","Utility NPV $", "Utility NVP lower bound $", "Utility NVP upper bound $"]        
        df = pd.merge(
            self.hamiltonian_features,
            self.utility_estimation_data[util_est_cols],
            on="task_uuid",
            how="outer"
        )

        df = pd.merge(
            self.aggregated_solver_labels_df,
            df,
            on="task_uuid",
            how="outer",
        )

        if output_csv_file_name is not None:
            df.to_csv(output_csv_file_name, index=False)

        return df


    def calculate_ml_scores(self) -> dict:
        """TODO: migrate miniML.py workflow into this method.  Note that running miniML.py takes about 15 minutes.

        Returns:
            dict: _description_
        """
        pass


    def calculate_solver_success_labels(self) -> pd.DataFrame:
        """Construct a pd.DataFrame containing the success/failure of each solver against `task_uuids`.
        
        Depends:
            BenchmarkData.solver_df (pd.DataFrame): Columns are `solver_uuid` and `solver_short_name`.  Each unique `solver_uuid` only appears once.
            BenchmarkData.problem_instance_list (list): A list of problem instances (dictionary objects), most likely produced by `load_json_files()`. 
            BenchmarkData.solution_list (list): A list of solutions (dictionary objects), most likely produced by `load_json_files()`. 
            BenchmarkData.hamiltonian_features (pd.DataFrame): A data frame containing a variety of interesting features about the Hamiltonians (by `task_uuid`).

        Returns:
            pd.DataFrame: A large, flat data frame containing the success/failure labels for the solvers against `task_uuids`.
        """

        aggregated_solver_labels_columns = [
            "solver_short_name",
            "solver_uuid",
            "solution_uuid",
            "problem_instance_short_name",
            "problem_instance_uuid",
            "task_uuid",
            "instance_data_object_uuid",
            "instance_data_object_url",
            "num_orbitals",
            "time_limit_seconds",
            "accuracy_tol",
            "reference_energy",
            "calendar_due_date",
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
        aggregated_solver_labels = pd.DataFrame(columns=aggregated_solver_labels_columns)

        for problem_instance in self.problem_instance_list:
            problem_instance_uuid = problem_instance["problem_instance_uuid"]
            problem_instance_short_name = problem_instance["short_name"]
            for task in problem_instance["tasks"]:
                num_supporting_files = len(task["supporting_files"])
                task_uuid = task["task_uuid"]
                for supporting_file in task["supporting_files"]:
                    instance_data_object_uuid = supporting_file["instance_data_object_uuid"]
                    instance_data_object_url = supporting_file["instance_data_object_url"]
                    parsed_url = urlparse(instance_data_object_url)
                    instance_data_object_file_name = parsed_url.path.split("/")[-1]
                    #TODO: improve hacky way of only grabbing FCIDUMP files:
                    if "fcidump".lower() in instance_data_object_file_name.lower():
                        # TODO: note we are assuming there is ONLY ONE FCIDUMP file for the Hamiltonian.
                        break
                    else:
                        # NOTE: this may be different type of file... such as a checkpoint CHK file.
                        continue
                for solver_uuid in self.solver_df["solver_uuid"].values:
                    solver_short_name = data_frame_vlookup(
                        df=self.solver_df,
                        lookup_value=solver_uuid,
                        lookup_value_column_header="solver_uuid",
                        find_value_column_header="solver_short_name"
                    )

                    results, solution_uuid = self.locate_solution_results_by_task_uuid_and_solver_uuid(
                        solver_uuid=solver_uuid,
                        task_uuid=task_uuid                        
                    )


                    # init (reset) other parameters to None, then update below.
                    num_orbitals = None
                    time_limit_seconds = None
                    accuracy_tol = None
                    reference_energy = None
                    calendar_due_date = None

                    # init (reset) all reported parameters as None, then update below.
                    attempted = None
                    solved_within_run_time = None
                    solved_within_accuracy_requirement = None
                    overall_run_time_seconds = None 
                    is_resource_estimate = None
                    num_logical_qubits = None
                    num_shots = None
                    num_T_gates_per_shot = None
                    submitted_by_calendar_due_date = None
                    label = None


                    # determine if it's a resource estimate
                    is_resource_estimate = None
                    for solution in self.solution_list:
                        if solution["solution_uuid"] == solution_uuid:
                            is_resource_estimate = solution["is_resource_estimate"]
                            break


                    num_orbitals = data_frame_vlookup(
                        df=self.hamiltonian_features,
                        lookup_value=task_uuid,
                        lookup_value_column_header="task_uuid",
                        find_value_column_header="n_orbs" # TODO: standardize on num_orbitals
                    )
                    


                    # task-specific requirements from `problem_instance`
                    calendar_due_date = problem_instance["calendar_due_date"] # may be None/null per .json.
                    time_limit_seconds = task["requirements"]["time_limit_seconds"]
                    accuracy_tol = task["requirements"]["accuracy"]
                    try:
                        reference_energy = task["requirements"]["reference_energy"]
                        # TODO:  account for differences in units.  E.g., Hartree vs. kCal/mol vs. other.
                    except Exception as e:
                        logging.error(f'Error: {e}', exc_info=True)
                        logging.warning(f"warning!  no reference_energy specified in task {task_uuid}")
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

                        # TODO: issue-#94:  physical resource estimate (PRE) not calculated for LRE
                        if is_resource_estimate:
                            try:
                                overall_run_time_seconds = results["run_time"]["overall_time"]["seconds"]
                                solved_within_run_time = overall_run_time_seconds <= time_limit_seconds
                            except Exception as e:
                                logging.error(f'Error: {e}', exc_info=True)
                                logging.error("physical resource estimate does not provide overall run time.")
                                overall_run_time_seconds = None
                                solved_within_run_time = False
                                attempted = False
                                solved_within_accuracy_requirement = True # always true for resource estimates.
                                label = None
                        else:
                            # not a resource estimate...
                            overall_run_time_seconds = results["run_time"]["overall_time"]["seconds"]
                            solved_within_run_time = overall_run_time_seconds <= time_limit_seconds

                        
                        
                        # TODO: check calendar due date submission.
                        submitted_by_calendar_due_date = True 
                            


                        if is_resource_estimate:
                            num_logical_qubits = results["quantum_resources"]["logical"]["num_logical_qubits"]
                            num_shots = results["quantum_resources"]["logical"]["num_shots"]
                            num_T_gates_per_shot = results["quantum_resources"]["logical"]["num_T_gates_per_shot"]
                            solved_within_accuracy_requirement = True # always true.  assume LREs solve to accuracy.
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
                                logging.warning(f"warning!  no energy target specified in task {task_uuid}")
                                solved_within_accuracy_requirement = False
                            
                            # TODO: issue-44.  handle case when more than one solution submitted by
                            # one solver.  for now assume solutions were submitted by due date.
                            # TODO: check calendar due date submission.
                            
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
                        "num_orbitals":num_orbitals,
                        "time_limit_seconds":time_limit_seconds,
                        "accuracy_tol":accuracy_tol,
                        "reference_energy":reference_energy,
                        "calendar_due_date":calendar_due_date,
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
                    aggregated_solver_labels = pd.concat(
                        [aggregated_solver_labels, new_row],
                        ignore_index=True
                    )
        
        return aggregated_solver_labels
                    
