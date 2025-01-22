# GSEE Benchmark Standard Report

Report based on data from 2025-01-21T21:29:50.150187+00:00

[https://github.com/isi-usc-edu/qb-gsee-benchmark](https://github.com/isi-usc-edu/qb-gsee-benchmark)

Input data: `Hamiltonian_features.csv`, last modified Mon Dec 30 16:29:03 2024

Input data: `GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv`, last modified Thu Jan  9 12:11:19 2025

Latest creation time for a `problem_instance.json` file: Tue Jan 21 16:28:56 2025

Latest creation time for a `performance_metrics.json` file: Tue Jan 21 16:31:34 2025

Latest creation time for a `solution.json` file: Thu Jan 16 14:04:59 2025

# Problem Instance Summary Statistics

number of `problem_instances`: 82

`problem_instance.json` with the most tasks: 16 (mo_n2_pincer/8a3787cc-d3d0-42a8-d9a9-7de2aed45208)

number of Hamiltonians (i.e., tasks): 230

minimum number of orbitals: 6

median number of orbitals: 53.5

maximum number of orbitals: 135

![Number of orbitals histogram](num_orbitals_histogram.png)

![Utility estimate per Hamiltonian](num_orbitals_vs_utility.png)

# Solver Summary Statistics

number of unique participating solvers: 9

![Solver scatter plot](solver_num_orbs_vs_runtime_scatter_plot.png)

![Solver scatter plot](solver_num_orbs_vs_log_runtime_scatter_plot.png)

## Solver SHCI_opt, 2dde727e-a881-44fa-aabf-bba6248e4baf

solver_uuid:2dde727e-a881-44fa-aabf-bba6248e4baf

solver_short_name:SHCI_opt

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with optimized orbitals followed by SHCI+PT

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: f4364191-6147-4802-b066-c96d629f9eda

creation_timestamp: 2025-01-21T21:29:50.150187+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 41

number_of_problem_instances_solved: 14

number_of_tasks: 230

number_of_tasks_attempted: 162

number_of_tasks_solved: 60

number_of_tasks_solved_within_run_time_limit: 162

number_of_tasks_solved_within_accuracy_threshold: 60

max_run_time_of_attempted_tasks: 55299.387

sum_of_run_time_of_attempted_tasks: 1138067.4269999997

solvability_ratio: 0.0073

f1_score: [0.9698795180722891, 0.921875]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_2dde727e-a881-44fa-aabf-bba6248e4baf_plot.png)

![Solver utility capture](solver_2dde727e-a881-44fa-aabf-bba6248e4baf_utility_capture_plot.png)

![Solver miniML plot](plot_solver_2dde727e-a881-44fa-aabf-bba6248e4baf.png)

![SHAP summary plot](shap_summary_plot_solver_2dde727e-a881-44fa-aabf-bba6248e4baf.png)

## Solver CCSDT_PLACEHOLDER, fd13c864-baf1-44de-b52d-0e5dd69f647a

solver_uuid:fd13c864-baf1-44de-b52d-0e5dd69f647a

solver_short_name:CCSDT_PLACEHOLDER

compute_hardware_type:classical_computer

classical_hardware_details:{'cpu_description': 'CCSDT_PLACEHOLDER_cpu_description'}

algorithm_details:CCSDT_PLACEHOLDER_algorithm_details

software_details:CCSDT_PLACEHOLDER_software_details

performance_metrics_uuid: 5fd0439b-c20a-4f72-9246-efd06b24f382

creation_timestamp: 2025-01-21T21:29:50.150187+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 4

number_of_problem_instances_solved: 3

number_of_tasks: 230

number_of_tasks_attempted: 53

number_of_tasks_solved: 43

number_of_tasks_solved_within_run_time_limit: 53

number_of_tasks_solved_within_accuracy_threshold: 43

max_run_time_of_attempted_tasks: 3600.0

sum_of_run_time_of_attempted_tasks: 190800.0

solvability_ratio: 0.0

f1_score: [0.9919137466307277, 0.9662921348314607]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_fd13c864-baf1-44de-b52d-0e5dd69f647a_plot.png)

![Solver utility capture](solver_fd13c864-baf1-44de-b52d-0e5dd69f647a_utility_capture_plot.png)

![Solver miniML plot](plot_solver_fd13c864-baf1-44de-b52d-0e5dd69f647a.png)

![SHAP summary plot](shap_summary_plot_solver_fd13c864-baf1-44de-b52d-0e5dd69f647a.png)

## Solver CISD, 418f060e-496b-4024-8d2d-9b1f8791e76d

solver_uuid:418f060e-496b-4024-8d2d-9b1f8791e76d

