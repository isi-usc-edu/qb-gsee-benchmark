# QB-GSEE-Benchmark

QB-GSEE-Benchmark is a comprehensive suite for benchmarking Ground State Energy Estimation (GSEE) algorithms developed by the DARPA Quantum Benchmarking (QB) Program. This tool enables performers to run a subset of Hamiltonian instances and assess the performance of their algorithms in terms of accuracy, runtime, and hardware utilization.

## What is QB-GSEE-Benchmark?

This repository includes:
- A curated list of Hamiltonian [`problem_instances`](./problem_instances/) for benchmarking.
- Example code to access and process these instances.
- Scripts to evaluate and summarize the performance of GSEE algorithms.

Performers will generate solution files that detail:
- Estimated energies or accuracies
- Computation runtime
- Hardware specifications
- Other relevant metrics

These solution files can then be used with this tool to generate comprehensive performance summaries and interface with the "Bubble ML" GUI for advanced performance exploration.

## Installation

Clone this repository to get started:
```bash
git clone https://github.com/yourusername/qb-gsee-benchmark.git
cd qb-gsee-benchmark
```
Install with:
```bash
pip install -e .
```

## Obtaining SFTP credentials
Generating features, solutions, and resource estimates requires access to an SFTP server that hosts FCIDUMPs and other large files.
Accessing this server requires a PPK file which contains appropriate credentials and also an associated username.
Contact the repository maintainers to get these.

## Usage

### Generating Logical Quantum Resource Estimates

The [`scripts/compute_all_LREs_script.py`](scripts/compute_all_LREs_script.py) script can be used to generate LQREs.
In order to run this script, first ensure that the qb-gsee-benchmark package is installed as described above.
Then, several files are required:

* A PPK file containing a key to access the SFTP server that provides access to FCIDUMP files as described above.
* A configuration file similar to [`scripts/LRE_config.json`](scripts/LRE_config.json) or [`scripts/LRE_config.json`](scripts/LRE_config_overlaps.json) which specifies algorithm parameters, solver UUID, and other information.
* If the `algorithm_parameters` object in the config file specifies a value for `overlap_csv`, then this CSV file must also be present. See for example [`scripts/overlaps.csv`](scripts/overlaps.csv)

The paths to these files must be passed as arguments to the script, for example:
```bash
python compute_all_LREs_script.py -i ../problem_instances -o ../solution_files --LRE_config_file LRE_config.json --sftp_username darpa-qb --sftp_key_file path_to_ppk_file
```

### Generating Physical Quantum Resource Estimates

Given a set of solution files containing logical quantum resource estimates, the [`scripts/compute_all_PREs_script.py`](scripts/compute_all_PREs_script.py) script can be used to generate physical resource estimates.
In addition to having solution files with LREs, you also must have a configuration file similar to [`scripts/PRE_config.json`](scripts/PRE_config.json) which specifies hardware parameters and other information.
The newly generated solution files will contain runtime estimates and physical quantum resources.
Note that these solution files will have new solution IDs that differ from the input LRE solution files.
It is also recommended to specify a solver UUID in the PRE config file that is different from the solver UUID for the LRE.

The PREs can be generated using a command such as:
```bash
python compute_all_LREs_script.py -i LRE_solution_files -o ../solution_files -PLRE_config_file PRE_config.json
```

<!-- ### Viewing Results
After running the benchmarks, generate a summary of performance:
```bash
python summarize_performance.py solution_file.json
```


### Exploring with BubbleML
Launch the Bubble ML GUI to visualize and explore performance details:
```bash
python bubble_ml_gui.py
``` -->

## Contributing

Contributions to the QB-GSEE-Benchmark are welcome! Please consider the following steps:
- Fork the repository.
- Create a feature branch (`git checkout -b feature-branch`).
- Commit your changes (`git commit -am 'Add some feature'`).
- Push to the branch (`git push origin feature-branch`).
- Open a Pull Request.

WARNING!  Nightly GitHub actions are configured to validate JSON files against their associated [schema](./schemas/).  If a file does not pass validation, it will be moved to the [`json_files_with_errors`](./json_files_with_errors/) directory.


## License

This project is licensed under the Apache License, Version 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This software was developed as a part of [DARPA Quantum Benchmarking program](https://www.darpa.mil/program/quantum-benchmarking).
