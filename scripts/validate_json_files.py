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

import requests

from qb_gsee_benchmark.utils import validate_json
from qb_gsee_benchmark.utils import load_json_files


json_object_list = load_json_files(search_dir="../solution_files")
print(f"checking {len(json_object_list)} files...")

schema_url = json_object_list[0]["$schema"]
schema = requests.get(schema_url).json()


# checking single file with default kwargs:
# json_object = json_object_list[2]
# validate_json(json_dict=json_object)



for json_object in json_object_list:
    validate_json(
        json_dict=json_object,
        schema=schema,
        local_resolver_directory="../schemas/whatever/"
    )

print(f"All {len(json_object_list)} files are OK!")


