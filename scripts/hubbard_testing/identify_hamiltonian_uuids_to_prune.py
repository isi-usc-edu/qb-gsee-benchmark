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


from qb_gsee_benchmark.utils import validate_json
from qb_gsee_benchmark.utils import load_json_files
import pandas as pd

import json
import sys
import os





df = pd.read_csv("../Hamiltonian_features.csv")
to_remove = df["task_uuid"].tolist()


problem_instances = load_json_files("../../problem_instances")

for problem_instance in problem_instances:
    for task in problem_instance["tasks"]:
        task_uuid = task["task_uuid"]
        if task_uuid in to_remove:
             to_remove.remove(task_uuid)




# print the leftovers:
print(to_remove)
    
print(f"\n\nnumber to remove {len(to_remove)}")


