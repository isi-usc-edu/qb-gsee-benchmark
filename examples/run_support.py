from urllib.parse import urlparse
import urllib.request
import json
import jsonschema
import paramiko
from pathlib import Path
import gzip
import shutil
import io
import dmrghandler.data_processing as dp
import h5py
import numpy as np
import copy
import uuid
import datetime
import os


def fetch_file_from_sftp(
    url=None, local_path=None, ppk_path=None, username=None, port=None
):
    """
    Download a file from an SFTP server using a private key file (.ppk).
    Code by John Penuel, with slight modifications; originates in https://github.com/isi-usc-edu/qb-gsee-benchmark/blob/main/examples/sftp-fetch.ipynb
    Args:
        url (str): The URL of the file to download.
        local_path (str): The local path to save the file.
        ppk_path (str): The path to the private key file (.ppk).
        username (str): The username to use for the SFTP connection.
        port (int): The port to use for the SFTP connection.
    """

    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    remote_path = parsed_url.path.lstrip("/")

    try:
        # Create an SSH client
        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connect using the private key file (.ppk)
            client.connect(
                hostname=hostname, port=port, username=username, key_filename=ppk_path
            )

            # Open an SFTP session
            with client.open_sftp() as sftp:
                sftp.get(remote_path, local_path)

        print(
            f"File fetched successfully from {hostname}: {Path(remote_path).name} -> {local_path}"
        )
    except Exception as e:
        print(f"Error: {e}")


def download_task_fcidump_files(
    chosen_problem_instance_files,
    problem_instance_files_path,
    local_store_path,
    ppk_path,
    sftp_username,
):
    data_file_list = []
    for problem_instance_file in chosen_problem_instance_files:
        with open(problem_instance_files_path / problem_instance_file) as f:
            problem_instance = json.load(f)
        tasks_list = problem_instance["tasks"]

        for task in tasks_list:
            for file_dict in task["supporting_files"]:
                if (
                    "fcidump" in file_dict["instance_data_object_url"]
                    or "FCIDUMP" in file_dict["instance_data_object_url"]
                ):
                    fcidump_url = file_dict["instance_data_object_url"]
                    fcidump_store_path = local_store_path / "fcidumps"
                    fcidump_store_path.mkdir(parents=True, exist_ok=True)
                    local_path = fcidump_store_path / fcidump_url.split("/")[-1]
                    fetch_file_from_sftp(
                        url=fcidump_url,
                        local_path=local_path,
                        ppk_path=ppk_path,
                        username=sftp_username,
                        port=22,
                    )

                    # If compressed, decompress
                    if str(local_path).endswith(".gz"):
                        print(f"Uncompressing {local_path.name}")
                        with gzip.open(local_path, "rb") as f_in:
                            local_path = Path(str(local_path).split(".gz")[0])
                            with open(local_path, "wb") as f_out:
                                shutil.copyfileobj(f_in, f_out)

                    data_file_list.append(local_path)

    return data_file_list


def get_uuid_fcidump_mapping(submit_commands, local_store_path):
    # Get uuid to fcidump mapping
    buf = io.StringIO(submit_commands.split("cd config_store/submit_dir")[0])
    orig_data_dict_list = []
    uuid_fcidump_mapping_dict = {}
    data_lines = buf.readlines()
    for line_iter, line in enumerate(data_lines):
        # print(line)
        if line.startswith("### "):
            continue
        if line.startswith(f"# {local_store_path}/fcidumps/"):
            fcidump_name_temp = line.split("/")[-1].split("#")[0].strip()
            next_line = data_lines[line_iter + 1]
            if not next_line.startswith("sbatch ../"):
                raise ValueError("Expected sbatch line")
            uuid_value = next_line.split("/")[1].strip()
            uuid_fcidump_mapping_dict[uuid_value] = fcidump_name_temp
    return uuid_fcidump_mapping_dict


