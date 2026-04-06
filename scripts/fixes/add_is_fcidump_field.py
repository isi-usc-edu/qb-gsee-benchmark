#!/usr/bin/env python3


# Copyright 2026 L3Harris Technologies, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from qb_gsee_benchmark.utils import validate_json
import json
import os
import shutil




   

#### fields for validating the JSON later:
local_schema_file = "../../schemas/problem_instance.schema.0.0.1.json"
with open(local_schema_file, "r") as schema_file:
    schema = json.load(schema_file)
local_resolver_directory = "../../schemas"


src_root = "../../problem_instances" 
dst_root = "../../TEMP_problem_instances" # revamped JSON files will be output here for inspection.

# Delete the destination directory and all its contents if it exists
if os.path.exists(dst_root):
    print(f"Deleting existing destination directory: {dst_root}")
    shutil.rmtree(dst_root)


for dirpath, _, filenames in os.walk(src_root):
    for filename in filenames:
        if filename.lower().endswith('.json'):
            src_file_path = os.path.join(dirpath, filename)
            # Compute relative path and destination path
            rel_path = os.path.relpath(src_file_path, src_root)
            dst_file_path = os.path.join(dst_root, rel_path)
            dst_dir = os.path.dirname(dst_file_path)
            os.makedirs(dst_dir, exist_ok=True)
            try:
                ##### load in OLD JSON data
                with open(src_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)


                ###### update/fix it:
                for task in data["tasks"]:
                    for supporting_file in task["supporting_files"]:
                        file_url = supporting_file["instance_data_object_url"]
                        if "fcidump" in file_url.lower():
                            supporting_file["is_fcidump_file"] = True
                        else:
                            supporting_file["is_fcidump_file"] = False



                ##### validate the JSON
                validate_json(
                    json_dict=data,
                    schema=schema,
                    local_resolver_directory="../../schemas"
                )


                ##### write out updated JSON to NEW destination path
                with open(dst_file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)


                ##### brag about it:
                print(f"Updated: {dst_file_path}")

            except Exception as e:
                print(f"Error processing {src_file_path}: {e}")




