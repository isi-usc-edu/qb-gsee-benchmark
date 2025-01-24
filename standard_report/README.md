# GSEE Benchmark Standard Report

Report based on data from 2025-01-24T22:30:00.577981+00:00

[https://github.com/isi-usc-edu/qb-gsee-benchmark](https://github.com/isi-usc-edu/qb-gsee-benchmark)

Input data: `Hamiltonian_features.csv`, last modified Mon Dec 30 16:29:03 2024

WARNING!  We only have features calculated for                             230/276 Hamiltonians.                             This report is based on partial results!

Input data: `GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv`, last modified Thu Jan  9 12:11:19 2025

Latest creation time for a `problem_instance.json` file: Fri Jan 24 15:12:37 2025

Latest creation time for a `solution.json` file: Fri Jan 24 15:33:26 2025

# Problem Instance Summary Statistics

number of `problem_instances`: 84.

`problem_instance.json` with the most tasks: 30 (hubbard_square/614c4444-a31a-4348-b24d-01040208651c)

number of Hamiltonians (i.e., tasks) we have features calculated for: 230

minimum number of orbitals: 6

median number of orbitals: 53.5

maximum number of orbitals: 135

![Number of orbitals histogram](num_orbitals_histogram.png)

![Utility estimate per Hamiltonian](num_orbitals_vs_utility.png)

# Solver Summary Statistics

number of unique participating solvers: 8

![Solver scatter plot](solver_num_orbs_vs_runtime_scatter_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

![Solver scatter plot](solver_num_orbs_vs_log_runtime_scatter_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

![Quantum vs Classical scatter plot](quantum_vs_classical_solver_num_orbs_vs_log_runtime_scatter_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

![Solver logFCI scatter plot](log_fci_dim_vs_runtime_all_solvers_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

![Solver logFCI scatter plot, log(runtime)](log_fci_dim_vs_log_runtime_all_solvers_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

## Solver SHCI_opt, 2dde727e-a881-44fa-aabf-bba6248e4baf

solver_uuid:2dde727e-a881-44fa-aabf-bba6248e4baf

solver_short_name:SHCI_opt

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with optimized orbitals followed by SHCI+PT

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: ffb78bb6-afbb-4ae5-9e1a-5960f5298461

creation_timestamp: 2025-01-24T22:30:00.577981+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 78

number_of_problem_instances_solved: 33

number_of_tasks: 230

number_of_tasks_attempted: 219

number_of_tasks_solved: 113

number_of_tasks_solved_within_run_time_limit: 219

number_of_tasks_solved_within_accuracy_threshold: 113

max_run_time_of_attempted_tasks: 57334.2

sum_of_run_time_of_attempted_tasks: 1428870.1239999998

solvability_ratio: 1.0

f1_score: [0.0, 0.9868995633187773]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_2dde727e-a881-44fa-aabf-bba6248e4baf_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](log_fci_dim_vs_runtime_solver_2dde727e-a881-44fa-aabf-bba6248e4baf_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](solver_2dde727e-a881-44fa-aabf-bba6248e4baf_utility_capture_plot.png)

![Solver miniML plot](plot_solver_2dde727e-a881-44fa-aabf-bba6248e4baf.png)

Note: ML surface plot is based on Hamiltonians where a `reference_energy` was provided. (`attempted` may be `True` or `False`.)

![SHAP summary plot](shap_summary_plot_solver_2dde727e-a881-44fa-aabf-bba6248e4baf.png)

## Solver DF_QPE, 5dad4064-cd11-412f-85cb-d722afe3b3de

solver_uuid:5dad4064-cd11-412f-85cb-d722afe3b3de

solver_short_name:DF_QPE

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': 'Double factorized QPE resource estimates based on methodology of arXiv:2406.06335. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.', 'algorithm_parameters': {'overlap_csv': 'overlaps.csv', 'sf_threshold': 1e-12, 'df_threshold': 0.001, 'max_orbitals': 70}}

software_details:[{'software_name': 'pyLIQTR', 'software_version': '1.3.4'}, {'software_name': 'qb-gsee-benchmark', 'software_version': '0.1.0a2.dev193+g879c00d'}, {'software_name': 'Python', 'software_version': '3.10.12 (main, Nov  6 2024, 20:22:13) [GCC 11.4.0]'}, {'software_name': 'qualtran', 'software_version': '0.4.0'}]

quantum_hardware_details:{'quantum_hardware_description': 'Optimistic superconducting hardware model based on that described in https://arxiv.org/abs/2011.03494.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 0.0001, 'cycle_time_microseconds': 1}}

logical_resource_estimate_solution_uuid:fc17e113-d2e0-49ab-955a-6fc08c6eb2f9

logical_resource_estimate_solver_uuid:f2d73e1f-3058-43c4-a634-b6c267c84ff1

performance_metrics_uuid: 8f235a80-da44-468b-a75e-31f49d54acc9

creation_timestamp: 2025-01-24T22:30:00.577981+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 22

number_of_problem_instances_solved: 0

number_of_tasks: 230

number_of_tasks_attempted: 154

number_of_tasks_solved: 0

number_of_tasks_solved_within_run_time_limit: 0

number_of_tasks_solved_within_accuracy_threshold: 154

max_run_time_of_attempted_tasks: 1394068547267.4111

sum_of_run_time_of_attempted_tasks: 15652541022388.93

solvability_ratio: None

f1_score: None

ml_metrics_calculator_version: 1

comment: All labels were either all `True` or all `False` and we cannot create an ML model with only one class.

![Solver success/failure plot](solver_5dad4064-cd11-412f-85cb-d722afe3b3de_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](log_fci_dim_vs_runtime_solver_5dad4064-cd11-412f-85cb-d722afe3b3de_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](solver_5dad4064-cd11-412f-85cb-d722afe3b3de_utility_capture_plot.png)

![Solver miniML plot](plot_solver_5dad4064-cd11-412f-85cb-d722afe3b3de.png)

Note: ML surface plot is based on Hamiltonians where a `reference_energy` was provided. (`attempted` may be `True` or `False`.)

![SHAP summary plot](shap_summary_plot_solver_5dad4064-cd11-412f-85cb-d722afe3b3de.png)

## Solver CISD, 418f060e-496b-4024-8d2d-9b1f8791e76d

solver_uuid:418f060e-496b-4024-8d2d-9b1f8791e76d

solver_short_name:CISD

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:CISD

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: 1e1e849e-14e8-4346-88b2-39f1d77322d6

creation_timestamp: 2025-01-24T22:30:00.577981+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 82

number_of_problem_instances_solved: 9

number_of_tasks: 230

number_of_tasks_attempted: 230

number_of_tasks_solved: 17

number_of_tasks_solved_within_run_time_limit: 230

number_of_tasks_solved_within_accuracy_threshold: 17

max_run_time_of_attempted_tasks: 62.58296537399292

sum_of_run_time_of_attempted_tasks: 2895.8530027866364

solvability_ratio: 0.1674

f1_score: [0.979381443298969, 0.8947368421052632]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_418f060e-496b-4024-8d2d-9b1f8791e76d_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](log_fci_dim_vs_runtime_solver_418f060e-496b-4024-8d2d-9b1f8791e76d_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](solver_418f060e-496b-4024-8d2d-9b1f8791e76d_utility_capture_plot.png)

![Solver miniML plot](plot_solver_418f060e-496b-4024-8d2d-9b1f8791e76d.png)

Note: ML surface plot is based on Hamiltonians where a `reference_energy` was provided. (`attempted` may be `True` or `False`.)

![SHAP summary plot](shap_summary_plot_solver_418f060e-496b-4024-8d2d-9b1f8791e76d.png)

## Solver CCSD(T), c09217e6-d0f7-4b0f-81c4-79210b7ac878

solver_uuid:c09217e6-d0f7-4b0f-81c4-79210b7ac878

solver_short_name:CCSD(T)

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:CCSD(T)

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: 54c9bc45-a6b1-4614-8d8e-b13c3d632b3f

creation_timestamp: 2025-01-24T22:30:00.577981+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 78

number_of_problem_instances_solved: 19

number_of_tasks: 230

number_of_tasks_attempted: 221

number_of_tasks_solved: 64

number_of_tasks_solved_within_run_time_limit: 221

number_of_tasks_solved_within_accuracy_threshold: 64

max_run_time_of_attempted_tasks: 493.4080808162689

sum_of_run_time_of_attempted_tasks: 12968.4871737957

solvability_ratio: 0.9842

f1_score: [0.970873786407767, 0.9767441860465116]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](log_fci_dim_vs_runtime_solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878_utility_capture_plot.png)

![Solver miniML plot](plot_solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878.png)

Note: ML surface plot is based on Hamiltonians where a `reference_energy` was provided. (`attempted` may be `True` or `False`.)

![SHAP summary plot](shap_summary_plot_solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878.png)

## Solver HF, 5f5e617a-19c2-4d82-bebc-b2d6b3dcb012

solver_uuid:5f5e617a-19c2-4d82-bebc-b2d6b3dcb012

solver_short_name:HF

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:Hartree Fock

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: 74960b2f-1d0e-4819-ade1-04b5dfaaa898

creation_timestamp: 2025-01-24T22:30:00.577981+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 82

number_of_problem_instances_solved: 5

number_of_tasks: 230

number_of_tasks_attempted: 230

number_of_tasks_solved: 5

number_of_tasks_solved_within_run_time_limit: 230

number_of_tasks_solved_within_accuracy_threshold: 5

max_run_time_of_attempted_tasks: 20.338801622390747

sum_of_run_time_of_attempted_tasks: 792.8028435707092

solvability_ratio: 0.0

f1_score: [0.995475113122172, 0.9090909090909091]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](log_fci_dim_vs_runtime_solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012_utility_capture_plot.png)

![Solver miniML plot](plot_solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012.png)

Note: ML surface plot is based on Hamiltonians where a `reference_energy` was provided. (`attempted` may be `True` or `False`.)

![SHAP summary plot](shap_summary_plot_solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012.png)

## Solver MP2, b420358b-5def-41e6-8c5d-b9d93b6aecd2

solver_uuid:b420358b-5def-41e6-8c5d-b9d93b6aecd2

solver_short_name:MP2

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:MP2

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: e91675b6-baa9-4828-a407-5b7ff0c778c1

creation_timestamp: 2025-01-24T22:30:00.577981+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 79

number_of_problem_instances_solved: 5

number_of_tasks: 230

number_of_tasks_attempted: 222

number_of_tasks_solved: 5

number_of_tasks_solved_within_run_time_limit: 222

number_of_tasks_solved_within_accuracy_threshold: 5

max_run_time_of_attempted_tasks: 2.230440139770508

sum_of_run_time_of_attempted_tasks: 87.6544258594513

solvability_ratio: 0.0

f1_score: [0.995475113122172, 0.9090909090909091]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](log_fci_dim_vs_runtime_solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2_utility_capture_plot.png)

![Solver miniML plot](plot_solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2.png)

Note: ML surface plot is based on Hamiltonians where a `reference_energy` was provided. (`attempted` may be `True` or `False`.)

![SHAP summary plot](shap_summary_plot_solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2.png)

## Solver CCSD, 0a29e54f-bef9-4d19-bafa-d94b1c4b37aa

solver_uuid:0a29e54f-bef9-4d19-bafa-d94b1c4b37aa

solver_short_name:CCSD

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:CCSD

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: de6eeab5-eb4e-4b40-9d97-9854a8b48260

creation_timestamp: 2025-01-24T22:30:00.577981+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 78

number_of_problem_instances_solved: 10

number_of_tasks: 230

number_of_tasks_attempted: 221

number_of_tasks_solved: 23

number_of_tasks_solved_within_run_time_limit: 221

number_of_tasks_solved_within_accuracy_threshold: 23

max_run_time_of_attempted_tasks: 485.1982181072235

sum_of_run_time_of_attempted_tasks: 12029.76450586319

solvability_ratio: 0.1283

f1_score: [0.9723756906077348, 0.9019607843137255]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](log_fci_dim_vs_runtime_solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa_utility_capture_plot.png)

![Solver miniML plot](plot_solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa.png)

Note: ML surface plot is based on Hamiltonians where a `reference_energy` was provided. (`attempted` may be `True` or `False`.)

![SHAP summary plot](shap_summary_plot_solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa.png)

## Solver DMRG_Niagara_cluster_lowest_energy, 16537433-9f4c-4eae-a65d-787dc3b35b59

solver_uuid:16537433-9f4c-4eae-a65d-787dc3b35b59

solver_short_name:DMRG_Niagara_cluster_lowest_energy

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'Niagara Cluster, Compute Canada', 'cpu_description': '40 Intel "Skylake" cores at 2.4 GHz or 40 Intel "CascadeLake" cores at 2.5 GHz', 'ram_available_gb': '202 GB (188 GiB)', 'clock_speed': '2.4 GHz or 2.5 GHz', 'total_num_cores': 40}

