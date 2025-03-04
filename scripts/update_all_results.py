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
import logging
import argparse
import sys
import shutil

from qb_gsee_benchmark.benchmark_data import BenchmarkData
from qb_gsee_benchmark.standard_report import StandardReport 
from qb_gsee_benchmark.utils import clear_or_create_output_directory


# logging configuration:
logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(
    "update_all_results.log.txt",
    mode="w"
)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler, file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)






def main(args: argparse.Namespace) -> None:
    
    if not args.production and not args.temp_results:
        logging.error(f"User did not specify --production or --temp_results.  See --help for usage.")
        logging.info(f"Exiting.")
        sys.exit(1)



    logging.info(f"Started...")
    if args.production:
        # fix/override other options: 
        args.temp_results = False
        args.validate_json = True
        args.shap_analysis = True
        args.data_to_csv = True
    
    
    
    


    benchmark_data = BenchmarkData(
        hamiltonian_features_csv_file_name="Hamiltonian_features.csv",
        utility_estimation_csv_file_name="GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv",
        problem_instances_directory="../problem_instances",
        solution_files_directory="../solution_files/",
        performance_metrics_directory="../performance_metrics"
    )
    
    
    if args.data_to_csv:
        benchmark_data.to_csv(
            f"all_data_{benchmark_data.datestamp}.csv"
        )

    if args.validate_json:
        logging.info(f"")
        benchmark_data.validate_all_json_objects(
            local_resolver_directory="../schemas"
        )
        logging.info(f"All JSON files are OK!")

    
            


    
    
    if args.production:
        benchmark_data.write_performance_metrics_json_files(
            output_directory=benchmark_data.performance_metrics_directory
        )
        resource_estimate_files_dir = f"resource_estimate_files_{benchmark_data.datestamp}"
        benchmark_data.write_sponsor_resource_estimate_files(
            output_directory=resource_estimate_files_dir
        )
        StandardReport(
            benchmark_data=benchmark_data,
            standard_report_output_directory="../standard_report"
        )
        # copy `data_for_BubbleML.csv` to BubbleML/UI folder
        # TODO: remove this block whenever BubbleML is integrated with /src.
        try:
            shutil.copy2("ml_artifacts/data_for_BubbleML.csv", "../BubbleML/UI/")
        except Exception as e:
            print(f"Error: {e}")
            print(f"Attempted to copy file with relative paths.  Maybe you are running this script from a different working directory.")
    
    if args.temp_results:
        temp_results_dir = "temp_results"
        clear_or_create_output_directory(temp_results_dir)
        benchmark_data.write_performance_metrics_json_files(
            output_directory=os.path.join(temp_results_dir,"performance_metrics")
        )
        resource_estimate_files_dir = f"resource_estimate_files_{benchmark_data.datestamp}"
        benchmark_data.write_sponsor_resource_estimate_files(
            output_directory=os.path.join(temp_results_dir,resource_estimate_files_dir)
        )
        StandardReport(
            benchmark_data=benchmark_data,
            standard_report_output_directory=os.path.join(temp_results_dir,"standard_report")
        )
    
    
    
    logging.info("Done.")
    logging.info(f"{str(benchmark_data)}")










if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update all results."
    )
    
    parser.add_argument(
        "--production", 
        action="store_true",
        default=False,
        help="WARNING: This overrides any other options.  This does everything and overwrites the results in /standard_report."
    )
    parser.add_argument(
        "--temp_results",
        action="store_true",
        default=False,
        help="Place results into /temp_results for review."
    )
    parser.add_argument(
        "--validate_json",
        action="store_true",
        default=False,
        help="Validate all JSON files."
    )
    parser.add_argument(
        "--data_to_csv",
        action="store_true",
        default=False,
        help="Write all benchmark data to all_data_YYYYMMDD.csv file."
    )


    args = parser.parse_args()
    main(args)


