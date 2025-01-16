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


from qb_gsee_benchmark.benchmark_data import BenchmarkData



benchmark_data = BenchmarkData(
    hamiltonian_features_csv_file_name="Hamiltonian_features.csv",
    utility_estimation_csv_file_name="GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv",
    problem_instances_directory="../problem_instances",
    solution_files_directory="../solution_files",
    performance_metrics_directory="../performance_metrics"
)

benchmark_data.validate_all_json_objects(
    local_resolver_directory="../schemas"
)
print(f"All JSON files are OK!")

print(benchmark_data)

