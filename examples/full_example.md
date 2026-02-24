# Full Example


The goal of this document is to guide the novice benchmark repo maintainer through the functionality.


## Installation

This example was tested with Python version 3.10 on Ubuntu Linux 22.04.


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
>>> from qb_gsee_benchmark.utils import get_file_sha1sum
>>> get_file_sha1sum("examples/obfuscated_sftp_server_key.bin")
'cee7323a366eb0a792fca0ccd9ece5693a9814b5'
```



## Set up your keys to fetch data from the SFTP server

Change directories to the `examples` folder if you haven't already.

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

| JSON Field Name              | UUID                                      | Comments                |
|-----------------------------|--------------------------------------------|-------------------------|
| problem_instance_uuid       | e0f6ed02-6502-454b-bf2c-e7994e0510f4       |                         |
| task_uuid                   | 443371ce-c80d-450d-b281-ac1c4d5ecc4d       | There may be multiple tasks for each problem instance.  In this case, there is only one.  A "task" corresponds to a single Hamiltonian to estimate ground state energy for.   |
| instance_data_object_uuid   | a7321b5d-4730-4ace-9ff8-734ec07f3fef       | There may be multiple data objects for each task.  This is the official Hamiltonian File (FCIDUMP format)   |
| instance_data_object_uuid   | 02b1e2b3-66f7-4004-9f27-94d407ab51e1       | There may be multiple data objects for each task.  This is the associated check file.   |


### Calculate Hamiltonian Features

WARNING!  Calculating Hamiltonian features only needs to be done when NEW problem instances are added.  The calculation may take a long time and consume lots of memory.  In practice, a VM with 8 CPU, 256GB of RAM and extra SWAP provisioned was used.

Really we will *update* the `scripts/Hamiltonian_features.csv` file.  To do so, we will run the `scripts/compute_all_ham_features_script.py`.  The script is smart enough to first look at the existing entries in the .csv file (by task UUID) and ignore them.  If a new problem instance (with new task UUIDs) is submitted, the script will calculate the features and update the .csv.  If you want to re-calculate Hamiltonian features for an existing task UUID, you should delete the entry from the .sv file and run the script.  That is exactly what we will do in this example for Methane.

0. Change directory to `scripts`.
1. Locate the `Hamiltonian_features.csv` file.
2. Make a backup copy of it.
3. Locate the line/entry associated with task_uuid 443371ce-c80d-450d-b281-ac1c4d5ecc4d and delete the line.

Now we will run the script.
```
# view help/usage:
./compute_all_ham_features_script.py --help
```

The following is an example call to the script that assumes you are already in the `scripts` directory and you have put your SFTP server key in the `.ssh` directory.
```
./compute_all_ham_features_script.py --input_dir ../problem_instances --ham_features_file Hamiltonian_features.csv --sftp_username darpa-qb --sftp_key_file ~/.ssh/darpa-qb-key.pem
```
You should see a lot of output that is basically reporting that it is skipping the calculation for all of the task UUIDs because they are already done.  It will stop when it finds the task UUID for methane and realizes it is NOT in the .csv file (because you deleted that entry for this example).  For this methane example, the computation takes about 10 minutes and about 4GiB of memory. 

During the process, the following files are manipulated:
0. A backup copy of `Hamiltonian_features.csv` is automatically created as `Hamiltonian_features.csv.backup-YYYY-MM-DD-HH-mm.csv`.  This is not removed automatically.  If all goes well, the user may remove it.
1. Per the URL in the problem instance file `problem_instances/small_molecules/problem_instance.c_h4_0.e0f6ed02-6502-454b-bf2c-e7994e0510f4.json`, the Hamiltonian FCIDUMP file `fcidump.c_h4_cc-pVDZ.a7321b5d-4730-4ace-9ff8-734ec07f3fef.gz` will be downloaded from the SFTP server.  If all goes well, the FCIDUMP file will be removed when the script finishes.  
2. The script appends log message to `scripts/compute_all_ham_features_script.log.txt` for troubleshooting.  The log file should be cleared out periodically.
3. A file containing the double factorized eigenvalues of the data object ID is saved as `double_factorized_eigs.a7321b5d-4730-4ace-9ff8-734ec07f3fef.bin`.  This is not removed automatically  The file is currently not used and may be removed.  Future versions of the script may not write out the file.  
4. Per this example, the `Hamiltonian_features.csv` file should have a new entry in it for Methane.  Verify it!


### Calculate Logical Resource Estimates for the DF-QPE Algorithm

TODO

### Calculate Physical Resource Estimates for the DF-QPE Algorithm with some Hardware Assumptions

TODO

### Calculate performance metrics and update the "standard report"

TODO














