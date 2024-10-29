################################################################################
# © Copyright 2024 Zapata Computing Inc.
################################################################################
"""This script will generate logical resource estimates using PyLIQTR for the mn_mono
benchmark instance. It will save the results to a JSON file.

The algorithm performance model is similar to that described in arXiv:2406.06335v1, but
with a few simplifying assumptions. First, the ground-state overlap is assumed to be
0.8. Second, the double-factorized truncation threshold is assumed to be 1e-3 Ha.

In order to run this script to work, you must have credentials with read access the
L3Harris SFTP server. QB performers can obtain the PPK file with credentials from the
basecamp thread linked below. The `ppk_path` variable should be set to the path of the
PPK file.

https://3.basecamp.com/3613864/buckets/26823103/messages/7222735635
"""

import json
import time
from typing import Any

import requests
from pyLIQTR.utils.resource_analysis import estimate_resources

from qb_gsee_benchmark.qre import get_df_qpe_circuit
from qb_gsee_benchmark.utils import retrieve_fcidump_from_sftp

ppk_path = "/Users/maxradin/.ssh/darpa-qb-key.ppk"
username = "darpa-qb"


url = "https://raw.githubusercontent.com/jp7745/qb-gsee-problem-instances/main/problem_instances/problem_instance.mn_mono.cb40f3f7-ffe8-40e8-4544-f26aad5a8bd8.json"
response = requests.get(url)
if response.status_code != 200:
    raise RuntimeError(f"Failed to retrieve {url}. Status code: {response.status_code}")

problem_instance = response.json()

solution_data: list[dict[str, Any]] = []

results = {}
for instance in problem_instance["instance_data"]:
    print(
        f"Getting logical resource estimates for {instance['instance_data_object_uuid']}..."
    )
    fci = retrieve_fcidump_from_sftp(
        instance["instance_data_object_url"], username=username, ppk_path=ppk_path
    )

    start = time.time()
    circuit, num_shots, hardware_failure_tolerance_per_shot = get_df_qpe_circuit(
        fci=fci,
        error_tolerance=1.6e-3,
        failure_tolerance=1e-2,
        square_overlap=0.8**2,
        df_threshold=1e-3,
    )
    preprocessing_time = time.time() - start
    print(f"Initialized circuit in {preprocessing_time} seconds.")
    print(f"Estimating logical resources...")
    logical_resources = estimate_resources(circuit.circuit)

    results[instance["instance_data_object_uuid"]] = {
        "num_logical_qubits": logical_resources["LogicalQubits"],
        "num_t": logical_resources["T"],
        "preprocessing_time": preprocessing_time,
        "num_shots": num_shots,
        "hardware_failure_tolerance_per_shot": hardware_failure_tolerance_per_shot,
    }

with open(f"lqre-{problem_instance['problem_instance_uuid']}.json", "w") as f:
    json.dump(results, f)
