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


from qb_gsee_benchmark.utils import iso8601_timestamp
from qb_gsee_benchmark.utils import validate_json
from qb_gsee_benchmark.utils import get_file_sha1sum
from pyscf import gto, scf, fci, lib
# set the number of threads PySCF uses to 1 (no multithreading)
lib.num_threads(1)

from pyscf.tools import fcidump
import gzip
import shutil
import json
import os


################################################################################
boilerplate_fields = {
    "$schema": "https://raw.githubusercontent.com/isi-usc-edu/qb-gsee-benchmark/main/schemas/problem_instance.schema.0.0.1.json",
    "references": [],
    "creation_timestamp": iso8601_timestamp(),
    "latest_update_timestamp": iso8601_timestamp(),
    "calendar_due_date": None,
    "license": {
        "name": "Apache 2.0",
        "url": "http://www.apache.org/licenses/LICENSE-2.0"
    },
    "contact_info": [
        {
            "name": "BOBQAT Team",
            "email": "bobqat@l3harris.com",
            "institution": "L3Harris Technologies, Inc.",
            "website":"www.l3harris.com"
        },
        {
            "name": "Joshua T. Cantin",
            "email": "joshua.cantin@utoronto.ca",
            "institution": "University of Toronto at Scarborough"
        }
    ],
    "status": "in_force",
    "superseded_by": None,
    "problem_type": "GSEE",
    "application_domain": "QC"
}




instances = []

################################################################################
# H instance:
problem_instance_uuid = "3aa01b76-53e2-49e8-bc05-72875168a00a"
task_uuid = "4e1617a3-7a5f-4c86-99b6-4cfc8b547197"
instance_data_object_uuid = "0b245a9c-7561-423d-bd50-8958b3625a94"
molecule_name = "H.cc-PVDZ"
short_name = f"validation.{molecule_name}"
instances.append({
    "problem_instance_uuid":problem_instance_uuid,
    "short_name":short_name,
    "tasks": [
        {
            "task_uuid": "4e1617a3-7a5f-4c86-99b6-4cfc8b547197",
            "features": {
                "molecule_name": molecule_name,
                "geometry": "H 0 0 0",
                "geometry_units": "angstrom",
                "basis_set": "cc-PVDZ",
                "charge": 0,
                # "multiplicity": 2,
                "spin": 1, 
                "num_electrons": "UPDATED-LATER",
                "num_orbitals": "UPDATED-LATER"
            },
            "requirements": {
                "probability_of_success": 0.99,
                "time_limit_seconds": 2592000,
                "absolute_accuracy_threshold": 0.00159362,
                "absolute_accuracy_threshold_energy_units": "Hartree",
                "reference_energy": "UPDATED-LATER",
                "reference_energy_units": "Hartree",
                "reference_energy_source": "Exact FCI solution in PySCF 2.8.0, with multithreading disabled.",
                "reference_energy_method": "Exact FCI solution in PySCF 2.8.0, with multithreading disabled."
            },
            "supporting_files": [
                {
                    "instance_data_object_uuid": instance_data_object_uuid,
                    "instance_data_object_url": f"sftp://sftp.l3harris.com/gsee/validation_instances/{short_name}.{instance_data_object_uuid}.fcidump.gz",
                    "instance_data_checksum": "TO-BE-UPDATED",
                    "instance_data_checksum_type": "sha1sum"
                }
            ]
        }
    ]
})





################################################################################
# H2 instance:
problem_instance_uuid = "9162371c-b23f-45a6-bacd-44cb7aaea917"
task_uuid = "4e1617a3-7a5f-4c86-99b6-4cfc8b547197"
instance_data_object_uuid = "bbcd09f2-8a89-4f35-9577-7851a76ea17c"
molecule_name = "H2.cc-PVDZ"
short_name = f"validation.{molecule_name}"
instances.append({
    "problem_instance_uuid":problem_instance_uuid,
    "short_name":short_name,
    "tasks": [
        {
            "task_uuid": task_uuid,
            "features": {
                "molecule_name": molecule_name,
                "geometry": "H -0.3705 0 0; H 0.3705 0 0",
                "geometry_units": "angstrom",
                "basis_set": "cc-PVDZ", 
                "charge": 0,
                "multiplicity": 1,
                "spin": 0, 
                "num_electrons": "UPDATED-LATER",
                "num_orbitals": "UPDATED-LATER",
                "utility_scale":False
            },
            "requirements": {
                "probability_of_success": 0.99,
                "time_limit_seconds": 2592000,
                "absolute_accuracy_threshold": 0.00159362,
                "absolute_accuracy_threshold_energy_units": "Hartree",
                "reference_energy": "UPDATED-LATER",
                "reference_energy_units": "Hartree",
                "reference_energy_source": "Exact FCI solution in PySCF 2.8.0, with multithreading disabled.",
                "reference_energy_method": "Exact FCI solution in PySCF 2.8.0, with multithreading disabled."
            },
            "supporting_files": [
                {
                    "instance_data_object_uuid": instance_data_object_uuid,
                    "instance_data_object_url": f"sftp://sftp.l3harris.com/gsee/validation_instances/{short_name}.{instance_data_object_uuid}.fcidump.gz",
                    "instance_data_checksum": "TO-BE-UPDATED",
                    "instance_data_checksum_type": "sha1sum"
                }
            ]
        }
    ]
})






