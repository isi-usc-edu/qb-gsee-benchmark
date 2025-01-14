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



from qb_gsee_benchmark.utils import data_frame_vlookup
from qb_gsee_benchmark.utils import BenchmarkData

import pprint
import pandas as pd





benchmark_data = BenchmarkData(
    hamiltonian_features_csv_file_name="/home/labuser/Projects/qb-gsee-benchmark/scripts/Hamiltonian_features.csv",
    utility_estimation_csv_file_name="/home/labuser/Projects/qb-gsee-benchmark/scripts/GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv",
    problem_instances_directory="/home/labuser/Projects/qb-gsee-benchmark/problem_instances",
    solution_files_directory="/home/labuser/Projects/qb-gsee-benchmark/solution_files",
    performance_metrics_directory="/home/labuser/Projects/qb-gsee-benchmark/performance_metrics"
)
print(benchmark_data)













################################################################################
## STEP 1:  Find `task_uuid` for each molecule listed in CCSDT .csv sheet.



ccsdt = pd.read_csv("/home/labuser/Projects/qb-gsee-benchmark/scripts/fixes/small_molecules_and_transition_metals_features_vdz.csv")



df = pd.DataFrame()

for i in range(len(ccsdt)):
    molecule_name = ccsdt["molecule_name"].iloc[i]
    n_orbs = ccsdt["n_orbs"].iloc[i]
    n_elec = ccsdt["n_elec"].iloc[i]
    ccsdt_max_vertex_degree = ccsdt["max_vertex_degree"].iloc[i]

    found_it = False
    task_uuid = None
    duplicate_molecule_name = None
    
    for problem_instance in benchmark_data.problem_instance_list:
        problem_instance_short_name = problem_instance["short_name"]

        for task in problem_instance["tasks"]:
            try: 
                mol_name = task["features"]["molecule_name"]
                if molecule_name == mol_name:
                    
                    num_orbitals = task["features"]["num_orbitals"]
                    num_electrons = task["features"]["num_electrons"]
                    if num_orbitals == n_orbs and num_electrons == n_elec:
                       
                        # print(f"{molecule_name} {n_elec} {n_orbs}")
                        # pprint.pprint(task)
                        # x = input("do you think we found it?  type k.  any other letter will quit.")
                        # if x == "k":
                        found_it = True
                        task_uuid = task["task_uuid"]

                        ccsdt_max_vertex_degree = ccsdt["max_vertex_degree"].iloc[i]

                        hf_max_vertex_degree= data_frame_vlookup(
                            df=benchmark_data.hamiltonian_features,
                            lookup_value=task_uuid,
                            lookup_value_column_header="task_uuid",
                            find_value_column_header="max_vertex_degree"
                        )

                        if ccsdt_max_vertex_degree == hf_max_vertex_degree:
                            print("WE HAVE A MATCH!")
                        
                        break # break out of task loop
            except Exception as e:
                continue
        
        if found_it:
            break # break out of problem_instance loop
        else:
            continue



    duplicate_molecule_name = len(ccsdt[ccsdt["molecule_name"]==molecule_name]) > 1

    if found_it:
        # n_orbs = ccsdt[ccsdt["molecule_name"]==molecule_name]["n_orbs"]
        # num_orbitals = data[data["instance_data_object_url"]==instance_data_object_url]["num_orbitals"]
        print(f"maybe found: {molecule_name} in {task_uuid}...")
        new_row = pd.DataFrame([{
            "molecule_name":molecule_name,
            "duplicate_molecule_name":duplicate_molecule_name,
            "task_uuid":task_uuid,
            "num_electrons":num_electrons,
            "num_orbitals":num_orbitals
        }])

    else:
        print(f"didn't find: {molecule_name} in {task_uuid}")
        new_row = pd.DataFrame([{
            "molecule_name":molecule_name,
            "duplicate_molecule_name":duplicate_molecule_name,
            "task_uuid":None,
            "num_electrons":n_elec,
            "num_orbitals":n_orbs
        }])  
    
    if len(df) == 0:
        df = new_row
    else:
        df = pd.concat([df, new_row], ignore_index=True)
    


df.to_csv("ccsdt_organizer.csv",index=False)




################################################################################
## STEP 2:  merge `task_uuid` into the original results DataFrame



ccsdt_organizer = pd.read_csv("/home/labuser/Projects/qb-gsee-benchmark/scripts/fixes/ccsdt_organizer.csv")
print(len(ccsdt_organizer))

# filter to only lines with task_uuid located (i.e., not NaN)
ccsdt_organizer = ccsdt_organizer.dropna(subset=["task_uuid"])
print(len(ccsdt_organizer))


ccsdt_organizer["matching_key"] = \
    ccsdt_organizer["molecule_name"] \
    + ccsdt_organizer["num_electrons"].astype(str) \
    + ccsdt_organizer["num_orbitals"].astype(str)
print(len(ccsdt_organizer))
print(ccsdt_organizer["matching_key"].nunique())
assert len(ccsdt_organizer) == ccsdt_organizer["matching_key"].nunique(), "not unique enough!!"


ccsdt = pd.read_csv("/home/labuser/Projects/qb-gsee-benchmark/scripts/fixes/small_molecules_and_transition_metals_features_vdz.csv")
ccsdt["matching_key"] = \
    ccsdt["molecule_name"] \
    + ccsdt["n_elec"].astype(str) \
    + ccsdt["n_orbs"].astype(str) # n_elec and n_orbs legacy fields... eventually transition to num_electrons and num_orbitals.
assert len(ccsdt) == ccsdt["matching_key"].nunique(), "not unique enough!!"


ccsdt_results = pd.merge(
    ccsdt,
    ccsdt_organizer,
    on="matching_key",
    how="inner",
    # how=inner only match rows that by task_uuid that exist in either file (possibly fewer rows).
    # how=outer fill in NaN when merging if uuids missing from either file.
    suffixes=("", "_2") # some column headers may be duplicated.
)

print(len(ccsdt_results))

ccsdt_results.to_csv("ccsdt_results_with_task_uuid.csv",index=False)


