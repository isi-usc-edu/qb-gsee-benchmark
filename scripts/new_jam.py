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


import datetime
from qb_gsee_benchmark.benchmark_data import BenchmarkData
from qb_gsee_benchmark.standard_report import StandardReport 




benchmark_data = BenchmarkData(
    hamiltonian_features_csv_file_name="Hamiltonian_features.csv",
    utility_estimation_csv_file_name="GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv",
    problem_instances_directory="../problem_instances",
    solution_files_directory="../solution_files",
    performance_metrics_directory="../performance_metrics"
)
print(benchmark_data)


# benchmark_data.read_performance_metrics_json_files()
# print(f"read in {len(benchmark_data.performance_metrics_list)} performance metrics files.")

benchmark_data.calculate_performance_metrics()

# benchmark_data.validate_all_json_objects()

benchmark_data.write_performance_metrics_json_files(
    output_directory=benchmark_data.performance_metrics_directory
)

benchmark_data.to_csv(
    f"all_data_{benchmark_data.datestamp}.csv"
)

benchmark_data.write_sponsor_resource_estimate_files(
    f"resource_estimate_files_{benchmark_data.datestamp}"
)

StandardReport(
    benchmark_data=benchmark_data,
    standard_report_output_directory="standard_report"
)