def collect_dmrg_data(dmrg_hdf5_files, uuid_fcidump_mapping_dict):
    all_dmrgh5_data = {}

    for file in dmrg_hdf5_files:
        print(file)
        with h5py.File(file, "r") as hdf5_file:
            solution_uuid = hdf5_file["parent_folder_name"][()].decode("utf-8")
            FCIDUMP_name = uuid_fcidump_mapping_dict[solution_uuid]
            FCIDUMP_short_name_temp = FCIDUMP_name.split("fcidump.")[-1].split(
                "FCIDUMP_"
            )[-1]

            if len(FCIDUMP_short_name_temp.split(".")[-1]) == len(
                "66d35e58-89f8-4f9c-baa9-e7cbd0c846e4"
            ):
                FCIDUMP_short_name = ".".join(FCIDUMP_short_name_temp.split(".")[:-1])
            else:
                FCIDUMP_short_name = FCIDUMP_short_name_temp

        if FCIDUMP_short_name not in all_dmrgh5_data:
            all_dmrgh5_data[FCIDUMP_short_name] = {}

        if solution_uuid in all_dmrgh5_data[FCIDUMP_short_name]:
            raise ValueError("Duplicate solution uuid")

        (
            dmrg_energies,
            bond_dimensions,
            discarded_weights,
            num_loops,
            num_dmrg_calculations,
            loop_cpu_times_s,
            loop_wall_times_s,
            num_sweeps_list,
            final_sweep_delta_energies_list,
            reordering_method_list,
            reordering_method_cpu_times_s,
            reordering_method_wall_times_s,
            extra_dict,
        ) = dp.get_data_from_incomplete_processing(file)

        min_dmrg_energy_arg = np.argmin(dmrg_energies)
        min_dmrg_energy = dmrg_energies[min_dmrg_energy_arg]
        min_dmrg_energy_bond_dim = bond_dimensions[min_dmrg_energy_arg]
        min_dmrg_energy_discarded_weight = discarded_weights[min_dmrg_energy_arg]
        min_dmrg_energy_loop_cpu_time = loop_cpu_times_s[
            min_dmrg_energy_arg
        ]  # overall_time
        min_dmrg_energy_loop_wall_time = loop_wall_times_s[
            min_dmrg_energy_arg
        ]  # overall_time
        min_dmrg_energy_num_sweeps = num_sweeps_list[min_dmrg_energy_arg]
        min_dmrg_energy_final_sweep_delta_energy = final_sweep_delta_energies_list[
            min_dmrg_energy_arg
        ]
        min_dmrg_energy_reordering_method = reordering_method_list[min_dmrg_energy_arg]
        min_dmrg_energy_reordering_method_cpu_time = reordering_method_cpu_times_s[
            min_dmrg_energy_arg
        ]
        min_dmrg_energy_reordering_method_wall_time = reordering_method_wall_times_s[
            min_dmrg_energy_arg
        ]

        min_dmrg_energy_preprocessing_sum = (
            float(
                extra_dict["loop_driver_initialize_system_wall_time_s_list"][
                    min_dmrg_energy_arg
                ]
            )
            + float(
                extra_dict["loop_generate_initial_mps_wall_time_s_list"][
                    min_dmrg_energy_arg
                ]
            )
            + float(
                extra_dict["loop_get_qchem_hami_mpo_wall_time_s_list"][
                    min_dmrg_energy_arg
                ]
            )
            + float(
                extra_dict["loop_reorder_integrals_wall_time_s_list"][
                    min_dmrg_energy_arg
                ]
            )
            + float(
                extra_dict["loop_make_driver_wall_time_s_list"][min_dmrg_energy_arg]
            )
        )

        min_dmrg_energy_preprocessing_sum_cpu = (
            float(
                extra_dict["loop_driver_initialize_system_cpu_time_s_list"][
                    min_dmrg_energy_arg
                ]
            )
            + float(
                extra_dict["loop_generate_initial_mps_cpu_time_s_list"][
                    min_dmrg_energy_arg
                ]
            )
            + float(
                extra_dict["loop_get_qchem_hami_mpo_cpu_time_s_list"][
                    min_dmrg_energy_arg
                ]
            )
            + float(
                extra_dict["loop_reorder_integrals_cpu_time_s_list"][
                    min_dmrg_energy_arg
                ]
            )
            + float(extra_dict["loop_make_driver_cpu_time_s_list"][min_dmrg_energy_arg])
        )

        min_dmrg_energy_algorithm_run_time = float(
            extra_dict["loop_dmrg_optimization_wall_time_s_list"][min_dmrg_energy_arg]
        )

        min_dmrg_energy_postprocessing_time = float(
            extra_dict["loop_copy_mps_wall_time_s_list"][min_dmrg_energy_arg]
        )

        min_dmrg_energy_algorithm_run_cpu_time = float(
            extra_dict["loop_dmrg_optimization_cpu_time_s_list"][min_dmrg_energy_arg]
        )

        min_dmrg_energy_postprocessing_cpu_time = float(
            extra_dict["loop_copy_mps_cpu_time_s_list"][min_dmrg_energy_arg]
        )

        dmrg_data_dict = {
            "dmrg_energy": min_dmrg_energy,
            "bond_dimension": min_dmrg_energy_bond_dim,
            "discarded_weight": min_dmrg_energy_discarded_weight,
            "loop_cpu_time": min_dmrg_energy_loop_cpu_time,
            "loop_wall_time": min_dmrg_energy_loop_wall_time,
            "num_sweeps": min_dmrg_energy_num_sweeps,
            "final_sweep_delta_energy": min_dmrg_energy_final_sweep_delta_energy,
            "reordering_method": min_dmrg_energy_reordering_method,
            "reordering_method_cpu_time": min_dmrg_energy_reordering_method_cpu_time,
            "reordering_method_wall_time": min_dmrg_energy_reordering_method_wall_time,
            "preprocessing_time": min_dmrg_energy_preprocessing_sum,
            "preprocessing_cpu_time": min_dmrg_energy_preprocessing_sum_cpu,
            "algorithm_run_time": min_dmrg_energy_algorithm_run_time,
            "postprocessing_time": min_dmrg_energy_postprocessing_time,
            "algorithm_run_cpu_time": min_dmrg_energy_algorithm_run_cpu_time,
            "postprocessing_cpu_time": min_dmrg_energy_postprocessing_cpu_time,
        }

        all_dmrgh5_data[FCIDUMP_short_name][solution_uuid] = copy.deepcopy(
            dmrg_data_dict
        )

    return all_dmrgh5_data


