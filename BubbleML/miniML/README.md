# miniML script


The `miniML.py` script is primarily responsible for generating the *solvability ratio* performance metric of a solver over the set of `problem_instances`.   Output plots and other files are placed in a nearby directory called `ml_artifacts`. 


Help message (`./miniML.py --help`):

```bash
usage: miniML.py [-h] --ham_features_file HAM_FEATURES_FILE --config_file CONFIG_FILE --solver_uuid SOLVER_UUID --solver_labels_file
                 SOLVER_LABELS_FILE [-v]

train an ML model using `Hamiltonian_features.csv` and `solver_labels.csv`. The model attempts to predict the True/False solvability of a set of
Hamiltonian features (input vector).

options:
  -h, --help            show this help message and exit
  --ham_features_file HAM_FEATURES_FILE
                        The/path/to/the Hamiltonian features (.csv) file. Hamiltonian features are solver-agnostic.
  --config_file CONFIG_FILE
                        The/path/to/the miniML_config.json file that specifies the Hamiltonian features that should be considered for the ML
                        model.
  --solver_uuid SOLVER_UUID
                        the UUID for the solver. A `solver` is defined as an algorithm/hardware pair and assigned a UUID for tracking.
  --solver_labels_file SOLVER_LABELS_FILE
                        The/path/to/the solver_labels.csv file. The labels are True/False to indicate that a solver can find the ground state
                        energy of a Hamiltonian (by FCIDUMP UUID).
  -v, --verbose         provide verbose output

```


Example call:

```bash
./miniML.py -v --ham_features_file ../../data/Hamiltonian_features/experimental/fast_double_factorization_features/Hamiltonian_features.csv --config_file miniML_config.json --solver_uuid 16537433-9f4c-4eae-a65d-787dc3b35b59 --solver_labels_file ../../scripts/solver_labels.DMRG_Niagara_cluster_lowest_energy.16537433-9f4c-4eae-a65d-787dc3b35b59.csv --verbose
```

Note that the `solver_uuid` is specific to the DMRG algorithm running on a specific compute platform in this example.

If the `--verbose` flag is included, then a `plot_<solver_uuid, datestamp>.png` plot and the `probs<solver_uuid, datestamp>.csv` file will be generated as artifacts.
