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


import os
import argparse
import sys
sys.path.append("../src/")
from qb_gsee_benchmark.benchmark_data import BenchmarkData
#from qb_gsee_benchmark.standard_report import StandardReport 
from qb_gsee_benchmark.utils import clear_or_create_output_directory
import json
import pickle



def main(args: argparse.Namespace) -> None:

    if args.DRYRUN_or_PRODUCTION == "DRYRUN" or args.DRYRUN_or_PRODUCTION == "PRODUCTION":
        print("starting...")
    else:
        raise ValueError("user should type either DRYRUN or PRODUCTION as CLI argument.")


    benchmark_data = BenchmarkData(
        hamiltonian_features_csv_file_name="Hamiltonian_features.csv",
        utility_estimation_csv_file_name="GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv",
        problem_instances_directory="../problem_instances",
        solution_files_directory="../_private_working_folder/PRE_solution_files_20250124/",
        performance_metrics_directory="../performance_metrics"
    )
    
    benchmark_data.to_csv(
        f"all_data_{benchmark_data.datestamp}.csv"
    )

    benchmark_data.calculate_performance_metrics()

    benchmark_data.validate_all_json_objects(
        local_resolver_directory="../schemas"
    )
    print(f"All JSON files are OK!")


    Z0_allsolvers = {}
    shap_values_allsolvers = {}

    if args.SHAP_analysis:
        for solver_uuid in benchmark_data.ml_models_dict:
            benchmark_data.ml_models_dict[solver_uuid].run_shap_analysis()
            Z0_allsolvers[solver_uuid] = benchmark_data.ml_models_dict[solver_uuid].Z0
            shap_values_allsolvers[solver_uuid] = benchmark_data.ml_models_dict[solver_uuid].shap_values

    #save for post_processing (could send it in directly too but wanted it saved for now)
    
    dicts = [Z0_allsolvers, shap_values_allsolvers]
    with open('post_process.pkl', 'wb') as fp:
        pickle.dump(dicts, fp)
   
    
    
    for solver_uuid in benchmark_data.ml_models_dict:
        benchmark_data.ml_models_dict[solver_uuid].write_all_plots()
        benchmark_data.ml_models_dict[solver_uuid].write_probs_to_file()
        


    if args.DRYRUN_or_PRODUCTION == "DRYRUN":
        temp_results_dir = "temp_results"
        clear_or_create_output_directory(temp_results_dir)
        benchmark_data.write_performance_metrics_json_files(
            output_directory=os.path.join(temp_results_dir,"performance_metrics")
        )
        resource_estimate_files_dir = f"resource_estimate_files_{benchmark_data.datestamp}"
        benchmark_data.write_sponsor_resource_estimate_files(
            output_directory=os.path.join(temp_results_dir,resource_estimate_files_dir)
        )
        '''
        StandardReport(
            benchmark_data=benchmark_data,
            standard_report_output_directory=os.path.join(temp_results_dir,"standard_report")
        )
        '''
        
    elif args.DRYRUN_or_PRODUCTION == "PRODUCTION":
        benchmark_data.write_performance_metrics_json_files(
            output_directory=benchmark_data.performance_metrics_directory
        )
        resource_estimate_files_dir = f"resource_estimate_files_{benchmark_data.datestamp}"
        benchmark_data.write_sponsor_resource_estimate_files(
            output_directory=resource_estimate_files_dir
        )
        '''
        StandardReport(
            benchmark_data=benchmark_data,
            standard_report_output_directory="../standard_report"
        )
        '''
        
    else:
        print("No action taken.  Select: DRYRUN or PRODUCTION.")

    print(benchmark_data)










if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update all results."
    )
    
    parser.add_argument(
        "DRYRUN_or_PRODUCTION", 
        type=str, 
        help="typing DRYRUN places results in a temporary folder nearby for review.  PRODUCTION overwrites results."
    )
    parser.add_argument(
        "--SHAP_analysis",
        action="store_true",
        default=False,
        help="Run SHAP analysis and generate SHAP plots for ML models (WARNING: Take a long time!!)"
    )


    args = parser.parse_args()
    main(args)


