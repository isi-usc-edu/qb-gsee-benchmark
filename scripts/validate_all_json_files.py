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


import sys
import argparse

from qb_gsee_benchmark.benchmark_data import BenchmarkData
from qb_gsee_benchmark.utils import validate_list_of_json_objects
from qb_gsee_benchmark.utils import validate_json






def main(args: argparse.Namespace) -> None:


    benchmark_data = BenchmarkData(
        hamiltonian_features_csv_file_name="Hamiltonian_features.csv",
        utility_estimation_csv_file_name="GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv",
        problem_instances_directory="../problem_instances",
        solution_files_directory="../solution_files",
        performance_metrics_directory="../performance_metrics"
    )



    if args.LOCALSCHEMAS_or_REMOTESCHEMAS == "LOCALSCHEMAS":
        lists = [
            (
                "problem instances",
                benchmark_data.problem_instance_list,
                "../schemas/problem_instance.schema.0.0.1.json"
            ),
            (
                "solutions",
                benchmark_data.solution_list,
                "../schemas/solution.schema.0.0.1.json"
            ),
            (
                "performance metrics",
                benchmark_data.performance_metrics_list,
                "../schemas/performance_metrics.schema.0.0.1.json"
            )
        ]
        for listy in lists:
            if listy[1] is None:
                print(f"{listy[0]} is empty/None.")
                print(f"this may happen if performance metrics have not yet been calculated.")
            else:
                print(f"validating {listy[0]}...")
                validate_list_of_json_objects(
                    json_object_list=listy[1],
                    local_resolver_directory="../schemas",
                    local_schema_file=listy[2]
                )
            print(f"warning:  did not validate resource estimates for schema (schema is not a local file!!)")
    elif args.LOCALSCHEMAS_or_REMOTESCHEMAS == "REMOTESCHEMAS":
        benchmark_data.validate_all_json_objects(
            local_resolver_directory="../schemas",
        )
    else:
        print(f"No action taken.  Type LOCALSCHEMAS or REMOTESCHEMAS.")
        sys.exit(1)


    print(f"All JSON files are OK!")
    print(benchmark_data)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate all JSON files."
    )
    
    parser.add_argument(
        "LOCALSCHEMAS_or_REMOTESCHEMAS", 
        type=str, 
        help="typing LOCALSCHEMAS is used when testing new schema updates.  REMOTESCHEMAS is used when fetching remote schemas from URLs (in production)."
    )


    args = parser.parse_args()
    main(args)


