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


import argparse
import datetime
import json
import logging
import math
import os
import sys
from importlib.metadata import version
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4
import time
from pprint import pprint


from pyscf.tools import fcidump

import pandas as pd
from pyLIQTR.utils.resource_analysis import estimate_resources

from qb_gsee_benchmark.qre import get_df_qpe_circuit
from qb_gsee_benchmark.utils import retrieve_fcidump_from_sftp
from qb_gsee_benchmark.utils import iso8601_timestamp
from qb_gsee_benchmark.utils import load_json_files

DOUBLE_FACTORIZED_ATTRIBUTES = [
    "L",
    "nL",
    "nXi",
    "nLXi",
    "phase_gradient_eps",
    "energy_error",
    "step_error",
    "bits_rot_givens",
    "keep_bitsize",
    "keep_bitsize_outer",
    "outer_prep_eps",
    "alpha",
]

logger = logging.getLogger()
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler("hubbard_LREs.log.txt", delay=False)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handlers = [console_handler, file_handler]
for h in handlers:
    h.setFormatter(formatter)
    logger.addHandler(h)



overlaps_df = pd.read_csv("overlaps.csv")
overlaps = {
    row["task_uuid"]: row["overlap"] for index, row in overlaps_df.iterrows()
}


solution_data: list[dict[str, Any]] = []
results: dict[str, Any] = {}



for fcidump_file in os.listdir("./FCIDUMP_hubbard_hartree_fock_orbitals"):
    fcidump_file_path = os.path.join("./FCIDUMP_hubbard_hartree_fock_orbitals", fcidump_file)
    fci = fcidump.read(fcidump_file_path)
    num_orbitals = fci["H1"].shape[0]
    
    error_tolerance = 0.00159
    failure_tolerance = 1 - 0.99
    overlap = 0.8

    circuit_generation_start_time = datetime.datetime.now()
    (
        circuit,
        num_shots,
        hardware_failure_tolerance_per_shot,
    ) = get_df_qpe_circuit(
        fci=fci,
        error_tolerance=error_tolerance,
        failure_tolerance=failure_tolerance,
        square_overlap=overlap**2,
        sf_threshold=1e-12,
        df_threshold=1e-3,
    )
    circuit_generation_end_time = datetime.datetime.now()
    logging.info(
        f"Circuit initialization time: {(circuit_generation_end_time - circuit_generation_start_time).total_seconds()} seconds."
    )
    logging.info(f"Estimating logical resources...")
    resource_estimation_start_time = datetime.datetime.now()
    logical_resources = estimate_resources(circuit.circuit)
    resource_estimation_end_time = datetime.datetime.now()
    LRE_calc_time = (
        resource_estimation_end_time - resource_estimation_start_time
    ).total_seconds()
    logging.info(f"Resource estimation time (seconds): {LRE_calc_time}")

    block_encoding = circuit._block_encoding
    solution_data.append(
        {
            "task_uuid": fcidump_file,
            "error_bound": error_tolerance,
            "confidence_level": 1 - failure_tolerance,
            "quantum_resources": {
                "logical": {
                    "num_logical_qubits": logical_resources["LogicalQubits"],
                    "num_T_gates_per_shot": logical_resources["T"],
                    "num_shots": math.ceil(num_shots),
                    "hardware_failure_tolerance_per_shot": hardware_failure_tolerance_per_shot,
                }
            },
            "solution_details": {
                "block_encoding_details": {
                    attribute: getattr(block_encoding, attribute)
                    for attribute in DOUBLE_FACTORIZED_ATTRIBUTES
                },
                "overlap": overlap,
                "num_bits_precision_qpe": circuit._prec,
            },
            "run_time": {
                "preprocessing_time": {
                    "wall_clock_start_time": circuit_generation_start_time.strftime(
                        "%Y-%m-%dT%H:%M:%S.%f"
                    )
                    + "+00:00",
                    "wall_clock_stop_time": circuit_generation_end_time.strftime(
                        "%Y-%m-%dT%H:%M:%S.%f"
                    )
                    + "+00:00",
                    "seconds": (
                        circuit_generation_end_time
                        - circuit_generation_start_time
                    ).total_seconds(),
                },
            },
        }
    )

    solver_details = {
        "solver_uuid": 7777777777,
        "solver_short_name": "DF_QPE",
        "compute_hardware_type": "quantum_computer",
        "algorithm_details": {
            "algorithm_description": 777777,
            "algorithm_parameters": 77777777,
        },
        "software_details": [
            {"software_name": "pyLIQTR", "software_version": version("pyLIQTR")},
            {
                "software_name": "qb-gsee-benchmark",
                "software_version": version("qb-gsee-benchmark"),
            },
            {"software_name": "Python", "software_version": sys.version},
        ],
    }
    results = {
        "$schema": "https://raw.githubusercontent.com/isi-usc-edu/qb-gsee-benchmark/refs/heads/main/schemas/solution.schema.0.0.1.json",
        "solution_uuid": str(uuid4()),
        "problem_instance_uuid": 88888888888,
        "creation_timestamp": iso8601_timestamp(),
        "is_resource_estimate": True,
        "contact_info": 77777777,
        "solution_data": solution_data,
        "compute_hardware_type": "quantum_computer",
        "solver_details": solver_details,
        "digital_signature": None,
    }

    pprint(results)