def filter_lowest_energy_data(all_dmrgh5_data):
    filtered_data = {}

    for FCIDUMP_short_name, solution_data in all_dmrgh5_data.items():
        min_energy = np.inf
        min_energy_uuid = None
        for solution_uuid, dmrg_data in solution_data.items():
            if dmrg_data["dmrg_energy"] < min_energy:
                min_energy = dmrg_data["dmrg_energy"]
                min_energy_uuid = solution_uuid

        filtered_data[FCIDUMP_short_name] = {"solution_uuid": min_energy_uuid}
        filtered_data[FCIDUMP_short_name].update(solution_data[min_energy_uuid])

    return filtered_data


def map_fcidump_to_problem_instances(
    chosen_problem_instance_files, problem_instance_files_path, all_dmrgh5_data
):
    prob_inst_data_sol_dict = {}
    print(chosen_problem_instance_files)

    for prob_inst_file in chosen_problem_instance_files:
        prob_inst_file_path = problem_instance_files_path / prob_inst_file
        with open(prob_inst_file_path) as f:
            prob_inst_data = json.load(f)
        prob_inst_uuid = prob_inst_data["problem_instance_uuid"]
        task_list = prob_inst_data["tasks"]

        for task in task_list:
            task_uuid = task["task_uuid"]
            supporting_files = task["supporting_files"]
            for supp_file in supporting_files:
                if (
                    "fcidump" in supp_file["instance_data_object_url"]
                    or "FCIDUMP" in supp_file["instance_data_object_url"]
                ):
                    FCIDUMP_url = supp_file["instance_data_object_url"]
                    FCIDUMP_uuid = supp_file["instance_data_object_uuid"]
                    break

            relevant_fcidump_short_name = None
            FCIDUMP_url_test = FCIDUMP_url
            print(FCIDUMP_url_test)
            if "benzene" in FCIDUMP_url_test:
                print(
                    "Benzene found----------------------------------------------------"
                )
                FCIDUMP_url_test = FCIDUMP_url_test.replace("benzene", "b")
                print(FCIDUMP_url_test)

            for dmrg_solution_fcidump_short_name in all_dmrgh5_data.keys():
                if "V1" in dmrg_solution_fcidump_short_name:
                    print(dmrg_solution_fcidump_short_name)

                if (
                    "/fcidump." + dmrg_solution_fcidump_short_name + "."
                    in FCIDUMP_url_test
                    or "/FCIDUMP_" + dmrg_solution_fcidump_short_name + "."
                    in FCIDUMP_url_test
                    or "/FCIDUMP_" + dmrg_solution_fcidump_short_name + "_"
                    in FCIDUMP_url_test
                ):
                    relevant_fcidump_short_name = dmrg_solution_fcidump_short_name
                    break

            if prob_inst_uuid not in prob_inst_data_sol_dict:
                prob_inst_data_sol_dict[prob_inst_uuid] = {
                    "prob_inst_file": prob_inst_file_path,
                    "prob_inst_short_name": prob_inst_data["short_name"],
                }

            if relevant_fcidump_short_name is None:
                print(
                    f"Could not find relevant fcidump short name for {FCIDUMP_url}, assuming solution not available."
                )
                print(prob_inst_uuid)
                print(task_uuid)
                prob_inst_data_sol_dict[prob_inst_uuid].update(
                    {task_uuid: "NO SOLUTION"}
                )
                continue

            prob_inst_data_sol_dict[prob_inst_uuid][task_uuid] = {
                "solution_uuid": all_dmrgh5_data[relevant_fcidump_short_name][
                    "solution_uuid"
                ],
                "instance_data_object_uuid": FCIDUMP_uuid,
                "instance_data_object_url": FCIDUMP_url,
                "dmrg_data": all_dmrgh5_data[relevant_fcidump_short_name],
            }

    return prob_inst_data_sol_dict


