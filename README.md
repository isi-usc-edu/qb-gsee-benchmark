# QB-GSEE-Benchmark

QB-GSEE-Benchmark is a comprehensive suite for benchmarking Ground State Energy Estimation (GSEE) algorithms.  QB-GSEE-Benchmark was developed by the DARPA Quantum Benchmarking (QB) Program. This tool enables performers to run a subset of Hamiltonian instances and assess the performance of their algorithms in terms of accuracy, runtime, and hardware utilization.  Although this work was developed for the Quantum Benchmarking program, the benchmark is hardware agnostic and classical computing algorithm/hardware developers are encouraged to participate.

## What is QB-GSEE-Benchmark?

This repository includes:
- A curated set of [`problem_instance.json` files](./problem_instances/).
  - See [`summary.csv`](summary.csv).
  - Each `problem_instance.json` contains a relevant family of Hamiltonians in a list of `tasks`.
  - In some cases, the list only contains one Hamiltonian.
  - The `problem_instance.json` file specifies the requirements for accuracy and run time.
  - The Hamiltonians are large FCIDUMP files.  The `problem_instance.json` file contains a URL to where the FCIDUMP file can be downloaded.  In most cases, the FCIDUMP files are stored at [`sftp.L3Harris.com`](sftp.L3Harris.com).  Contact the maintainers for credentials.  
- A set of [`solution.json` files](./solution_files/)
  - Some solution files were submitted representing classical algorithms (e.g., DMRG).
  - Some solution files are "quantum resource estimates" which include estimates for the number of logical qubits, T-gates, and estimates of run time for a given quantum algorithm (e.g., qubitized quantum phase estimation with double factorization).  Resource estimation gives us an idea of how large of a quantum computer would be required to be meet or exceed classical algorithm/hardware performance.
  - The hope is that eventually some solution files will be submitted based on the performance of actual quantum computing hardware, and thus we can compare the performance of real quantum computing hardware/algorithms to classical hardware/algorithms.
- A set of [`performance_metrics.json` files](./performance_metrics/)
  - For one particular compute platform or "solver"--which is a combination of algorithm/hyperparameters/hardware and uniquely identified by `solver_uuid`--the QB-GSEE-Benchmark repository contains scripts to calculate a `performance_metrics.json` file.  
  - The `performance_metrics.json` file compares the solver's performance against all `problem_instance.json` files, even if the solver did not attempt them (i.e., the solver did not submit a `solution.json` file for a `problem_instance.json` or did not attempt to solve all Hamiltonians in the set of `tasks` within a `problem_instance.json` file.)
  - The `performance_metrics.json` file contains performance metrics broken down by Hamiltonian and aggregated to other levels. 

We rely on [universally unique identifiers (UUID, version 4)](https://en.wikipedia.org/wiki/Universally_unique_identifier) to track multiple solvers, problem instances, solution files, performance metrics files, and other results.  By convention, UUIDs tend to appear in file names to ensure that files are not overwritten by other outputs.  By [schema](./schemas), UUIDs are required fields inside of most JSON files.  

## Use cases

As a **classical algorithm/hardware developer**, I want to test my new algorithm/hardware against the benchmark problems and get a score.
- Download the subset of `problem_instance.json` files you want to attempt.  For each `problem_instance.json`, submit one `solution.json` file with your results (runtime and energy estimate).
- Ensure that the `solution.json` file you submit adheres to our [schema](./schemas/).
- Run the `scripts/compute_all_performance_metrics.py` script to generate performance metrics and scores and locate your results file. 
- Included in this repository is the `examples/run_dmrg.ipynb` notebook, which demonstrates how to run density matrix renormalization group (DMRG) calculations on a choice of problem instance files and then produce solution files. Running instructions are included in the notebook.

As a **quantum algorithm/hardware developer**, I want to test my new algorithm/hardware against the benchmark problems and get a score. 
- If your quantum compute hardware exists, then proceed in the same way as the classical algorithm/hardware developer.
- If your hardware doesn't actually exist yet, you may submit a `solution.json` file that *estimates the quantum resources required to solve the problem*.
- Again, for each `problem_instance.json` file, submit one `solution.json` file.
- Ensure that the `solution.json` file you submit adheres to our [schema](./schemas/).
- Run the `scripts/compute_all_performance_metrics.py` script to generate performance metrics and scores and locate your results file. 
- Included in this repository is the `scripts/compute_all_LREs_script.py`, which will estimate logical quantum resources for a subset of the problem instances based on qubitized quantum phase estimation with double factorization.

As an **investor or budget/policymaker**, I want to compare the performance of various hardware/software platforms to determine where investment should be made.
- Standard reports and other output products are still in development.  What reports, charts or leader boards would you like to see?

As a **competition host**, I want to host a competition between various compute platforms using the benchmark instances.
- The repository contains some "planted solution" problem instances, which are obfuscated Hamiltonians with known ground state energies.  
- Other ideas for generating new "planted solutions" are in development.  Currently, we use [https://github.com/jtcantin/planted_solutions](https://github.com/jtcantin/planted_solutions).
- Planted solution Hamiltonians may be generated with various features, difficulty or sizes.
- A competition set of planted-solution Hamiltonians may be generated as `problem_instance.json` files in advance of the competition and published at the start of the competition.  A required calendar due date for `solution.json` files may be specified.

As an **industry or academic expert**, I want to contribute new or suggest changes to existing `problem_instance.json` files.
- Ensure the `problem_instance.json` files you generate adhere to our [schemas](./schemas/). 
- This repository has automatic validation in place to move non-compliant JSON files to the `json_files_with_errors` directory until they are fixed.
 
As a **maintainer of this repository**, I want to ensure all artifacts and results are up-to-date.
- This benchmark is a prototype and currently relies on several important scripts in the [`/scripts`](./scripts/) directory. See [`/scripts/README.md`](./scripts/README.md) for more information.
- All outputs from the scripts are based on the `problem_instances.json` and `solution.json` files.


All users may also be interested in the "Bubble ML" GUI/tool for advanced performance exploration through the space of Hamiltonians.  


## Installation

Clone this repository to get started:
```bash
git clone https://github.com/isi-usc-edu/qb-gsee-benchmark.git
cd qb-gsee-benchmark
```
Install with:
```bash
pip install -e .
```


## Contributing

Contributions to the QB-GSEE-Benchmark are welcome! Please consider the following steps:
- Fork the repository.
- Create a feature branch (`git checkout -b feature-branch`).
- Commit your changes (`git commit -am 'Add some feature'`).
- Push to the branch (`git push origin feature-branch`).
- Open a pull request.

As a reminder, GitHub actions are configured to validate JSON files against their associated [schema](./schemas/).  If a file does not pass validation, it will be moved to the [`json_files_with_errors`](./json_files_with_errors/) directory.


## License

This project is licensed under the Apache License, Version 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This software was developed as a part of [DARPA Quantum Benchmarking program](https://www.darpa.mil/program/quantum-benchmarking).
