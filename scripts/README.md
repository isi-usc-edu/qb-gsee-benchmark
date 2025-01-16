# Scripts

**This directory is primarily used by the benchmark maintainers (repo maintainers).  The casual benchmark enjoyer will probably not use any of the scripts or content here.**


Several of these scripts rely on authentication keys to fetch material from the SFTP server.  Contact the repository maintainers for key files.

## Calculating Hamiltonian features

`./compute_all_ham_features_script.py`

```bash
-h, --help            show this help message and exit
-i INPUT_DIR, --input_dir INPUT_DIR
                    The directory that contains the problem_instance JSON files.
--ham_features_file HAM_FEATURES_FILE
                    The file name of the Hamiltonian features (.csv) file. If the file already exists, new data rows will be added to it. A backup copy is also made at the beginning
                    of the script.
--sftp_username SFTP_USERNAME
                    username for the SFTP server where FCIDUMP files are stored.
--sftp_key_file SFTP_KEY_FILE
                    local/path/to/the/keyfile for the SFTP server corresponding to sftp_username.
```
The primary output is an updated `Hamiltonian_features.csv`.  The `Hamiltonian_features.csv` is an input to the `miniML.py` functions that explore the space and difficulty of solving various Hamiltonians.

**WARNING!** The calculation of Hamiltonian features requires a compute platform with a significant amount of memory.  Thankfully, running this script is only required if new Hamiltonians are added to the set of problem instances.





## Generating logical quantum resource estimates as `solution.json` files.

`./compute_all_LREs_script.py`

```bash
options:
-h, --help            show this help message and exit
-i INPUT_DIR, --input_dir INPUT_DIR
                    Specify directory for problem_instances (.json files)
-o OUTPUT_DIR, --output_dir OUTPUT_DIR
                    Specify directory to save resource estimates to (.json files)
--LRE_config_file LRE_CONFIG_FILE
                    A JSON file with configuration options and hyperparameters for LRE and a `solver` UUID.
--sftp_username SFTP_USERNAME
                    username for SFTP server where FCIDUMP files are stored.
--sftp_key_file SFTP_KEY_FILE
                    local/path/to/the/keyfile for the SFTP server (corresponding to sftp_username)
```

The script will generate logical quantum resource estimates for a subset of Hamiltonians from the `problem_instance.json` files.  The resource estimates are output as a set of `solution.json` files (one `solution.json` file for each `problem_instance.json` file).  The subset of problems attempted depends on the number of orbitals is less than some threshold specified in the `LRE_config_overlaps.json` file and the availability of an overlap in the `overlaps.csv` file.

This script is currently based on the qubitized quantum phase estimation with double factorization algorithm.


## Generating physical quantum resource estimates as `solution.json` files.

`./compute_all_PREs_script.py`

```bash
options:
  -h, --help            show this help message and exit
  -i INPUT_DIR, --input_dir INPUT_DIR
                        Specify directory for solution logical resource estiamtes (.json files)
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR
                        Specify directory to save physical resource estimates to (.json files)
  --PRE_config_file PRE_CONFIG_FILE
                        A JSON file with configuration options and hyperparameters for PRE and a `solver` UUID.
```

This script ingests solution files containing logical resource estimates and generates new solution files that contain physical resource estimates.
Note that these solution files will have new solution IDs that differ from the input LRE solution files.
It is also recommended to specify a solver UUID in the PRE config file that is different from the solver UUID for the LRE.
See [`PRE_config.json`](PRE_config.json) for an example PRE config file.






## Generating `performance_metrics.json` files

`./compute_all_performance_metrics_script.py`

```bash
options:
  -h, --help            show this help message and exit
  --problem_instance_dir PROBLEM_INSTANCE_DIR
                        Specify directory for problem_instances (.json files). This is input.
  --solution_file_dir SOLUTION_FILE_DIR
                        Specify directory for solution.json files. This is input.
  --performance_metrics_dir PERFORMANCE_METRICS_DIR
                        Specify directory for performance_metrics.json files. Freshly calculated performance_metrics.json files will be placed here.
  --ham_features_file HAM_FEATURES_FILE
                        The/path/to/the Hamiltonian features (.csv) file. Hamiltonian features in this .csv file are solver-agnostic.
```


The script ingests all available `problem_instance.json` and `solution.json` files and, for each solver identified by `solver_uuid`, returns a `performance_metrics.solver_uuid.json` file.  Note that *many* `solution.json` files are ingested for one `solver_uuid` and only a single `performance_metrics.solver_uuid.json` is returned.  This `performance_metrics.solver_uuid.json` contains performance metrics broken down to the Hamiltonian and aggregated to higher levels. 

The script also produces the `aggregated_solver_labels_<date>.csv` artifact file.  The `aggregated_solver_labels_<date>.csv` and the `Hamiltonian_features.csv` file are used by the `miniML.py` functions to calculate the ML scores which appear as fields in the `performance_metrics.json` file.  Note that the `Hamiltonian_features.csv` is calculated by a different script and should be up-to-date before running this script.