solver_short_name:CISD

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:CISD

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: 7abfd4be-862e-4d51-8240-e40783d90d05

creation_timestamp: 2025-01-21T21:29:50.150187+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 82

number_of_problem_instances_solved: 9

number_of_tasks: 230

number_of_tasks_attempted: 230

number_of_tasks_solved: 15

number_of_tasks_solved_within_run_time_limit: 230

number_of_tasks_solved_within_accuracy_threshold: 15

max_run_time_of_attempted_tasks: 62.58296537399292

sum_of_run_time_of_attempted_tasks: 2895.8530027866364

solvability_ratio: 0.012

f1_score: [0.9976689976689976, 0.967741935483871]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_418f060e-496b-4024-8d2d-9b1f8791e76d_plot.png)

![Solver utility capture](solver_418f060e-496b-4024-8d2d-9b1f8791e76d_utility_capture_plot.png)

![Solver miniML plot](plot_solver_418f060e-496b-4024-8d2d-9b1f8791e76d.png)

![SHAP summary plot](shap_summary_plot_solver_418f060e-496b-4024-8d2d-9b1f8791e76d.png)

## Solver CCSD(T), c09217e6-d0f7-4b0f-81c4-79210b7ac878

solver_uuid:c09217e6-d0f7-4b0f-81c4-79210b7ac878

solver_short_name:CCSD(T)

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:CCSD(T)

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: 3eb9c362-299a-4266-ba65-03306379cac3

creation_timestamp: 2025-01-21T21:29:50.150187+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 78

number_of_problem_instances_solved: 19

number_of_tasks: 230

number_of_tasks_attempted: 221

number_of_tasks_solved: 54

number_of_tasks_solved_within_run_time_limit: 221

number_of_tasks_solved_within_accuracy_threshold: 54

max_run_time_of_attempted_tasks: 493.4080808162689

sum_of_run_time_of_attempted_tasks: 12968.4871737957

solvability_ratio: 0.0016

f1_score: [0.9100817438692098, 0.6451612903225806]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878_plot.png)

![Solver utility capture](solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878_utility_capture_plot.png)

![Solver miniML plot](plot_solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878.png)

![SHAP summary plot](shap_summary_plot_solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878.png)

## Solver HF, 5f5e617a-19c2-4d82-bebc-b2d6b3dcb012

solver_uuid:5f5e617a-19c2-4d82-bebc-b2d6b3dcb012

solver_short_name:HF

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:Hartree Fock

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: a1db1491-8349-4ed0-8320-20a5ab6d7eba

creation_timestamp: 2025-01-21T21:29:50.150187+00:00

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

f1_score: [0.9955357142857143, 0.8333333333333334]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012_plot.png)

![Solver utility capture](solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012_utility_capture_plot.png)

![Solver miniML plot](plot_solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012.png)

![SHAP summary plot](shap_summary_plot_solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012.png)

## Solver MP2, b420358b-5def-41e6-8c5d-b9d93b6aecd2

solver_uuid:b420358b-5def-41e6-8c5d-b9d93b6aecd2

solver_short_name:MP2

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:MP2

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: 78c8d828-24cd-40ed-b3f4-deef79086b00

creation_timestamp: 2025-01-21T21:29:50.150187+00:00

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

f1_score: [0.9955357142857143, 0.8333333333333334]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2_plot.png)

![Solver utility capture](solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2_utility_capture_plot.png)

![Solver miniML plot](plot_solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2.png)

![SHAP summary plot](shap_summary_plot_solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2.png)

## Solver CCSD, 0a29e54f-bef9-4d19-bafa-d94b1c4b37aa

solver_uuid:0a29e54f-bef9-4d19-bafa-d94b1c4b37aa

solver_short_name:CCSD

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:CCSD

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: d1c3e86c-7b1e-46fb-a590-57d6f2bb301e

creation_timestamp: 2025-01-21T21:29:50.150187+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 78

number_of_problem_instances_solved: 9

number_of_tasks: 230

number_of_tasks_attempted: 221

number_of_tasks_solved: 19

number_of_tasks_solved_within_run_time_limit: 221

number_of_tasks_solved_within_accuracy_threshold: 19

max_run_time_of_attempted_tasks: 485.1982181072235

sum_of_run_time_of_attempted_tasks: 12029.76450586319

solvability_ratio: 0.0125

f1_score: [1.0, 1.0]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa_plot.png)

![Solver utility capture](solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa_utility_capture_plot.png)

![Solver miniML plot](plot_solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa.png)

![SHAP summary plot](shap_summary_plot_solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa.png)