def create_solution_files(
    prob_inst_data_sol_dict,
    solution_save_location,
    json_solution_schema_url_file,
    contact_info,
    solver_details,
):
    for prob_inst_uuid, prob_inst_data in prob_inst_data_sol_dict.items():
        solution_file_uuid = str(uuid.uuid4())
        print(prob_inst_data.keys())
        print(prob_inst_data.items())
        Path(solution_save_location).mkdir(parents=True, exist_ok=True)
        prob_inst_sol_file = Path(solution_save_location) / Path(
            f"solution.{prob_inst_data['prob_inst_short_name']}.{prob_inst_uuid}_{solution_file_uuid}.json"
        )

        # Timestamp in ISO 8601 format in UTC (note the `Z`) with final Z
        creation_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Replace the time zone shift with Z
        creation_timestamp = creation_timestamp[:-6] + "Z"
        prob_inst_sol_data = {
            "$schema": json_solution_schema_url_file,
            "solution_uuid": solution_file_uuid,
            "problem_instance_uuid": prob_inst_uuid,
            "creation_timestamp": creation_timestamp,
            "contact_info": contact_info,
            "is_resource_estimate": False,
            "solution_data": [],
            "solver_details": solver_details,
            "digital_signature": None,
        }
        for task_uuid, task_data in prob_inst_data.items():
            if len(task_uuid) != len("66d35e58-89f8-4f9c-baa9-e7cbd0c846e4"):
                continue

            if task_data == "NO SOLUTION":
                continue
            dmrg_data = task_data["dmrg_data"]

            overall_time = dmrg_data["loop_wall_time"]
            preprocessing_time = dmrg_data["preprocessing_time"]
            algorithm_run_time = dmrg_data["algorithm_run_time"]
            postprocessing_time = dmrg_data["postprocessing_time"]
            overall_cpu_time = dmrg_data["loop_cpu_time"]
            preprocessing_cpu_time = dmrg_data["preprocessing_cpu_time"]
            algorithm_run_cpu_time = dmrg_data["algorithm_run_cpu_time"]
            postprocessing_cpu_time = dmrg_data["postprocessing_cpu_time"]
            # Verify algorithm_run_time is a float
            if not isinstance(algorithm_run_time, float):
                raise ValueError("algorithm_run_time is not a float")

            run_time = {
                "overall_time": {"seconds": overall_time},
                "preprocessing_time": {"seconds": preprocessing_time},
                "algorithm_run_time": {"seconds": algorithm_run_time},
                "postprocessing_time": {"seconds": postprocessing_time},
            }
            run_time_cpu = {
                "overall_time": {"seconds": overall_cpu_time},
                "preprocessing_time": {"seconds": preprocessing_cpu_time},
                "algorithm_run_time": {"seconds": algorithm_run_cpu_time},
                "postprocessing_time": {"seconds": postprocessing_cpu_time},
            }
            solution_details = {
                "instance_data_object_url": task_data["instance_data_object_url"],
                "bond_dimension": dmrg_data["bond_dimension"],
                "discarded_weight": dmrg_data["discarded_weight"],
                "calculation_uuid": task_data["solution_uuid"],
            }
            solution_dict = {
                "task_uuid": task_uuid,
                "energy": dmrg_data["dmrg_energy"],
                "energy_units": "Hartree",
                "run_time": run_time,
                "run_time_cpu": run_time_cpu,
                "solution_details": solution_details,
            }
            prob_inst_sol_data["solution_data"].append(solution_dict)
        with open(prob_inst_sol_file, "w") as f:
            json.dump(prob_inst_sol_data, f, indent=4)
            print(f"Saved {prob_inst_sol_file}")
        prob_inst_data["file_name"] = prob_inst_sol_file

def validate_solution_files(json_solution_schema_url, prob_inst_data_sol_dict):
    # Validate the solution json files against the schema
    schema_filepath = Path("temp_sol_schema.json")

    # Download schema
    urllib.request.urlretrieve(json_solution_schema_url, schema_filepath.name)
    schema = json.load(open(schema_filepath))

    for prob_inst_uuid, prob_inst_data in prob_inst_data_sol_dict.items():
        prob_inst_sol_file = prob_inst_data["file_name"]
        print(prob_inst_sol_file)
        jsonschema.validate(json.load(open(prob_inst_sol_file)), schema)
        print(f"Validated {prob_inst_sol_file}")

    # Remove schema file
    schema_filepath.unlink()
