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


from qb_gsee_benchmark.utils import validate_json


import json
import sys
import os
import datetime

import time
# additional package(s)
import jsonschema



input_directory = "../../solution_files"

local_schema_file = "../../schemas/solution.schema.0.0.1.json"
with open(local_schema_file, "r") as schema_file:
    schema = json.load(schema_file)
local_resolver_directory = "../../schemas"

output_directory = "../../solution_files"

json_files = os.listdir(input_directory)
for json_file in json_files:
    ################################################
    #### read in .json file
    json_file_path = os.path.join(input_directory, json_file)
    with open(json_file_path, "r") as jf:
        json_dict = json.load(jf)
    
    ################################################
    #### Fix stuff

    


    validate_json(
        json_dict=json_dict,
        schema=schema,
        local_resolver_directory="../../schemas"
    )



    ########################################################
    #### write out the updated .json file
    output_json_file_path = os.path.join(output_directory, json_file)
    with open(output_json_file_path, "w") as output_json_file:
            json.dump(
                problem_instance,
                output_json_file,
                indent=4
            )


    
    