## Solver DF_QPE, 5dad4064-cd11-412f-85cb-d722afe3b3de

solver_uuid:5dad4064-cd11-412f-85cb-d722afe3b3de

solver_short_name:DF_QPE

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': 'Double factorized QPE resource estimates based on methodology of arXiv:2406.06335. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.', 'algorithm_parameters': {'overlap_csv': 'overlaps.csv', 'sf_threshold': 1e-12, 'df_threshold': 0.001, 'max_orbitals': 70}}

software_details:[{'software_name': 'pyLIQTR', 'software_version': '1.2.1'}, {'software_name': 'qb-gsee-benchmark', 'software_version': '0.1.0a2.dev71+g5d9efab.d20241230'}, {'software_name': 'Python', 'software_version': '3.10.12 (main, Nov  6 2024, 20:22:13) [GCC 11.4.0]'}, {'software_name': 'qualtran', 'software_version': '0.2.0'}]

quantum_hardware_details:{'quantum_hardware_description': 'Optimistic superconducting hardware model based on that described in https://arxiv.org/abs/2011.03494.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 0.0001, 'cycle_time_microseconds': 1}}

logical_resource_estimate_solution_uuid:72dea71b-fb03-43f0-8086-eb37605ba3db

logical_resource_estimate_solver_uuid:f2d73e1f-3058-43c4-a634-b6c267c84ff1

performance_metrics_uuid: 23fe59d3-5ca6-478a-9e5c-5d3a6b6bf9fb

creation_timestamp: 2025-01-21T21:29:50.150187+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 24

number_of_problem_instances_solved: 3

number_of_tasks: 230

number_of_tasks_attempted: 163

number_of_tasks_solved: 26

number_of_tasks_solved_within_run_time_limit: 26

number_of_tasks_solved_within_accuracy_threshold: 163

max_run_time_of_attempted_tasks: 233737829.40462503

sum_of_run_time_of_attempted_tasks: 1180589418.3385448

solvability_ratio: 0.0232

f1_score: [0.9950738916256158, 0.9629629629629629]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_5dad4064-cd11-412f-85cb-d722afe3b3de_plot.png)

![Solver utility capture](solver_5dad4064-cd11-412f-85cb-d722afe3b3de_utility_capture_plot.png)

![Solver miniML plot](plot_solver_5dad4064-cd11-412f-85cb-d722afe3b3de.png)

![SHAP summary plot](shap_summary_plot_solver_5dad4064-cd11-412f-85cb-d722afe3b3de.png)

## Solver DMRG_Niagara_cluster_lowest_energy, 16537433-9f4c-4eae-a65d-787dc3b35b59

solver_uuid:16537433-9f4c-4eae-a65d-787dc3b35b59

solver_short_name:DMRG_Niagara_cluster_lowest_energy

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'Niagara Cluster, Compute Canada', 'cpu_description': '40 Intel "Skylake" cores at 2.4 GHz or 40 Intel "CascadeLake" cores at 2.5 GHz', 'ram_available_gb': '202 GB (188 GiB)', 'clock_speed': '2.4 GHz or 2.5 GHz', 'total_num_cores': 40}

algorithm_details:DMRG with the lowest variational energy obtained so far.

software_details:Block2 v0.5.3rc16 with dmrghandler, commit version d603fdc6409fc194a416aa3a519362d5d91790d9 or later.

performance_metrics_uuid: fe0d35f0-a4b1-4fee-ae13-4375bc3b8e54

creation_timestamp: 2025-01-21T21:29:50.150187+00:00

number_of_problem_instances: 82

number_of_problem_instances_attempted: 82

number_of_problem_instances_solved: 8

number_of_tasks: 230

number_of_tasks_attempted: 230

number_of_tasks_solved: 52

number_of_tasks_solved_within_run_time_limit: 230

number_of_tasks_solved_within_accuracy_threshold: 52

max_run_time_of_attempted_tasks: 80820.729907066

sum_of_run_time_of_attempted_tasks: 2456481.4481055504

solvability_ratio: 0.0145

f1_score: [0.9943502824858758, 0.9811320754716981]

ml_metrics_calculator_version: 1

![Solver success/failure plot](solver_16537433-9f4c-4eae-a65d-787dc3b35b59_plot.png)

![Solver utility capture](solver_16537433-9f4c-4eae-a65d-787dc3b35b59_utility_capture_plot.png)

![Solver miniML plot](plot_solver_16537433-9f4c-4eae-a65d-787dc3b35b59.png)

![SHAP summary plot](shap_summary_plot_solver_16537433-9f4c-4eae-a65d-787dc3b35b59.png)