algorithm_details:DMRG with the lowest variational energy obtained so far.

software_details:Block2 v0.5.3rc16 with dmrghandler, commit version d603fdc6409fc194a416aa3a519362d5d91790d9 or later.

performance_metrics_uuid: 4c257743-402c-49c0-be8a-eb24a2c1a63e

creation_timestamp: 2025-01-24T22:30:00.577981+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 82

number_of_problem_instances_solved: 9

number_of_tasks: 230

number_of_tasks_attempted: 230

number_of_tasks_solved: 72

number_of_tasks_solved_within_run_time_limit: 230

number_of_tasks_solved_within_accuracy_threshold: 72

max_run_time_of_attempted_tasks: 80820.729907066

sum_of_run_time_of_attempted_tasks: 2456481.4481055504

solvability_ratio: 0.354

f1_score: [0.9772727272727273, 0.9861111111111112]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_16537433-9f4c-4eae-a65d-787dc3b35b59_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](log_fci_dim_vs_runtime_solver_16537433-9f4c-4eae-a65d-787dc3b35b59_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](solver_16537433-9f4c-4eae-a65d-787dc3b35b59_utility_capture_plot.png)

![Solver miniML plot](plot_solver_16537433-9f4c-4eae-a65d-787dc3b35b59.png)

Note: ML surface plot is based on Hamiltonians where a `reference_energy` was provided. (`attempted` may be `True` or `False`.)

![SHAP summary plot](shap_summary_plot_solver_16537433-9f4c-4eae-a65d-787dc3b35b59.png)

# Non-negative matrix factorization (ML latent space)

![NNMF plot](nnmf_components.png)

Features: ['max_vertex_degree', 'min_vertex_degree', 'mean_vertex_degree', 'std_dev_vertex_degree', 'max_weight', 'min_weight', 'mean_weight', 'std_dev_weight', 'max_edge_order', 'mean_edge_order', 'std_dev_edge_order', 'one_norm', 'log_fci_dim', 'n_elec', 'n_orbs', 'df_gap']

Component 1: [0.         0.02685827 0.         0.         0.97511264 0.0969199
 0.29760092 0.37920344 0.23862642 0.26950715 0.22773165 0.04425233
 0.65545981 0.8390423  0.23877827 0.06293065]

Component 2: [0.3985962  0.35811604 0.39791082 0.39779672 0.20050903 0.
 0.         0.         0.6598437  0.66421914 0.65646106 0.40606965
 0.44313759 0.07508895 0.66011449 0.54976891]

