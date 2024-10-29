#!/usr/bin/env python3


# Copyright 2023 L3Harris Technologies, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import json
import csv
import sys
sys.path.append("../")
import os
import datetime


def main(args):
    input_directory = args.input
    output_csv_file_name = args.output

    print("started at ",datetime.datetime.utcnow().isoformat())
    print("input directory: ", input_directory)
    print("output file: ", output_csv_file_name)

    csv_field_names = ["count","file_name", "problem_instance_uuid", "team", "creation_timestamp", "short_name", "number_of_hamiltonians"]
    count = 0

    with open(output_csv_file_name, mode="w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_field_names)
        writer.writeheader()

        json_files = os.listdir(input_directory)
        for json_file in json_files:
            json_file_path = input_directory + "/" + json_file
            print("parsing",json_file_path)
            with open(json_file_path, "r") as jf:
                problem_instance = json.load(jf)
                
                # populate "row" data for csv file
                # NOTE: some fields are not simply key/values 
                # from the problem_instance dict.
                row = {}

                count += 1
                row["count"] = count

                row["file_name"] = json_file
                row["problem_instance_uuid"] = problem_instance["problem_instance_uuid"]
                team_name = ""
                for team in problem_instance["contact_info"]:
                    team_name += team["name"] + "/"
                row["team"] = team_name


                row["creation_timestamp"] = problem_instance["creation_timestamp"]
                row["short_name"] = problem_instance["short_name"]
                
                row["number_of_hamiltonians"] = len(problem_instance["instance_data"])

                # write "row" data for csv file.
                writer.writerow(row)

    print("done")
    




if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a summary .csv file for problem_instances"
    )

    parser.add_argument(
        "-i", 
        "--input", 
        type=str, 
        help="Specify directory for problem_instances (.json files)"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Specify output file name"
    )

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
    else:
        main(args)

