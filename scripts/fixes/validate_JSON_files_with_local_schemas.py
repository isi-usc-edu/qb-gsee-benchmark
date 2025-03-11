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

from qb_gsee_benchmark.utils import load_json_files
from qb_gsee_benchmark.utils import validate_list_of_json_objects



# Read/load JSON files as lists:
json_files = load_json_files(
    search_dir="../../solution_files/"
)
print(f"loaded {len(json_files)} JSON files.")

# validate the JSON files in the directories:
validate_list_of_json_objects(
    json_object_list=json_files,
    local_resolver_directory="../../schemas", # resolves $refs in schema
    local_schema_file="../../schemas/solution.schema.0.0.1.json", # local file
)
print(f"JSON files are OK!")







