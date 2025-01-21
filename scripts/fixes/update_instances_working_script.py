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



import json
import sys
import os
import datetime

import time
# additional package(s)
import jsonschema



input_directory = "../../problem_instances"

output_directory = "../../problem_instances"

json_files = os.listdir(input_directory)
for json_file in json_files:
    ################################################
    #### read in .json file
    json_file_path = os.path.join(input_directory, json_file)
    with open(json_file_path, "r") as jf:
        problem_instance = json.load(jf)
    for i in range(len(problem_instance["tasks"])):
        if "reference_energy" in problem_instance["tasks"][i]["requirements"]:
            print("has reference energy")
        else:
            problem_instance["tasks"][i]["requirements"]["reference_energy"] = None
            problem_instance["tasks"][i]["requirements"]["reference_energy_units"] = "Hartree"
            print("added None as reference energy.")
    
    ########################################################
    #### write out the updated .json file
    output_json_file_path = os.path.join(output_directory, json_file)
    with open(output_json_file_path, "w") as output_json_file:
            json.dump(
                problem_instance,
                output_json_file,
                indent=4
            )


    
    



