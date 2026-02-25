# Full Example


The goal of this document is to guide the novice benchmark repo maintainer through the functionality.

WARNING!  During the course of running through this example, you will create some temporary files and directories that we don't want living on in the Github repository.  For the purposes of this example, it's best to create a separate clone/folder of the repo, run through these examples, and then just discard the separate clone/folder.


## Installation

This example was tested with Python version 3.12.2 (latest supported of Python to be used with PyLIQTR 1.4.2 as of 25-Feb 2026) on Ubuntu Linux 22.04.


Clone this repository to get started:
```
git clone https://github.com/isi-usc-edu/qb-gsee-benchmark.git
cd qb-gsee-benchmark
```

It's optional, but recommended, to create and activate a Python virtual environment
```
python -m venv .venv
source .venv/bin/activate
```

Install the modules and dependencies with
```
pip install -e .
```

Test the installation by entering the Python interpreter and attempting to import a function
```
>>> from qb_gsee_benchmark.utils import iso8601_timestamp
>>> iso8601_timestamp()
'2026-02-25T15:36:20.702104+00:00'
```



## Set up your keys to fetch data from the SFTP server

Change directory to the `examples` folder.

```
# get the SFTP server key
./get_sftp_key.py  
# creates darpa-qb-key.pem file.

# test fetch a Hamiltonian
./fetch_file_from_sftp_server.py
# downloads the file fcidump.c_h4_cc-pVDZ.a7321b5d-4730-4ace-9ff8-734ec07f3fef.gz
```

Optional, but recommended to move this key to a location where keys are typically stored:
```
mv darpa-qb-key.pem ~/.ssh/.
```

You may delete the file `fcidump.c_h4_cc-pVDZ.a7321b5d-4730-4ace-9ff8-734ec07f3fef.gz`.





## Example Workflow

We will go through the full workflow of analysis for a "small molecule" $CH_4$ methane.  

Methane is described in `problem_instances/small_molecules/problem_instance.c_h4_0.e0f6ed02-6502-454b-bf2c-e7994e0510f4.json`.  

The `problem_instance.json` file contains two tasks (by UUID)

1. task UUID: 443371ce-c80d-450d-b281-ac1c4d5ecc4d, Methane with CC-pVDZ basis
2. task UUID: f936469c-1d1e-4295-a006-84a778c1714c, Methane with CC-pVTZ basis 

Each "task" corresponds with one Hamiltonian.

For each task/Hamiltonian, the problem instance file has a few supporting files and URLs pointing to those files.  The files are currently on the SFTP server, but may be elsewhere in the future.  For Methane with the CC-pVDZ basis set there are two files:

1.  `sftp://sftp.l3harris.com/gsee/small_molecules/fcidump.c_h4_cc-pVTZ.47a5eadf-e31e-4c38-983f-8c75460463ea.gz`
2.  `sftp://sftp.l3harris.com/gsee/small_molecules/c_h4_cc-pVTZ.6e2fb98f-f4d8-47c9-a4f4-496999541f0d.chk`

The first is the FCIDUMP file, which is the official Hamiltonian file for the benchmark problem instance.  Any other files may be related or informational files, but are not used.  During this example, we will use scripts that will download the official FCIDUMP Hamiltonian file and calculate features and resource estimates for it.


### Calculate Hamiltonian Features

WARNING!  Calculating Hamiltonian features only needs to be done when NEW problem instances are added.  The calculation may take a long time and consume lots of memory.  In practice, a VM with 8 CPU, 256GB of RAM and extra SWAP provisioned was used.

Really we will *update* the `scripts/Hamiltonian_features.csv` file.  To do so, we will run the `scripts/compute_all_ham_features_script.py`.  The script is smart enough to first look at the existing entry-lines in the .csv file (by task UUID) and ignore them.  If a new problem instance (with new task UUIDs) is submitted, the script will calculate the features and update the .csv with new entry-lines.  If you want to re-calculate Hamiltonian features for an existing task UUID, you should delete the entry-line from the .csv file and run the script.  That is exactly what we will do in this example for Methane.

