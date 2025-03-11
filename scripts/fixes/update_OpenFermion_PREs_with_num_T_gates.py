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



input_directory = "../../solution_files/PRE_solution_files_20250304"

local_schema_file = "../../schemas/solution.schema.0.0.1.json"
with open(local_schema_file, "r") as schema_file:
    schema = json.load(schema_file)
local_resolver_directory = "../../schemas"

output_directory = "../../solution_files/PRE_solution_files_20250304"

json_files = os.listdir(input_directory)
for json_file in json_files:
    ################################################
    #### read in .json file
    json_file_path = os.path.join(input_directory, json_file)
    with open(json_file_path, "r") as jf:
        d = json.load(jf)
    for i in range(len(d["solution_data"])):
        num_toffoli_gates_per_shot = d["solution_data"][i]["quantum_resources"]["logical"]["num_toffoli_gates_per_shot"]    
        num_T_gates_per_shot = 4*num_toffoli_gates_per_shot
        d["solution_data"][i]["quantum_resources"]["logical"]["num_T_gates_per_shot"] = num_T_gates_per_shot
        comment = "`num_toffoli_gates_per_shot` calculated by OpenFermion.  `num_T_gates_per_shot` estimated as `num_T_gates_per_shot` := 4*`num_toffoli_gates_per_shot` per https://quantum-journal.org/papers/q-2019-12-02-208/pdf/"
        d["solution_data"][i]["quantum_resources"]["logical"]["comment"] = comment
        
        
        
        # "task_uuid": "2b2eefc4-9c8c-4a02-b621-059774f620c4",
        #     "error_bound": 0.00159362,
        #     "confidence_level": 0.99,
        #     "quantum_resources": {
        #         "logical": {
        #             "num_logical_qubits": 804,
        #             "num_toffoli_gates_per_shot": 15302709200,
        #             "num_T_gates_per_shot": 61210836800,
        #             "comment": "`num_toffoli_gates_per_shot` calculated by OpenFermion.  `num_T_gates_per_shot` estimated as `num_T_gates_per_shot` := 4*`num_toffoli_gates_per_shot` per https://quantum-journal.org/papers/q-2019-12-02-208/pdf/",
                  


    validate_json(
        json_dict=d,
        schema=schema,
        local_resolver_directory="../../schemas"
    )



    ########################################################
    #### write out the updated .json file
    output_json_file_path = os.path.join(output_directory, json_file)
    with open(output_json_file_path, "w") as output_json_file:
            json.dump(
                d,
                output_json_file,
                indent=4
            )


    
    



