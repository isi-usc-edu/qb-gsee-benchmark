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


# Assuming you have installed qb_gsee_benchmark per the README,
# you may import/use this function:
from qb_gsee_benchmark.utils import load_json_files
from qb_gsee_benchmark.utils import validate_list_of_json_objects




# Read/load JSON files as lists:
problem_instances_list = load_json_files(
    search_dir="../problem_instances" # relative path
)
print(f"loaded {len(problem_instances_list)} problem instance JSON files.")

# validate the JSON files in the directories:
validate_list_of_json_objects(
    json_object_list=problem_instances_list,
    local_resolver_directory="../schemas", # resolves $refs in schema
    local_schema_file=None, # Unless specified, schema is fetched from $schema URL inside of the *first* JSON file in the list.
)
print(f"problem instance files are OK!")




# validate the JSON files in the directories:
solution_files_list = load_json_files(
    search_dir="../solution_files" # relative path
)
print(f"loaded {len(solution_files_list)} solution JSON files.")

# validate the JSON files in the directories:
validate_list_of_json_objects(
    json_object_list=solution_files_list,
    local_resolver_directory="../schemas", # resolves $refs in schema
    local_schema_file=None, # Unless specified, schema is fetched from $schema URL inside of the *first* JSON file in the list.
)  
print("solution files are OK!")


# NOTE:  no output implies success!!