################################################################################
# He instance:
problem_instance_uuid = "036fc218-6a9c-4d49-88a4-930f5ebb5ae6"
task_uuid = "3e803f97-2478-4630-a7a3-12fbc69f7666"
instance_data_object_uuid = "00243a50-3f5c-44da-99c8-021ac2214cba"
molecule_name = "He.cc-PVDZ"
short_name = f"validation.{molecule_name}"
instances.append({
    "problem_instance_uuid":problem_instance_uuid,
    "short_name":short_name,
    "tasks": [
        {
            "task_uuid": task_uuid,
            "features": {
                "molecule_name": molecule_name,
                "geometry": "He 0 0 0",
                "geometry_units": "angstrom",
                "basis_set": "cc-PVDZ", 
                "charge": 0,
                "multiplicity": 1,
                "spin": 0,
                "num_electrons": "UPDATED-LATER",
                "num_orbitals": "UPDATED-LATER",
                "utility_scale":False
            },
            "requirements": {
                "probability_of_success": 0.99,
                "time_limit_seconds": 2592000,
                "absolute_accuracy_threshold": 0.00159362,
                "absolute_accuracy_threshold_energy_units": "Hartree",
                "reference_energy": "UPDATED-LATER",
                "reference_energy_units": "Hartree",
                "reference_energy_source": "Exact FCI solution in PySCF 2.8.0, with multithreading disabled.",
                "reference_energy_method": "Exact FCI solution in PySCF 2.8.0, with multithreading disabled."
            },
            "supporting_files": [
                {
                    "instance_data_object_uuid": instance_data_object_uuid,
                    "instance_data_object_url": f"sftp://sftp.l3harris.com/gsee/validation_instances/{short_name}.{instance_data_object_uuid}.fcidump.gz",
                    "instance_data_checksum": "TO-BE-UPDATED",
                    "instance_data_checksum_type": "sha1sum"
                }
            ]
        }
    ]
})












################################################################################
# LiH instance:
problem_instance_uuid = "00ec23d5-3e17-46d3-a8b6-9ceff1826377"
task_uuid = "2b2eefc4-9c8c-4a02-b621-059774f620c4"
instance_data_object_uuid = "7298a64d-1574-42d7-b092-3e9f686ec162"
molecule_name = "LiH.cc-PVDZ"
short_name = f"validation.{molecule_name}"
instances.append({
    "problem_instance_uuid":problem_instance_uuid,
    "short_name":short_name,
    "tasks": [
        {
            "task_uuid": task_uuid,
            "features": {
                "molecule_name": molecule_name,
                "geometry":"Li 0 0 0; H 0 0 1.596",
                "geometry_units": "angstrom",
                "basis_set": "cc-PVDZ", 
                "charge": 0,
                "multiplicity": 1,
                "spin": 0,
                "num_electrons": "UPDATED-LATER",
                "num_orbitals": "UPDATED-LATER",
                "utility_scale":False
            },
            "requirements": {
                "probability_of_success": 0.99,
                "time_limit_seconds": 2592000,
                "absolute_accuracy_threshold": 0.00159362,
                "absolute_accuracy_threshold_energy_units": "Hartree",
                "reference_energy": "UPDATED-LATER",
                "reference_energy_units": "Hartree",
                "reference_energy_source": "Exact FCI solution in PySCF 2.8.0, with multithreading disabled.",
                "reference_energy_method": "Exact FCI solution in PySCF 2.8.0, with multithreading disabled."
            },
            "supporting_files": [
                {
                    "instance_data_object_uuid": instance_data_object_uuid,
                    "instance_data_object_url": f"sftp://sftp.l3harris.com/gsee/validation_instances/{short_name}.{instance_data_object_uuid}.fcidump.gz",
                    "instance_data_checksum": "TO-BE-UPDATED",
                    "instance_data_checksum_type": "sha1sum"
                }
            ]
        }
    ]
})




















