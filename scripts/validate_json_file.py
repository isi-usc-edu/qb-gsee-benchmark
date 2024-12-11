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

import sys
import json
import requests
import argparse

# additional package(s):
import jsonschema




def main(args):
    
    # read the file you want to validate
    try:
        with open(args.file, "r") as json_file:
            file_contents = json.load(json_file)
    except Exception as e:
        print(f"Error: {e}")
        print(f"Cannot read the file {args.file}...\n\n")
        sys.exit(1)



    if args.schema:
        # a schema was specified on the command line... try and read it.
        try:
            with open(args.schema, "r") as schema_file:
                schema = json.load(schema_file)
        except Exception as e:
                print(f"Error: {e}")
                print(f"Cannot read the schema file {args.schema}...\n\n")
                sys.exit(1)
    else:     
        # a schema was NOT specified in a command line argument.
        # pull out the $schema field as specified in the JSON file:
        print(f"No schema was specified as a command-line argument.")
        print(f"Trying to find $schema inside of JSON file...")
        try:
            schema_url = file_contents["$schema"]
            print(f"Schema URL to fetch: {schema_url}")
        except Exception as e:
            print(f"Error: {e}")
            print(f"\n\nThe JSON file may be missing the $schema field...\n\n")
            sys.exit(1)
        # fetch the schema from the URL (http request):
        try:
            schema = requests.get(schema_url, verify=False).json()
        except Exception as e:
            print(f"Error: {e}")
            print(f"Failed to retrieve the schema from the URL...\n\n")
            sys.exit(1)


    # validate ... no output implies success!
    try:
        jsonschema.validate(instance=file_contents, schema=schema)
        print("JSON file is valid per the schema!\n\n")
    except Exception as e:
        if args.verbose:
            print(f"Error: {e}") ## lots of output...
            print("\n\n")
        print(f"JSON file has FAILED schema validation!\n\n")
        sys.exit(1)






if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check that a JSON file adheres to the $schema field within the file."
    )
    
    parser.add_argument(
        "file", 
        type=str, 
        help="the JSON file you want to validate."
    )

    parser.add_argument(
        "--schema", 
        type=str, 
        required=False,
        help="(Optional) schema file.  If used, this will override whatever URL may be listed in the JSON file in the $schema field."
    )
    
    parser.add_argument(
        "-v","--verbose",
        action="store_true",
        default=False,
        help="print verbose error message of why the file may have failed validation."
    )

    args = parser.parse_args()

    main(args)