0. Change directory to `scripts`.
1. Locate the `Hamiltonian_features.csv` file.
2. Locate the entry-line associated with task_uuid 443371ce-c80d-450d-b281-ac1c4d5ecc4d and delete the line.

Now we will run the script.
```
# first view help/usage:
./compute_all_ham_features_script.py --help
```

The following is an example call to the script that assumes you are already in the `scripts` directory and you have put your SFTP server key in the `.ssh` directory.  Adjust this to match your own folder structure.
```
./compute_all_ham_features_script.py --input_dir ../problem_instances --ham_features_file Hamiltonian_features.csv --sftp_username darpa-qb --sftp_key_file ~/.ssh/darpa-qb-key.pem
```
You should see a lot of output that is basically reporting that it is skipping the calculation for most of the task UUIDs because they are already done and present in the `Hamiltonian_features.csv` file.  It will stop when it finds the task UUID for methane and realizes it is NOT in the .csv file (because you deleted that entry for the purposes of this example).  For this methane example, the computation takes about 10 minutes and about 4GiB of memory. 

During the process, the following files are manipulated:

0. A backup copy of `Hamiltonian_features.csv` is automatically created as `Hamiltonian_features.csv.backup-YYYY-MM-DD-HH-mm.csv`.  This is not removed automatically.  If all goes well, you may remove it.
1. Per the URL in the problem instance file `problem_instances/small_molecules/problem_instance.c_h4_0.e0f6ed02-6502-454b-bf2c-e7994e0510f4.json`, the Hamiltonian FCIDUMP file `fcidump.c_h4_cc-pVDZ.a7321b5d-4730-4ace-9ff8-734ec07f3fef.gz` will be downloaded from the SFTP server.  If all goes well, the FCIDUMP file will be removed automatically when the script finishes.  
2. The script appends log messages to `scripts/compute_all_ham_features_script.log.txt` for troubleshooting.  The log file should be cleared out periodically.
3. A file containing the double factorized eigenvalues of the data object ID is saved as `double_factorized_eigs.a7321b5d-4730-4ace-9ff8-734ec07f3fef.bin`.  This is not removed automatically  The file is currently not used and may be removed.  Future versions of the script may not write out the file.  
4. Per this example, the `Hamiltonian_features.csv` file should have a new entry in it for Methane.  Verify it!


### Calculate Logical Resource Estimates for the DF-QPE Algorithm

As a reminder, not all of these sections/steps need to be done all the time.  This is simply an example that walks one Hamiltonian all the way through.  In most scenarios, other benchmark performers submit their new `solution.json` data.  

For the purposes of this example, we will calculate logical resource estimates (LREs) *for the specific algorithm of* Double Factorized Quantum Phase Estimation (DF-QPE).  An LRE estimation script for DF-QPE is provided in this repository as an example quantum algorithm.  We do NOT plan to develop resource estimate methods/scripts for other quantum algorithms.  A benchmark performer that has a new algorithm they wish to promote using this benchmark should develop their own resource estimation software (presumably in their own code repository) and provide the penultimate `solution.json` files that include the logical resource estimates as well as physical resource estimates (e.g., estimated wall-clock runtime).

For the Methane example (task UUID 443371ce-c80d-450d-b281-ac1c4d5ecc4d), we first look for the `scripts/overlaps.csv` file and determine if we have an entry for the task UUID.  

Prerequisite files in the `scripts` directory:
1. `LRE_config_overlaps.json` (or `LRE_config.json` assumes flat 0.8 overlap) contains some parameters used for the DF-QPE algorithm and tracking data that will be inserted into the output LRE JSON files.
2. `overlaps.csv` contains the estimate of ground state overlap with the dominant configuration state function for a subset of instances.
 