################################################################################
# merge in boilerplate fields/vals.
for instance in instances:
    instance.update(boilerplate_fields) 



################################################################################
# build each FCIDUMP file
fcidump_file_list = []
for instance in instances:
    
    short_name = instance["short_name"]
    print(f"\n{short_name}")

    data_uuid = instance["tasks"][0]["supporting_files"][0]["instance_data_object_uuid"]

    fcidump_file_name = f"{short_name}.{data_uuid}.fcidump"
    fcidump_file_list.append(fcidump_file_name)

    features = instance["tasks"][0]["features"]

    mol = gto.M(
        atom=features["geometry"],
        basis=features["basis_set"],
        unit=features["geometry_units"], # should be angstrom
        spin=features["spin"],
        charge=features["charge"]
    )
    mol.build()
    print(f"geometry units: {mol.unit}")
    mf = scf.RHF(mol)
    mf.max_cycle=10000
    mf.conv_tol=1e-14
    hf_energy_hartree = mf.kernel()
    hf_energy_eV = 27.211386245981*hf_energy_hartree
    print(f"HF energy in eV: {hf_energy_eV}")
    fcidump.from_scf(mf, fcidump_file_name)
    print(f"wrote {fcidump_file_name}")



################################################################################
# create compressed versions of the FCIDUMP files:
for fcidump_file in fcidump_file_list:
    with open(fcidump_file, "rb") as f_in:
        with gzip.open(fcidump_file + ".gz", "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)





################################################################################
# update a few fields based on the FCIDUMP file:
for instance in instances:
    short_name = instance["short_name"]
    data_uuid = instance["tasks"][0]["supporting_files"][0]["instance_data_object_uuid"]
    fcidump_file_name = f"{short_name}.{data_uuid}.fcidump"

    print("\n\nsolving for GSE based on the FCIDUMP file alone:")
    fci_params = fcidump.read(fcidump_file_name)

    # update fields straight from the FCIDUMP info:
    instance["tasks"][0]["features"]["num_electrons"] = fci_params["NELEC"] # update JSON
    instance["tasks"][0]["features"]["num_orbitals"] = fci_params["NORB"] # udpate JSON

    # update file checksums
    sha1sum = get_file_sha1sum(fcidump_file_name + ".gz")
    instance["tasks"][0]["supporting_files"][0]["instance_data_checksum"] = sha1sum

    
    # solve for GSEE using FCI for funsies:
    mf = fcidump.to_scf(fcidump_file_name)
    mf.max_cycle = 10000
    mf.conv_tol = 1e-16
    mf.kernel()
    print(f"HF energy: {mf.e_tot}")

    # Solve for GSE using FCI:
    fci_solver = fci.FCI(mf)
    fci_solver.max_cycle = 10000
    fci_solver.max_memory = 8192 
    fci_solver.conv_tol = 1e-14
    fci_solver.conv_tol_residual = 1e-14
    energy, _ = fci_solver.kernel()
    print(f"FCI energy: {energy}")
    instance["tasks"][0]["requirements"]["reference_energy"] = energy # update in JSON.




################################################################################
# validate JSON against the schema
for instance in instances:
    validate_json(instance)


################################################################################
# write out JSON files
for instance in instances:
    short_name = instance["short_name"]
    prob_instance_uuid = instance["problem_instance_uuid"]
    json_file_name = f"problem_instance.{short_name}.{prob_instance_uuid}.json"
    with open(json_file_name, "w") as output_json_file:
            json.dump(
                instance,
                output_json_file,
                indent=4
            )


    
    

################################################################################
# delete the uncompressed FCIDUMP files to avoid confusion:
for fcidump_file in fcidump_file_list:
    os.remove(fcidump_file)


for fcidump_file in fcidump_file_list:
    sha1sum = get_file_sha1sum(fcidump_file + ".gz")
    print(f"{fcidump_file}.gz sha1sum: {sha1sum}")