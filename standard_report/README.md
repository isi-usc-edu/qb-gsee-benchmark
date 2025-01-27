# GSEE Benchmark Standard Report

Report based on data from 2025-01-27T15:13:49.214554+00:00

[https://github.com/isi-usc-edu/qb-gsee-benchmark](https://github.com/isi-usc-edu/qb-gsee-benchmark)

Input data: `Hamiltonian_features.csv`, last modified Mon Jan 27 08:48:37 2025

Input data: `GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv`, last modified Thu Jan  9 12:11:19 2025

Latest creation time for a `problem_instance.json` file: Fri Jan 24 15:12:37 2025

Latest creation time for a `solution.json` file: Fri Jan 24 17:42:26 2025

# Problem Instance Summary Statistics

number of `problem_instances`: 84.

`problem_instance.json` with the most tasks: 30 (hubbard_square/614c4444-a31a-4348-b24d-01040208651c)

number of Hamiltonians (i.e., tasks) we have features calculated for: 276

minimum number of orbitals: 6

median number of orbitals: 42.0

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

performance_metrics_uuid: cf1a40bd-52ec-4d9c-b0a8-3490ece15cf3

creation_timestamp: 2025-01-27T15:13:49.214554+00:00

number_of_problem_instances: 84

number_of_problem_instances_attempted: 80

number_of_problem_instances_solved: 33

number_of_tasks: 276

number_of_tasks_attempted: 265

number_of_tasks_solved: 153

number_of_tasks_solved_within_run_time_limit: 265

number_of_tasks_solved_within_accuracy_threshold: 153

max_run_time_of_attempted_tasks: 57334.2

sum_of_run_time_of_attempted_tasks: 1553340.6179999998

solvability_ratio: 1.0

f1_score: [0.8333333333333334, 0.993421052631579]

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

performance_metrics_uuid: 90a16327-fbf4-4b46-8260-c1d9b7eb00ab

creation_timestamp: 2025-01-27T15:13:49.214554+00:00

number_of_problem_instances: 84

number_of_problem_instances_attempted: 22

number_of_problem_instances_solved: 0

number_of_tasks: 276

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

performance_metrics_uuid: 1b52f6c5-8dc7-46de-be21-a37589f2f250

creation_timestamp: 2025-01-27T15:13:49.214554+00:00

number_of_problem_instances: 84

number_of_problem_instances_attempted: 84

number_of_problem_instances_solved: 9

number_of_tasks: 276

number_of_tasks_attempted: 276

number_of_tasks_solved: 17

number_of_tasks_solved_within_run_time_limit: 276

number_of_tasks_solved_within_accuracy_threshold: 17

max_run_time_of_attempted_tasks: 62.58296537399292

sum_of_run_time_of_attempted_tasks: 2929.870177745819

solvability_ratio: 0.2773

f1_score: [0.9819494584837545, 0.8717948717948718]

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

performance_metrics_uuid: 0c28995e-47ad-4391-b719-256428dcf6cb

creation_timestamp: 2025-01-27T15:13:49.214554+00:00

number_of_problem_instances: 84

number_of_problem_instances_attempted: 79

number_of_problem_instances_solved: 19

number_of_tasks: 276

number_of_tasks_attempted: 264

number_of_tasks_solved: 71

number_of_tasks_solved_within_run_time_limit: 264

number_of_tasks_solved_within_accuracy_threshold: 71

max_run_time_of_attempted_tasks: 493.4080808162689

sum_of_run_time_of_attempted_tasks: 13199.317583084106

solvability_ratio: 0.8567

f1_score: [0.8795180722891566, 0.8666666666666667]

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

performance_metrics_uuid: 30aa466b-ad2c-43b5-abbc-7d0a0f64f90c

creation_timestamp: 2025-01-27T15:13:49.214554+00:00

number_of_problem_instances: 84

number_of_problem_instances_attempted: 84

number_of_problem_instances_solved: 5

number_of_tasks: 276

number_of_tasks_attempted: 276

number_of_tasks_solved: 5

number_of_tasks_solved_within_run_time_limit: 276

number_of_tasks_solved_within_accuracy_threshold: 5

max_run_time_of_attempted_tasks: 20.338801622390747

sum_of_run_time_of_attempted_tasks: 906.4860525131226

solvability_ratio: 0.0

f1_score: [0.9867549668874173, 0.7142857142857143]

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

performance_metrics_uuid: 10729930-3edd-42fd-9a0c-f351dcbaed1a

creation_timestamp: 2025-01-27T15:13:49.214554+00:00

number_of_problem_instances: 84

number_of_problem_instances_attempted: 81

number_of_problem_instances_solved: 5

number_of_tasks: 276

number_of_tasks_attempted: 268

number_of_tasks_solved: 5

number_of_tasks_solved_within_run_time_limit: 268

number_of_tasks_solved_within_accuracy_threshold: 5

max_run_time_of_attempted_tasks: 2.230440139770508

sum_of_run_time_of_attempted_tasks: 94.7442626953125

solvability_ratio: 0.0

f1_score: [0.9867549668874173, 0.7142857142857143]

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

performance_metrics_uuid: 83c1a56e-1306-427a-bc6e-3f6e6fc9d127

creation_timestamp: 2025-01-27T15:13:49.214554+00:00

number_of_problem_instances: 84

number_of_problem_instances_attempted: 79

number_of_problem_instances_solved: 10

number_of_tasks: 276

number_of_tasks_attempted: 264

number_of_tasks_solved: 24

number_of_tasks_solved_within_run_time_limit: 264

number_of_tasks_solved_within_accuracy_threshold: 24

max_run_time_of_attempted_tasks: 485.1982181072235

sum_of_run_time_of_attempted_tasks: 12252.72845697403

solvability_ratio: 0.0154

f1_score: [0.9777777777777777, 0.8695652173913043]

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

performance_metrics_uuid: d0f46196-4d22-4bb7-b003-9b2ed6f4b350

creation_timestamp: 2025-01-27T15:13:49.214554+00:00

number_of_problem_instances: 84

number_of_problem_instances_attempted: 84

number_of_problem_instances_solved: 9

number_of_tasks: 276

number_of_tasks_attempted: 276

number_of_tasks_solved: 112

number_of_tasks_solved_within_run_time_limit: 276

number_of_tasks_solved_within_accuracy_threshold: 112

max_run_time_of_attempted_tasks: 80820.729907066

sum_of_run_time_of_attempted_tasks: 2471726.9051446947

solvability_ratio: 0.3405

f1_score: [0.9662921348314607, 0.986784140969163]

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

Component 1: [0.36604788 0.3465517  0.3656555  0.36466294 0.49391307 0.
 0.         0.07560829 0.70083452 0.73297542 0.69367903 0.39707278
 0.62804024 0.33874397 0.7006798  0.57585866]

Component 2: [0.         0.         0.         0.         0.06352889 1.09340886
 0.56300493 0.44159773 0.05242832 0.01821226 0.07191467 0.
 0.12812831 0.07525071 0.07071245 0.        ]