Run the script:
```
# first view help/usage:
./compute_all_LREs_script.py --help
```

The `compute_all_LREs_script.py` is smart enough to look for jobs that have already been done in the output directory and skip them.  Logical resource estimates are really an intermediate product before the final product of physical resource estimates, so we usually keep a working folder of LRE results in the `scripts` directory.  As of the latest, this is the `LRE_solution_files_before_PRE_YYYYMMDD` directory.  For the purposes of this example, we are going to create a new, empty input directory `temp_problem_instances` with only one problem instance in it: `problem_instance.c_h4_0.e0f6ed02-6502-454b-bf2c-e7994e0510f4.json` and an empty output directory `temp_LRE_20260224`. 
```
./compute_all_LREs_script.py --input_dir temp_problem_instances --output_dir temp_LRE_20260224 --LRE_config_file LRE_config_overlaps.json --sftp_username darpa-qb --sftp_key_file ~/.ssh/darpa-qb-key.pem
```

If this is the first time you have called the script, it will download and compile Julia and Julia libraries.  This will take a while, but only happens once.  Not including the Julia download/install, this example takes about 5 minutes to run.

The script will open the `problem_instance.c_h4_0.e0f6ed02-6502-454b-bf2c-e7994e0510f4.json` file and take note of the two tasks in it.  For each task, it will download the FCIDUMP file from the SFTP server and analyze it.  Per the `LRE_config_overlaps.json` (or `LRE_config.json`), there is a maximum orbital limit.  It will process the Methane Hamiltonian with the CC-pVDZ basis set with 34 orbitals but will not process the Methane Hamiltonian with the CC-pVTZ basis set with 86 orbitals.  The orbital limit is a limitation of compute host memory and PyLIQTR and may be increased in the future.

Look in the `temp_LRE_YYYYMMDD` (whatever empty output folder you set up) and find the JSON file.  Open the file to review logical resource estimates of 
```
"task_uuid": "443371ce-c80d-450d-b281-ac1c4d5ecc4d",
"error_bound": 0.00159362,
"confidence_level": 0.99,
"quantum_resources": {
    "logical": {
        "num_logical_qubits": 1428,
        "num_T_gates_per_shot": 33710661438304,
        "num_shots": 9,
        "hardware_failure_tolerance_per_shot": 0.0001111605249424219
    }
```
Note: results from 24-Feb 2026, PyLIQTR version 1.4.2.  Your results may vary slightly as PyLIQTR is refined.

### Calculate Physical Resource Estimates for the DF-QPE Algorithm with some Hardware Assumptions

Now we will turn the logical resource estimate (LRE) into a physical resource estimate (PRE), complete with the performance metric of wall-clock run time.  Note that the logical/physical resource estimates are all based on parameters that drive the algorithm to the required accuracy requirements ("chemical accuracy") and probability of success.  So the "accuracy" performance metric for a quantum algorithm is a moot point.  The only performance metric of interest is wall-clock run time.  (Hardware manufacturers are also interested in quantum resources required: gates, logical qubits, physical qubits, etc.)


Run the script:
```
# view help/usage:
./compute_all_PREs_script.py --help
```

Note that there is also a the script consumes all LRE input files in the input folder and calculates PREs for each based on the `PRE_config_file` argument.  In production, we also have `compute_all_PREs_for_all_PRE_configs.sh` shell script that calls the `./compute_all_PREs_script.py` repeatedly with different PRE config files.

We will use the `PRE_config_0.0001_1us_parallel.json`.  The description inside of the config file states "Optimistic superconducting hardware model based on that described in https://arxiv.org/abs/2011.03494. Assumes that enough QPUs are available to run all shots in parallel."  (So we area only calculating wall-clock run time for one execution of the DF-QPE circuit, with some additional assumptions on hardware, error correction, error rate, etc.)

