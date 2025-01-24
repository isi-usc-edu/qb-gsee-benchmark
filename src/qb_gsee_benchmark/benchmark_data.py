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


import os
from urllib.parse import urlparse
from datetime import datetime

import argparse
from typing import Any
import logging
import json
from pathlib import Path
from uuid import uuid4

import requests

import pandas as pd
import numpy as np


from qb_gsee_benchmark.utils import load_json_files
from qb_gsee_benchmark.utils import clear_or_create_output_directory
from qb_gsee_benchmark.utils import find_dict_with_matching_kv_pair
from qb_gsee_benchmark.utils import data_frame_vlookup
from qb_gsee_benchmark.utils import iso8601_timestamp
from qb_gsee_benchmark.utils import validate_json
from qb_gsee_benchmark.mini_ml import MiniML




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
        """

        self.timestamp = iso8601_timestamp()
        self.datestamp = datetime.fromisoformat(self.timestamp).strftime("%Y%m%d")

        # store file paths and directories for posterity:
        self.hamiltonian_features_csv_file_name = hamiltonian_features_csv_file_name
        self.utility_estimation_csv_file_name = utility_estimation_csv_file_name
        self.problem_instances_directory = problem_instances_directory
        self.solution_files_directory = solution_files_directory
        self.performance_metrics_directory = performance_metrics_directory

        # read in data:
        self.hamiltonian_features = pd.read_csv(hamiltonian_features_csv_file_name)
        self.utility_estimation_data = pd.read_csv(utility_estimation_csv_file_name)
        self.problem_instance_list = load_json_files(search_dir=problem_instances_directory)
        self.solution_list = load_json_files(search_dir=solution_files_directory)
        self.performance_metrics_list = None # read in or calculated later.
        # TODO:  migrate performance metrics calculation to method below. self.performance_metrics_list = load_json_files(search_dir=performance_metrics_directory)
        

        # Calculations and data collation:
        # Order of operations matters!
        #1:
        self.identify_unique_participating_solvers()
        #2:
        self.calculate_solver_success_labels()
        #3:
        self.flatten_benchmark_data()
        #4:
        self.calculate_sponsor_resource_estimates()












    def __repr__(self) -> str:
        return f"benchmark data with {len(self.problem_instance_list)} problem instances, and {len(self.solution_list)} solutions, submitted by {len(self.solvers_df)} solvers."
        








    def validate_all_json_objects(
            self,
            local_resolver_directory: str
        ) -> None:
        """TODO: docstring.  no errors implies success!!
        """
        
        lists = [
            ("problem instances", self.problem_instance_list),
            ("solutions", self.solution_list),
            ("resource estimates", self.sponsor_resource_estimate_list),
            ("performance metrics", self.performance_metrics_list)
        ]
        for listy in lists:
            name = listy[0]
            the_list = listy[1]
            if the_list is None:
                print(f"{name} is None.")
                # this may happen if performance metrics have not yet been calculated.
            elif the_list ==[]:
                print(f"{name} is empty.")
                # this may happen if there are no resource estimates.
            else:
                print(f"validating {name}...")
                schema_url = the_list[0]["$schema"]
                schema = requests.get(schema_url).json()
                for json_dict in the_list:
                    validate_json(
                        json_dict=json_dict,
                        schema=schema,
                        local_resolver_directory=local_resolver_directory
                    )
            









    def identify_unique_participating_solvers(self) -> pd.DataFrame:
        """Construct the `BenchmarkData.solvers_df` (`pd.DataFrame`) and `BenchmarkData.solvers_dict` attributes containing the solvers participating. 
        
        Depends:
            `BenchmarkData.solution_list` (`list`): A list of solutions (dictionary objects), most likely produced by `load_json_files()`. 

        Returns:
            `pd.DataFrame`: The `BenchmarkData.solvers_df` attribute is updated in place.  It is also returned for other usage.
        """

        # init
        solvers_dict = {}
        solvers_df = pd.DataFrame(columns=["solver_short_name","solver_uuid"])
        
        for solution in self.solution_list:
            solver_uuid = solution["solver_details"]["solver_uuid"]
            if solver_uuid in solvers_df["solver_uuid"].values:
                # the solver (by UUID) is already in the list.
                continue
            else:
                # the solver (by UUID) is NOT in the list.  add it.
                solver_short_name = solution["solver_details"]["solver_short_name"]
                solvers_df.loc[len(solvers_df)] = [solver_short_name, solver_uuid]
                solvers_dict[solver_uuid] = solution["solver_details"]
        
        self.solvers_df = solvers_df
        self.solvers_dict = solvers_dict
        return solvers_df
    
















    def locate_solution_results_by_task_uuid_and_solver_uuid(self,
            solver_uuid: str,
            task_uuid: str,
        ) -> tuple:
        """Search `BenchmarkData.solution_list` attribute for specific results object by `solver_uuid` and `task_uuid`

        Depends:
            BenchmarkData.solution_list (list): A list of solutions (dictionary objects), most likely produced by `load_json_files()`. 

        Args:
            solver_uuid (str): UUID in 8-4-4-4-12 format as a string.
            task_uuid (str): UUID in 8-4-4-4-12 format as a string.

        Returns:
            tuple: `results` (`dict`), `solution_uuid` (`str`)
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


















    def to_csv(self, output_csv_file_name: str):
        """Write all of the current BenchmarkData to a large, flat CSV file.

        Depends:
            BenchmarkData.all_data_df (pd.DataFrame): Should be up-to-date. It should have been created during `.__init__()`.

        Args:
            output_csv_file_name (str): relative/path/to/the/output CSV file.
        """
        self.all_data_df.to_csv(output_csv_file_name, index=False)























    def flatten_benchmark_data(
            self,
        ) -> pd.DataFrame:
        """Updates the `BenchmarkData.all_data_df` (DataFrame) attribute with collated benchmark data from the various sources.

        Depends:
            on almost all of the attributes of BenchmarkData.

        Returns:
            pd.DataFrame: The `BenchmarkData.all_data_df` is updated in place.  It is also returned for other usage.
        """

        util_est_cols = ["task_uuid","Utility NPV $", "Utility NVP lower bound $", "Utility NVP upper bound $"]        
        df = pd.merge(
            self.hamiltonian_features,
            self.utility_estimation_data[util_est_cols],
            on="task_uuid",
            how="outer"
        )
        df.fillna(0.0, inplace=True) # fill NaN in Utility estimates with zeros.

        df = pd.merge(
            self.aggregated_solver_labels_df,
            df,
            on="task_uuid",
            how="outer",
            suffixes=("","_duplicate")
        )
        self.all_data_df = df 
        return self.all_data_df
























    def calculate_ml_scores(
            self,
        ) -> dict:
        """TODO: `miniML.py` takes about 15 minutes.

        Returns:
            dict: _description_
        """

        ml_scores_dict = {}
        ml_models_dict = {}
        for solver_uuid in self.solvers_dict:
            df = self.aggregated_solver_labels_df
            df = df[df["solver_uuid"]==solver_uuid] # filter df to only solver_uuid
            df = df[~df["reference_energy"].isna()] # filter to only entries with reference energy specified.
            # df = df[df["attempted"]==True] # filter to attempted tasks/Hamiltonians

            try:
                mini_ml_model = MiniML(
                    solver_labels_by_task_uuid=df,
                    hamiltonian_features_by_task_uuid=self.hamiltonian_features    
                )
                ml_scores_dict[solver_uuid] = {
                    "solvability_ratio":mini_ml_model.ml_solvability_ratio,
                    "f1_score":list(mini_ml_model.f1_score),
                    "ml_metrics_calculator_version":1
                }
            except Exception as e:
                logging.error(f'Error: {e}', exc_info=True)
                mini_ml_model = "Model could not be calculated."
                ml_scores_dict[solver_uuid] = {
                    "solvability_ratio":None,
                    "f1_score":None,
                    "ml_metrics_calculator_version":1,
                    "comment":"All labels were either all `True` or all `False` and we cannot create an ML model with only one class."
                }

            ml_models_dict[solver_uuid] = mini_ml_model # TODO: currently storing the all MiniML models.

        self.ml_scores_dict = ml_scores_dict # update in place
        self.ml_models_dict = ml_models_dict # update in place
        return self.ml_scores_dict # return for other usage.
        
























    def calculate_solver_success_labels(self) -> pd.DataFrame:
        """Construct the `BenchmarkData.aggregated_solver_labels_df` (pd.DataFrame) attribute containing the success/failure of each solver against `task_uuids`.
        
        Depends:
            BenchmarkData.solver_df (pd.DataFrame): Columns are `solver_uuid` and `solver_short_name`.  Each unique `solver_uuid` only appears once.
            BenchmarkData.problem_instance_list (list): A list of problem instances (dictionary objects), most likely produced by `load_json_files()`. 
            BenchmarkData.solution_list (list): A list of solutions (dictionary objects), most likely produced by `load_json_files()`. 
            BenchmarkData.hamiltonian_features (pd.DataFrame): A data frame containing a variety of interesting features about the Hamiltonians (by `task_uuid`).

        Returns:
            pd.DataFrame: The `BenchmarkData.aggregated_solver_labels_df` attribute is updated in place.  It is also returned for other usage.
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
            "re_circuit_repetitions_per_calculation",
            "re_calculation_repetitions",
            "re_total_circuit_repetitions",
            "re_logical_abstract_num_qubits",
            "re_logical_abstract_t_count",
            "re_logical_architecture_description",
            "re_logical_compiled_num_qubits",
            "re_logical_compiled_t_count",
            "re_logical_compiled_num_t_factories",
            "re_physical_architecture_description",
            "re_physical_code_name",
            "re_physical_code_distance",
            "re_physical_runtime",
            "re_physical_num_qubits",
            "re_physical_t_count",
            "re_physical_num_t_factories",
            "submitted_by_calendar_due_date",
            "label" # label True/False, that the Hamiltonian was solved.
        ]
        aggregated_solver_labels = pd.DataFrame(columns=aggregated_solver_labels_columns)

        for problem_instance in self.problem_instance_list:
            problem_instance_uuid = problem_instance["problem_instance_uuid"]
            problem_instance_short_name = problem_instance["short_name"]
            for task in problem_instance["tasks"]:
                task_uuid = task["task_uuid"]
                

                if len(self.hamiltonian_features[self.hamiltonian_features["task_uuid"]==task_uuid])==0:
                    # we do NOT have Hamiltonian features calculated for this task_uuid yet... skip it.
                    continue
                
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
                for solver_uuid in self.solvers_df["solver_uuid"].values:
                    solver_short_name = data_frame_vlookup(
                        df=self.solvers_df,
                        lookup_value=solver_uuid,
                        lookup_value_column_header="solver_uuid",
                        find_value_column_header="solver_short_name"
                    )

                    results, solution_uuid = self.locate_solution_results_by_task_uuid_and_solver_uuid(
                        solver_uuid=solver_uuid,
                        task_uuid=task_uuid                        
                    )

                    if results is None: 
                        # no corresponding results/solution submitted for task_uuid by solver.
                        solution = None
                    else:
                        solution = find_dict_with_matching_kv_pair(
                            list_of_dicts=self.solution_list,
                            lookup_key="solution_uuid",
                            lookup_val=solution_uuid
                        )



                    d = {}
                    for k in aggregated_solver_labels_columns:
                        d[k] = None # init all to None.  Update below.    

                    # re init some metadata:
                    d["solver_short_name"] = solver_short_name
                    d["solver_uuid"] = solver_uuid
                    d["solution_uuid"] = solution_uuid
                    d["problem_instance_short_name"] = problem_instance_short_name
                    d["problem_instance_uuid"] = problem_instance_uuid
                    d["task_uuid"] = task_uuid
                    d["instance_data_object_uuid"] = instance_data_object_uuid
                    d["instance_data_object_url"] = instance_data_object_url

                    d["num_orbitals"] = data_frame_vlookup(
                        df=self.hamiltonian_features,
                        lookup_value=task_uuid,
                        lookup_value_column_header="task_uuid",
                        find_value_column_header="n_orbs" # TODO: standardize on num_orbitals
                    )

                    # task-specific requirements from `problem_instance`
                    d["calendar_due_date"] = problem_instance["calendar_due_date"] # may be None/null per .json.
                    d["time_limit_seconds"] = task["requirements"]["time_limit_seconds"]
                    d["accuracy_tol"] = task["requirements"]["absolute_accuracy_threshold"]
                    d["reference_energy"] = task["requirements"]["reference_energy"]
                        

                    if results is None:
                        # the solver did NOT submit a solution file for the problem_instance or Hamiltonian.
                        # mark it as failed.  TODO:  do something more nuanced with non-attempted problems in the future.
                        d["is_resource_estimate"] = None
                        d["attempted"] = False
                        d["solved_within_run_time"] = False
                        d["solved_within_accuracy_requirement"] = False
                        d["label"] = False # overall result:  solved==True/False
                        d["submitted_by_calendar_due_date"] = False
                        d["overall_run_time_seconds"] = None
                    else:
                        d["is_resource_estimate"] = solution["is_resource_estimate"]
                        
                        # calculate simple performance metrics for the solver against
                        # this Hamiltonian
                        d["attempted"] = True 

                        # TODO: issue-#94:  physical resource estimate (PRE) not calculated for LRE
                        d["overall_run_time_seconds"] = results["run_time"]["overall_time"]["seconds"]
                        d["solved_within_run_time"] = d["overall_run_time_seconds"] <= d["time_limit_seconds"]
                    
                        
                        # TODO: check calendar due date submission.... not implemented at this time.
                        d["submitted_by_calendar_due_date"] = True 
                            


                        if d["is_resource_estimate"]:
                            d["num_logical_qubits"] = results["quantum_resources"]["logical"]["num_logical_qubits"]
                            d["num_shots"] = results["quantum_resources"]["logical"]["num_shots"]
                            d["num_T_gates_per_shot"] = results["quantum_resources"]["logical"]["num_T_gates_per_shot"]
                            d["solved_within_accuracy_requirement"] = True # always true.  assume LREs solve to accuracy.
                        else:
                            # NOT a logical resource estimate.
                            
                            d["reported_energy"] = results["energy"]
                            try:
                                d["solved_within_accuracy_requirement"] = bool(np.abs(d["reported_energy"] - d["reference_energy"]) < d["accuracy_tol"])
                            except Exception as e:
                                logging.error(f'Error: {e}', exc_info=True)
                                logging.warning(f"warning!  no energy target specified in task {task_uuid}.  reference_energy={d['reference_energy']}")
                                d["solved_within_accuracy_requirement"] = False
                            
                            # TODO: issue-44.  handle case when more than one solution submitted by
                            # one solver.  for now assume solutions were submitted by due date.
                            # TODO: check calendar due date submission.
                            
                        d["label"] = d["solved_within_run_time"] and d["solved_within_accuracy_requirement"]
                            

                    # translate values for sponsor RE field names
                    if d["is_resource_estimate"]:
                        d["re_circuit_repetitions_per_calculation"] = d["num_shots"]
                        d["re_calculation_repetitions"] = 1
                        d["re_total_circuit_repetitions"] = d["re_circuit_repetitions_per_calculation"]*d["re_calculation_repetitions"]
                        d["re_logical_abstract_num_qubits"] = d["num_logical_qubits"]
                        d["re_logical_abstract_t_count"] = d["num_T_gates_per_shot"]
                        
                        # remove commas so we don't mess up the CSV output.
                        d["re_logical_architecture_description"] = solution["solver_details"]["algorithm_details"]["algorithm_description"].replace(",","")
                        d["re_logical_compiled_num_qubits"] = results["quantum_resources"]["physical"]["num_logical_compiled_qubits"]
                        d["re_logical_compiled_t_count"] = None # TODO: not reported at this time.
                        d["re_logical_compiled_num_t_factories"] = solution["solver_details"]["quantum_hardware_details"]["quantum_hardware_parameters"]["num_factories"]
                        
                        # remove commas so we don't mess up the CSV output.
                        d["re_physical_architecture_description"] = solution["solver_details"]["quantum_hardware_details"]["quantum_hardware_description"].replace(",","")
                        
                        d["re_physical_code_name"] = "surface" # TODO: fixed value at this time.  Revisit later. 
                        d["re_physical_code_distance"] = results["quantum_resources"]["physical"]["data_code_distance"]
                        d["re_physical_runtime"] = d["overall_run_time_seconds"]
                        d["re_physical_num_qubits"] = results["quantum_resources"]["physical"]["num_physical_qubits"]
                        d["re_physical_t_count"] = None # TODO: not reported at this time.
                        d["re_physical_num_t_factories"] = solution["solver_details"]["quantum_hardware_details"]["quantum_hardware_parameters"]["num_factories"]


                    # new row added (for each solver_uuid/task_uuid)
                    aggregated_solver_labels = pd.concat(
                        [aggregated_solver_labels, pd.DataFrame([d])],
                        ignore_index=True
                    )
        
        self.aggregated_solver_labels_df = aggregated_solver_labels
        return aggregated_solver_labels
    


















    def write_sponsor_resource_estimate_files(
            self,
            output_directory: str,
        ) -> None:
        """Write the sponsor's resource estimate JSON files to the `output_directory`

        Warning:
            The `output_directory` is erased and repopulated.

        Depends:
            BenchmarkData.sponsor_resource_estimate_list (list): Should be up-to-date. It should have been created during `.__init__()`.

        Args:
            output_directory (str): relative/path/to/output/directory for JSON files.
        """
        
        clear_or_create_output_directory(output_directory=output_directory)

        for re in self.sponsor_resource_estimate_list:
            resource_estimate_file_name = f"resource_estimate.gsee.{re['name']}.{re['size']}.{re['id']}.json"
            output_path = os.path.join(output_directory, resource_estimate_file_name)
            with open(output_path, "w") as output:
                json.dump(re, output, indent=4)






















    def calculate_sponsor_resource_estimates(self) -> list:
        """Construct the `BenchmarkData.sponsor_resource_estimate_list` (`list`) attribute per the sponsor's resource estimate schema.

        Returns:
            list: The `BenchmarkData.sponsor_resource_estimate_list` attribute is updated in place.  It is also returned for other usage.
        """

        
        self.sponsor_resource_estimate_list = [] # erase/init.

        for i in range(len(self.all_data_df)):
            d = self.all_data_df.iloc[i]
            if d["is_resource_estimate"] and d["attempted"]:

                # translate lots of our fields to sponsor-schema fields:
                re = {}
                re["$schema"] = "https://raw.githubusercontent.com/rroodll/QB-Estimate-Reporting/main/schema/resource_estimate_schema.json"
                re["id"] = d["task_uuid"]
                re["name"] = d['problem_instance_short_name']
                re["category"] = "industrial" #enum
                re["size"] = f"{d['num_orbitals']}_orbitals"
                re["task"] = "ground_state_energy_estimation" #enum
                re["implementation"] = d["re_logical_architecture_description"]
                re["value"] = d["Utility NPV $"]
                re["value_ci"] = [d["Utility NVP lower bound $"], d["Utility NVP lower bound $"]]
                # re["value_per_t_gate"] updated below after other fields populated...
                re["circuit_repetitions_per_calculation"] = d["re_circuit_repetitions_per_calculation"]
                re["calculation_repetitions"] = d["re_calculation_repetitions"]
                re["total_circuit_repetitions"] = d["re_total_circuit_repetitions"]
                re["runtime_requirement"] = d["time_limit_seconds"]
                re["logical-abstract"] = {} # object is required.
                re["logical-abstract"]["num_qubits"] = d["re_logical_abstract_num_qubits"]
                re["logical-abstract"]["t_count"] = d["re_logical_abstract_t_count"]
                # re["logical-abstract"]["clifford_count"] # SCHEMA-OPTIONAL.  Not reported at this time.
                # re["logical-abstract"]["gate_count"] # SCHEMA-OPTIONAL.  Not reported at this time.
                # re["logical-abstract"]["circuit_depth"] # SCHEMA-OPTIONAL.  Not reported at this time.
                # re["logical-abstract"]["t_depth"] # SCHEMA-OPTIONAL.  Not reported at this time.
                
                # TODO: not reporting logical-compiled as of 2025-01-09 as we are missing the REQUIRED t_count field.
                # re["logical-compiled"] = {} # object is optional.
                # re["logical-compiled"]["logical_architecture_description"] = d["re_logical_architecture_description"]
                # re["logical-compiled"]["num_qubits"] = d["re_logical_compiled_num_qubits"]
                # re["logical-compiled"]["t_count"] = "XXXXXXXXXXXXX"
                # re["logical-compiled"]["num_t_factories"] = d["re_physical_num_t_factories"]
                # re["logical-compiled"]["gate_count"] # SCHEMA-OPTIONAL.  Not reported at this time.
                # re["logical-compiled"]["clifford_count"] # SCHEMA-OPTIONAL.  Not reported at this time.
                # re["logical-compiled"]["circuit_depth"] # SCHEMA-OPTIONAL.  Not reported at this time.
                # re["logical-compiled"]["t_depth"] # SCHEMA-OPTIONAL.  Not reported at this time.
                
                # TODO: not reporting physical as of 2025-01-09 as we are missing the REQUIRED t_count field.
                # re["physical"] = {} # object is optional
                # re["physical"]["physical_architecture_description"] = d["re_physical_architecture_description"]
                # re["physical"]["code_name"] = d["re_physical_code_name"] #schema enum to "surface" or "other"
                # re["physical"]["code_distance"] = d["re_physical_code_distance"]
                # re["physical"]["runtime"] = d["re_physical_runtime"]
                # re["physical"]["num_qubits"] = d["re_physical_num_qubits"]
                # re["physical"]["t_count"] = "XXXXXXXXXXXXX"
                # re["physical"]["num_t_factories"] = d["re_physical_num_t_factories"]
                # re["physical"]["num_factory_qubits"]# SCHEMA-OPTIONAL.  Not reported at this time.
                # re["physical"]["gate_count"]# SCHEMA-OPTIONAL.  Not reported at this time.
                # re["physical"]["circuit_depth"]# SCHEMA-OPTIONAL.  Not reported at this time.
                # re["physical"]["t_depth"]# SCHEMA-OPTIONAL.  Not reported at this time.
                # re["physical"]["clifford_count"]# SCHEMA-OPTIONAL.  Not reported at this time.
                
                # update "value_per_t_gate" after all other fields populated:
                x = re["value"]
                y = re["total_circuit_repetitions"]*re["logical-abstract"]["t_count"]
                re["value_per_t_gate"] = x/y

                self.sponsor_resource_estimate_list.append(re)
        
        return self.sponsor_resource_estimate_list





    def read_performance_metrics_json_files(self) -> list:
        """TODO: docstring
        """
        self.performance_metrics_list = load_json_files(
            search_dir=self.performance_metrics_directory
        ) # updated in place.

        return self.performance_metrics_list # returned for other usage.







    def calculate_performance_metrics(self) -> list:
        """TODO: docstring

        Returns:
            list: _description_
        """
        
        # first call/calculate ml scores.
        self.calculate_ml_scores()

        # clear/init
        self.performance_metrics_list = [] 

        for solver_uuid in self.solvers_dict:
            solver = self.solvers_dict[solver_uuid]
            df = self.all_data_df
            df = df[df["solver_uuid"]==solver_uuid] # filter data to solver_uuid

            performance_metrics_uuid = str(uuid4())
            performance_metrics = {}
            performance_metrics["$schema"] = "https://raw.githubusercontent.com/isi-usc-edu/qb-gsee-benchmark/main/schemas/performance_metrics.schema.0.0.1.json"
            performance_metrics["performance_metrics_uuid"] = performance_metrics_uuid
            performance_metrics["solver_short_name"] = solver["solver_short_name"]
            performance_metrics["solver_uuid"] = solver_uuid
            performance_metrics["creation_timestamp"] = self.timestamp
            performance_metrics["ml_metrics"] = self.ml_scores_dict[solver_uuid]

            # Top-level aggregated performance metrics:
            # ===============================================================
            number_of_tasks_attempted = len(df[df["attempted"]==True])
            number_of_tasks_solved = len(df[df["label"]==True])
            number_of_tasks_solved_within_run_time_limit = len(df[df["solved_within_run_time"]==True])
            number_of_tasks_solved_within_accuracy_threshold = len(df[df["solved_within_accuracy_requirement"]==True])
            performance_metrics["top_level_results"] = {
                    "number_of_problem_instances": df["problem_instance_uuid"].nunique(),
                    "number_of_problem_instances_attempted": None, #calculated below...
                    "number_of_problem_instances_solved": None, #calculated below...
                    "number_of_tasks": df["task_uuid"].nunique(),
                    "number_of_tasks_attempted": number_of_tasks_attempted,
                    "number_of_tasks_solved": number_of_tasks_solved,
                    "number_of_tasks_solved_within_run_time_limit": number_of_tasks_solved_within_run_time_limit,
                    "number_of_tasks_solved_within_accuracy_threshold": number_of_tasks_solved_within_accuracy_threshold,
                    "max_run_time_of_attempted_tasks": None, #calculated below...,
                    "sum_of_run_time_of_attempted_tasks":None, #calculated below...,
            }
            
            
            # number_of_problem_instances_ATTEMPTED...
            problem_instance_uuid_list = df["problem_instance_uuid"].unique()
            count_number_problem_instances_attempted = 0
            for problem_instance_uuid in problem_instance_uuid_list:
                # filter df to only problem instance
                df_filtered = df[df["problem_instance_uuid"]==problem_instance_uuid]
                num_tasks = len(df_filtered)
                num_attempted_tasks = len(df_filtered[df_filtered["attempted"]==True])
                # must attempt ALL task to "attempt" the problem_instance.
                if num_tasks == num_attempted_tasks:
                    count_number_problem_instances_attempted += 1
            performance_metrics["top_level_results"]["number_of_problem_instances_attempted"] \
                = count_number_problem_instances_attempted


            # number_of_problem_instances_SOLVED...
            count_number_problem_instances_solved = 0
            for problem_instance_uuid in problem_instance_uuid_list:
                # filter df to only problem instance
                df_filtered = df[df["problem_instance_uuid"]==problem_instance_uuid]
                num_tasks = len(df_filtered)
                num_solved_tasks = len(df_filtered[df_filtered["label"]==True])
                # must SOLVE ALL tasks to "SOLVE" the problem_instance.
                if num_tasks == num_solved_tasks:
                    count_number_problem_instances_solved += 1
            performance_metrics["top_level_results"]["number_of_problem_instances_solved"] \
                = count_number_problem_instances_solved


            # max_run_time_of_attempted_tasks...
            # filter down to only task that were attempted:
            df_filtered = df[df["attempted"]==True]
            performance_metrics["top_level_results"]["max_run_time_of_attempted_tasks"] \
                = max(df_filtered["overall_run_time_seconds"])

            # sum_of_run_time_of_attempted_tasks...
            # filter down to only task that were attempted:
            df_filtered = df[df["attempted"]==True]
            performance_metrics["top_level_results"]["sum_of_run_time_of_attempted_tasks"] \
                = sum(df_filtered["overall_run_time_seconds"])




            # Performance metrics by problem_instance:
            # ===============================================================
            
            performance_metrics["results_by_problem_instance"] = []
            
            for problem_instance_uuid in problem_instance_uuid_list:
                df_filtered = df[df["problem_instance_uuid"]==problem_instance_uuid]
                logging.info(f"problem_instance_uuid: {problem_instance_uuid}")
                logging.info(f"number of tasks: {len(df_filtered)}")
                
                # TODO: PRIORITY:  issue #44: handle situation where one solver has more than one solution_uuid for a single problem_uuid
                assert df_filtered["solution_uuid"].nunique() <= 1, "issue #44:  we have more than one solution_uuid for a (solver_uuid,problem_uuid) pair."
                x = {
                    "problem_instance_uuid":problem_instance_uuid,
                    "solution_uuid": df_filtered["solution_uuid"].unique()[0], # should only be one solution_uuid.  see issue #44.
                    "number_of_tasks": len(df_filtered),
                    "number_of_tasks_attempted": len(df_filtered[df_filtered["attempted"]==True]),
                    "number_of_tasks_solved_within_runtime_limit":len(df_filtered[df_filtered["solved_within_run_time"]==True]),
                    "number_of_tasks_solved_within_accuracy_requirement":len(df_filtered[df_filtered["solved_within_accuracy_requirement"]==True]),
                    "number_of_tasks_solved":len(df_filtered[df_filtered["label"]==True]),
                    "sum_of_run_time_of_attempted_tasks":None, # updated below...
                    "max_run_time_of_attempted_tasks":None, # updated below...
                    "solution_submitted_by_due_date":\
                        df_filtered["submitted_by_calendar_due_date"].values[0] # should only be one.  see issue #44.
                        
                }
                if len(df_filtered[df_filtered["attempted"]==True]) > 0:
                    # logging.info(f"number of attempted tasks: {len(df_filtered[df_filtered['attempted']==True])}")
                    x["sum_of_run_time_of_attempted_tasks"] \
                        = sum(df_filtered[df_filtered["attempted"]==True]["overall_run_time_seconds"])
                    x["max_run_time_of_attempted_tasks"] \
                        = max(df_filtered[df_filtered["attempted"]==True]["overall_run_time_seconds"])
                else:
                    pass
                    # logging.info(f"it seems the solver did not attempt ANY of the tasks in problem_instance_uuid {problem_instance_uuid}")

                performance_metrics["results_by_problem_instance"].append(x)






            # Performance metrics by task:
            # ===============================================================
            
            performance_metrics["results_by_task"] = []
            
            task_uuid_list = df["task_uuid"].unique()
            for task_uuid in task_uuid_list:
                df_filtered = df[df["task_uuid"]==task_uuid]
                # TODO: issue #44:  handle case where more than one solution_uuid per (solver_uuid, task_uuid) present.
                assert df_filtered["solution_uuid"].nunique() <= 1, "issue #44:  we have more than one solution_uuid for a (solver_uuid,task_uuid) pair."
                assert len(df_filtered) == 1, "issue #44:  we have more than one solution_uuid for a (solver_uuid,task_uuid) pair."
                x = {
                    "task_uuid":task_uuid,
                    "problem_instance_uuid":df_filtered["problem_instance_uuid"].values[0], # should only be one...TODO: issue #44.
                    "instance_data_object_uuid":df_filtered["instance_data_object_uuid"].values[0],
                    "solution_uuid": df_filtered["solution_uuid"].unique()[0],
                    "attempted":df_filtered["attempted"].values[0],
                    "solved_within_run_time":df_filtered["solved_within_run_time"].values[0],
                    "solved_within_accuracy_requirement":df_filtered["solved_within_accuracy_requirement"].values[0],
                    "solved":df_filtered["label"].values[0],
                    "overall_run_time_seconds":None #calculated below
                }
                if x["attempted"]:
                    x["overall_run_time_seconds"] = df_filtered["overall_run_time_seconds"].values[0]
                performance_metrics["results_by_task"].append(x)


            
            self.performance_metrics_list.append(performance_metrics) # update in place.
        return self.performance_metrics_list # return for other usage.











    
    def write_performance_metrics_json_files(
            self,
            output_directory: str
        ) -> None:
        """TODO: docstring

        Args:
            output_directory (str): _description_
        """
        clear_or_create_output_directory(output_directory=output_directory)
        
        for pm in self.performance_metrics_list:
            performance_metrics_file_name = f"performance_metrics.{pm['solver_short_name']}.{pm['solver_uuid']}.json"
            output_path = os.path.join(output_directory, performance_metrics_file_name)
            with open(output_path, "w") as output:
                json.dump(pm, output, indent=4)




