Create an empty output directory `temp_PRE_YYYYMMDD` and call the script approximately as
```
./compute_all_PREs_script.py --input_dir temp_LRE_20260224/ --output_dir temp_PRE_20260224 --PRE_config_file PRE_config_0.0001_1us_parallel.json 
```

The `compute_all_PREs_script.py` runs quickly, so we didn't configure it to check to see if work is already done.  If a PRE was already calculated, the script will calculate another!  So clear out the output directory before re-running it.


Investigate the output JSON file and note that it now contains `run_time/overall_time/seconds` which is the performance metric we are most interested in because it allows us to compare a quantum algorithm/platform with a classical algorithm/platform.
```
"task_uuid": "443371ce-c80d-450d-b281-ac1c4d5ecc4d",
"error_bound": 0.00159362,
"confidence_level": 0.99,
"quantum_resources": {
    "logical": {
        "num_logical_qubits": 1428,
        "num_T_gates_per_shot": 33710661438304,
        "num_shots": 9,
        "hardware_failure_tolerance_per_shot": 0.0001111605249424219
    },
    "physical": {
        "num_physical_qubits": 2167516,
        "distillation_layer_1_code_distance": 11,
        "distillation_layer_2_code_distance": 19,
        "data_code_distance": 21,
        "data_routing_overhead": 0.5,
        "num_factory_physical_qubits": 278272,
        "num_logical_compiled_qubits": 2142,
        "num_qpus": 9
    }
},
"run_time": {
    "overall_time": {
        "seconds": 629968254.488452
    }
}
```
Note: results from 24-Feb 2026, PyLIQTR version 1.4.2.  Your results may vary slightly as PyLIQTR is refined.

In production, these new physical resource estimate `solution.json` files should be manually moved to the `solution_files` folder, possibly replacing (updating) the PRE solutions that currently live there.



### Calculate performance metrics and update the "standard report"

After all the `Hamiltonian_features.csv` and `solution.json` files have been updated, it's time to refresh the "Standard Report".  

In the `scripts` directory:
```
# First view help/usage
./update_all_results.py --help
```

Note that the `update_all_results.py` script can be run in `--production` mode or in `--temp_results` or some other combinations.  `--production` will override all options, do everything it needs to do, and update the results in the `standard_report` directory.

For this example, let's run the `--temp_results` option.  Earlier in this example we created temporary directories to calculate one LRE/PRE at a time.  For this section of the example, we will run the `update_all_results.py` script over all problem instances and all solutions.  

Note that the `update_all_results.py` has some aspects of the repository folder structure hard-coded and expects certain folders to be in their relative positions.

Call the script as
```
./update_all_results.py --temp_results --validate_json --data_to_csv
```

Some of the machine learning (ML) artifacts are placed in `scripts/ml_artifacts` as the computation runs.  In future runs, it will use these cached values.  Clear out the `ml_artifacts` directory to force it to re-calculate them.  This is primarily for the SHAP values for each solver, which take some time to calculate.

This repo runs on JSON files, but if you used the `--data_to_csv` argument, it will flatten all of the JSON data into a rather large `all_data_YYYYMMDD.csv` file.  This is moved to the `standard_report` directory in a production run for posterity.

Visit the `scripts/temp_results/standard_report` to view the standard report in PDF, HTML or markdown format (same content, different formats for portability).

The folder `scripts/temp_results/performance_metrics` has the latest compiled `performance_metric.json` files.  If this were a production run, they would replace the JSON files in the top-level `performance_metrics` folder.  

Finally the `scripts/temp_results/resource_estimate_files_YYYYMMDD` is a collection of JSON files that the QB program sponsor used for charts.  They are not used any more within this repository and may be deleted.  




## Cleanup

In the process of this example you created a few files and directories.  We don't want those artifacts living on in the github repository.  You may delete your entire clone of the repo and start over, or if you are comfortable using `git` you may run 
```
git fetch origin
git reset --hard origin/main
```























