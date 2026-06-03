# GSEE Benchmark Standard Report

Report based on data from 2026-05-14T19:00:21.508451+00:00

[https://github.com/isi-usc-edu/qb-gsee-benchmark](https://github.com/isi-usc-edu/qb-gsee-benchmark)

Input data: `Hamiltonian_features.csv`, last modified Thu May 14 14:59:36 2026

Input data: `GSEE-HC_utility_estimates_all_instances_task_uuids_v2.csv`, last modified Thu Feb 26 10:38:50 2026

Latest creation time for a `problem_instance.json` file: Tue Apr  7 08:08:02 2026

Latest creation time for a `solution.json` file: Tue Apr  7 08:08:02 2026

# Problem Instance Summary Statistics

number of `problem_instances`: 67.

`problem_instance.json` with the most tasks: 16 (mo_n2_pincer/8a3787cc-d3d0-42a8-d9a9-7de2aed45208)

number of Hamiltonians (i.e., tasks) we have features calculated for: 184

minimum number of orbitals: 5

median number of orbitals: 50.5

maximum number of orbitals: 135

![Number of orbitals histogram](supporting_artifacts/num_orbitals_histogram.png)

![Utility estimate per Hamiltonian](supporting_artifacts/num_orbitals_vs_utility.png)

# Solver Summary Statistics

number of unique participating solvers: 23

Solver: SHCI_opt/2dde727e-a881-44fa-aabf-bba6248e4baf, ML Solvability Ratio: {'PCA': 0.9028, 'NNMF': 0.9706}, F1 Score: [1. 1.]

Solver: DF_QPE/5dad4064-cd11-412f-85cb-d722afe3b3de, ML Solvability Ratio: {'PCA': 0.0, 'NNMF': 0.0}, F1 Score: [1. 1.]

Solver: THC_BLISS_QPE_1mHa/b8ed03bd-9c3e-4d07-80af-8f77f0e7c2ac, Model could not be calculated.

Solver: DF_QPE/2610d8de-bd3a-469e-9a80-473e8988755f, ML Solvability Ratio: {'PCA': 0.0, 'NNMF': 0.0}, F1 Score: [1. 1.]

Solver: SHCI_pt_1e-4/4ed500f1-0650-41e3-af00-e4d0359394b4, ML Solvability Ratio: {'PCA': 0.8021, 'NNMF': 0.7755}, F1 Score: [0.84210526 0.96808511]

Solver: SHCI_var_1e-4/7e730dfb-57ee-480b-a8a1-4b73f5f07c54, ML Solvability Ratio: {'PCA': 0.3803, 'NNMF': 0.3745}, F1 Score: [0.94230769 0.95081967]

Solver: SHCI_pt_2e-4/ad964781-302e-4728-a26d-39918e0a6cdb, ML Solvability Ratio: {'PCA': 0.8021, 'NNMF': 0.7755}, F1 Score: [0.84210526 0.96808511]

Solver: SHCI_pt_2e-5/c71b90bd-3250-4c0c-b4e7-fc9878f141f6, ML Solvability Ratio: {'PCA': 0.807, 'NNMF': 0.7788}, F1 Score: [0.92857143 0.98989899]

Solver: SHCI_pt_5e-5/d626506c-7aae-4ad6-802a-b29af5f2bb93, ML Solvability Ratio: {'PCA': 0.7036, 'NNMF': 0.466}, F1 Score: [0.90909091 0.98445596]

Solver: SHCI_var_2e-4/0db183e3-a86d-491b-9125-599556e37c7a, ML Solvability Ratio: {'PCA': 0.2838, 'NNMF': 0.1391}, F1 Score: [0.93103448 0.92727273]

Solver: SHCI_var_2e-5/86bfe50c-9342-4d54-bb68-abc8abd95688, ML Solvability Ratio: {'PCA': 0.5218, 'NNMF': 0.3492}, F1 Score: [0.84210526 0.94674556]

Solver: SHCI_var_5e-5/01949b95-c427-4693-9134-01f47f688c09, ML Solvability Ratio: {'PCA': 0.4131, 'NNMF': 0.2482}, F1 Score: [0.86075949 0.92517007]

Solver: THC_QPE_1mHa/18c187af-3e5b-4e6c-87fd-73c26fd48a60, Model could not be calculated.

Solver: CISD/418f060e-496b-4024-8d2d-9b1f8791e76d, ML Solvability Ratio: {'PCA': 0.0217, 'NNMF': 0.1262}, F1 Score: [0.97777778 0.91304348]

Solver: CCSD/0a29e54f-bef9-4d19-bafa-d94b1c4b37aa, ML Solvability Ratio: {'PCA': 0.048, 'NNMF': 0.1418}, F1 Score: [0.98245614 0.94545455]

Solver: HF/5f5e617a-19c2-4d82-bebc-b2d6b3dcb012, ML Solvability Ratio: {'PCA': 0.0, 'NNMF': 0.0}, F1 Score: [0.         0.10084034]

Solver: MP2/b420358b-5def-41e6-8c5d-b9d93b6aecd2, ML Solvability Ratio: {'PCA': 0.0, 'NNMF': 0.0}, F1 Score: [0.         0.10084034]

Solver: CCSD(T)/c09217e6-d0f7-4b0f-81c4-79210b7ac878, ML Solvability Ratio: {'PCA': 0.9196, 'NNMF': 0.8976}, F1 Score: [0.96969697 0.97637795]

Solver: DF_QPE/7c8ef984-4d3a-4468-8900-e0da3bd8b22d, ML Solvability Ratio: {'PCA': 0.0, 'NNMF': 0.0}, F1 Score: [0.92307692 0.11111111]

Solver: DF_QPE/5d768520-b3d0-4292-bbb4-9776fa128107, ML Solvability Ratio: {'PCA': 0.0, 'NNMF': 0.0}, F1 Score: [1. 1.]

Solver: DF_QPE/f6b36bde-be4a-4eee-975b-2c5f7e553f5f, ML Solvability Ratio: {'PCA': 0.0, 'NNMF': 0.0}, F1 Score: [0.98630137 0.57142857]

Solver: DMRG_Niagara_cluster_lowest_energy/16537433-9f4c-4eae-a65d-787dc3b35b59, ML Solvability Ratio: {'PCA': 0.386, 'NNMF': 0.203}, F1 Score: [0.96774194 0.97744361]

Solver: DF_QPE/4b07b89f-c66f-4e72-8c24-df3e4222cb41, ML Solvability Ratio: {'PCA': 0.0, 'NNMF': 0.0}, F1 Score: [0.99547511 0.8       ]

![Solver scatter plot](supporting_artifacts/solver_num_orbs_vs_runtime_scatter_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

![Solver scatter plot](supporting_artifacts/solver_num_orbs_vs_log_runtime_scatter_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

![Quantum vs Classical scatter plot](supporting_artifacts/quantum_vs_classical_solver_num_orbs_vs_log_runtime_scatter_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

![Solver logFCI scatter plot](supporting_artifacts/log_fci_dim_vs_runtime_all_solvers_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

![Solver logFCI scatter plot, log(runtime)](supporting_artifacts/log_fci_dim_vs_log_runtime_all_solvers_plot.png)

NOTE: only `attempted` tasks are plotted on the chart.  Triangle up/down indicates solved/unsolved.

## Solver SHCI_opt, 2dde727e-a881-44fa-aabf-bba6248e4baf

solver_uuid:2dde727e-a881-44fa-aabf-bba6248e4baf

solver_short_name:SHCI_opt

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with optimized orbitals followed by SHCI+PT

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: d719483e-36f0-491e-91c5-e67042c77323

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 64

number_of_problem_instances_solved: 37

number_of_tasks: 184

number_of_tasks_attempted: 180

number_of_tasks_solved: 108

number_of_tasks_solved_within_run_time_limit: 180

number_of_tasks_solved_within_accuracy_threshold: 108

max_run_time_of_attempted_tasks: 57334.2

sum_of_run_time_of_attempted_tasks: 975847.098

solvability_ratio: 0.9028

comments: solvability ratio based on PCA embedding.

f1_score: [1.0, 1.0]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_2dde727e-a881-44fa-aabf-bba6248e4baf_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_2dde727e-a881-44fa-aabf-bba6248e4baf_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_2dde727e-a881-44fa-aabf-bba6248e4baf_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_2dde727e-a881-44fa-aabf-bba6248e4baf.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_2dde727e-a881-44fa-aabf-bba6248e4baf.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_2dde727e-a881-44fa-aabf-bba6248e4baf.png)

## Solver DF_QPE, 5dad4064-cd11-412f-85cb-d722afe3b3de

solver_uuid:5dad4064-cd11-412f-85cb-d722afe3b3de

solver_short_name:DF_QPE

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': 'Double factorized QPE resource estimates based on methodology of arXiv:2406.06335. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.', 'algorithm_parameters': {'overlap_csv': 'overlaps.csv', 'sf_threshold': 1e-12, 'df_threshold': 0.001, 'max_orbitals': 70}}

software_details:[{'software_name': 'pyLIQTR', 'software_version': '1.4.2'}, {'software_name': 'qb-gsee-benchmark', 'software_version': '0.1.0a3.dev107+gc9c6ccda3.d20260302'}, {'software_name': 'Python', 'software_version': '3.12.2 (main, Feb 26 2026, 10:21:15) [GCC 11.4.0]'}, {'software_name': 'qualtran', 'software_version': '0.4.0'}]

quantum_hardware_details:{'quantum_hardware_description': 'Optimistic superconducting hardware model based on that described in https://arxiv.org/abs/2011.03494.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 0.0001, 'cycle_time_microseconds': 1, 'parallelize_shots': False}}

logical_resource_estimate_solution_uuid:0d495e30-978f-4e99-848a-9fe3a8b51de4

logical_resource_estimate_solver_uuid:f2d73e1f-3058-43c4-a634-b6c267c84ff1

performance_metrics_uuid: 13bf70ec-b7de-41fa-87cb-32f2eac4fc8f

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 23

number_of_problem_instances_solved: 2

number_of_tasks: 184

number_of_tasks_attempted: 133

number_of_tasks_solved: 2

number_of_tasks_solved_within_run_time_limit: 2

number_of_tasks_solved_within_accuracy_threshold: 133

max_run_time_of_attempted_tasks: 1394057079996.7158

sum_of_run_time_of_attempted_tasks: 10996408382832.924

solvability_ratio: 0.0

comments: solvability ratio based on PCA embedding.

f1_score: [1.0, 1.0]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_5dad4064-cd11-412f-85cb-d722afe3b3de_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_5dad4064-cd11-412f-85cb-d722afe3b3de_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_5dad4064-cd11-412f-85cb-d722afe3b3de_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_5dad4064-cd11-412f-85cb-d722afe3b3de.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_5dad4064-cd11-412f-85cb-d722afe3b3de.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_5dad4064-cd11-412f-85cb-d722afe3b3de.png)

## Solver THC_BLISS_QPE_1mHa, b8ed03bd-9c3e-4d07-80af-8f77f0e7c2ac

solver_uuid:b8ed03bd-9c3e-4d07-80af-8f77f0e7c2ac

solver_short_name:THC_BLISS_QPE_1mHa

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': '', 'algorithm_parameters': {'overlap_csv': 'overlaps.csv'}, 'description': 'Tensor Hypercontraction + BLock Invariant Symmetry Shift (BLISS) QPE resource estimates for 1mHa accuracy (more stringent than benchmark-requested 1.59 mHa accuracy) based on methodology in arXiv:2406.06335v2, which is a modified form of the method in arXiv: 2501.06165. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and this DMRG runtime is not included in the classical compute costs.'}

software_details:[{'software_name': 'benchq', 'software_version': '0.7.1.dev10+g80b8279.d20250116'}, {'software_name': 'openfermion', 'software_version': '1.6.1'}, {'software_name': 'Python', 'software_version': '3.12.2'}, {'software_name': 'JAX', 'software_version': '0.4.31'}, {'software_name': 'benchq', 'software_version': '0.1.dev153+g3d429cb.d20250508'}]

logical_resource_estimate_solution_uuid:fd9fd934-0256-494b-b973-5a816ce69fe8

quantum_hardware_details:{'quantum_hardware_description': 'Superconducting hardware model based on that described in https://arxiv.org/abs/2011.03494. Used with THC+BLISS.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 0.001, 'cycle_time_microseconds': 1}}

logical_resource_estimate_solver_uuid:12fbca08-3df3-4f3e-b7fd-c535b6b44b1c

performance_metrics_uuid: e1c93c8d-ed85-4db3-ba2e-04a75c03ee6f

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 3

number_of_problem_instances_solved: 0

number_of_tasks: 184

number_of_tasks_attempted: 23

number_of_tasks_solved: 0

number_of_tasks_solved_within_run_time_limit: 0

number_of_tasks_solved_within_accuracy_threshold: 23

max_run_time_of_attempted_tasks: 68780768267.04153

sum_of_run_time_of_attempted_tasks: 145936991321.73734

solvability_ratio: None

f1_score: None

ml_metrics_calculator_version: 1

comment: All labels were either all `True` or all `False` and we cannot create an ML model with only one class.

![Solver success/failure plot](supporting_artifacts/solver_b8ed03bd-9c3e-4d07-80af-8f77f0e7c2ac_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_b8ed03bd-9c3e-4d07-80af-8f77f0e7c2ac_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_b8ed03bd-9c3e-4d07-80af-8f77f0e7c2ac_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_b8ed03bd-9c3e-4d07-80af-8f77f0e7c2ac.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_b8ed03bd-9c3e-4d07-80af-8f77f0e7c2ac.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_b8ed03bd-9c3e-4d07-80af-8f77f0e7c2ac.png)

## Solver DF_QPE, 2610d8de-bd3a-469e-9a80-473e8988755f

solver_uuid:2610d8de-bd3a-469e-9a80-473e8988755f

solver_short_name:DF_QPE

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': 'Double factorized QPE resource estimates based on methodology of arXiv:2406.06335. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.', 'algorithm_parameters': {'overlap_csv': 'overlaps.csv', 'sf_threshold': 1e-12, 'df_threshold': 0.001, 'max_orbitals': 70}}

software_details:[{'software_name': 'pyLIQTR', 'software_version': '1.4.2'}, {'software_name': 'qb-gsee-benchmark', 'software_version': '0.1.0a3.dev107+gc9c6ccda3.d20260302'}, {'software_name': 'Python', 'software_version': '3.12.2 (main, Feb 26 2026, 10:21:15) [GCC 11.4.0]'}, {'software_name': 'qualtran', 'software_version': '0.4.0'}]

quantum_hardware_details:{'quantum_hardware_description': 'Ultra-optimistic hardware model based on the superconducting architecture described in https://arxiv.org/abs/2011.03494.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 0.0001, 'cycle_time_microseconds': 0.1, 'parallelize_shots': False}}

logical_resource_estimate_solution_uuid:c7dddc47-261a-40a9-af26-b53cf209f8e2

logical_resource_estimate_solver_uuid:f2d73e1f-3058-43c4-a634-b6c267c84ff1

performance_metrics_uuid: 514dbccc-e71b-4642-ad9e-29a5702da826

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 23

number_of_problem_instances_solved: 3

number_of_tasks: 184

number_of_tasks_attempted: 133

number_of_tasks_solved: 4

number_of_tasks_solved_within_run_time_limit: 4

number_of_tasks_solved_within_accuracy_threshold: 133

max_run_time_of_attempted_tasks: 139405709800.31985

sum_of_run_time_of_attempted_tasks: 1099640949950.695

solvability_ratio: 0.0

comments: solvability ratio based on PCA embedding.

f1_score: [1.0, 1.0]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_2610d8de-bd3a-469e-9a80-473e8988755f_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_2610d8de-bd3a-469e-9a80-473e8988755f_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_2610d8de-bd3a-469e-9a80-473e8988755f_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_2610d8de-bd3a-469e-9a80-473e8988755f.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_2610d8de-bd3a-469e-9a80-473e8988755f.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_2610d8de-bd3a-469e-9a80-473e8988755f.png)

## Solver SHCI_pt_1e-4, 4ed500f1-0650-41e3-af00-e4d0359394b4

solver_uuid:4ed500f1-0650-41e3-af00-e4d0359394b4

solver_short_name:SHCI_pt_1e-4

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with eps_var 1e-4 + PT

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: 482d9a28-d3c6-401b-b943-d3238172a1c0

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 26

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 95

number_of_tasks_solved_within_run_time_limit: 181

number_of_tasks_solved_within_accuracy_threshold: 95

max_run_time_of_attempted_tasks: 77244.15200000002

sum_of_run_time_of_attempted_tasks: 1096251.301

solvability_ratio: 0.8021

comments: solvability ratio based on PCA embedding.

f1_score: [0.8421052631578947, 0.9680851063829787]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_4ed500f1-0650-41e3-af00-e4d0359394b4_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_4ed500f1-0650-41e3-af00-e4d0359394b4_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_4ed500f1-0650-41e3-af00-e4d0359394b4_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_4ed500f1-0650-41e3-af00-e4d0359394b4.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_4ed500f1-0650-41e3-af00-e4d0359394b4.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_4ed500f1-0650-41e3-af00-e4d0359394b4.png)

## Solver SHCI_var_1e-4, 7e730dfb-57ee-480b-a8a1-4b73f5f07c54

solver_uuid:7e730dfb-57ee-480b-a8a1-4b73f5f07c54

solver_short_name:SHCI_var_1e-4

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with eps_var 1e-4

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: 3cde5923-7c75-4714-9910-9cd9ff961e87

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 17

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 62

number_of_tasks_solved_within_run_time_limit: 181

number_of_tasks_solved_within_accuracy_threshold: 62

max_run_time_of_attempted_tasks: 77244.15200000002

sum_of_run_time_of_attempted_tasks: 1096251.301

solvability_ratio: 0.3803

comments: solvability ratio based on PCA embedding.

f1_score: [0.9423076923076923, 0.9508196721311475]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_7e730dfb-57ee-480b-a8a1-4b73f5f07c54_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_7e730dfb-57ee-480b-a8a1-4b73f5f07c54_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_7e730dfb-57ee-480b-a8a1-4b73f5f07c54_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_7e730dfb-57ee-480b-a8a1-4b73f5f07c54.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_7e730dfb-57ee-480b-a8a1-4b73f5f07c54.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_7e730dfb-57ee-480b-a8a1-4b73f5f07c54.png)

## Solver SHCI_pt_2e-4, ad964781-302e-4728-a26d-39918e0a6cdb

solver_uuid:ad964781-302e-4728-a26d-39918e0a6cdb

solver_short_name:SHCI_pt_2e-4

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with eps_var 2e-4 + PT

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: c1bf28e1-ec27-48a7-a9d2-6be8dcee6a4a

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 26

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 95

number_of_tasks_solved_within_run_time_limit: 181

number_of_tasks_solved_within_accuracy_threshold: 95

max_run_time_of_attempted_tasks: 77244.15200000002

sum_of_run_time_of_attempted_tasks: 1096251.301

solvability_ratio: 0.8021

comments: solvability ratio based on PCA embedding.

f1_score: [0.8421052631578947, 0.9680851063829787]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_ad964781-302e-4728-a26d-39918e0a6cdb_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_ad964781-302e-4728-a26d-39918e0a6cdb_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_ad964781-302e-4728-a26d-39918e0a6cdb_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_ad964781-302e-4728-a26d-39918e0a6cdb.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_ad964781-302e-4728-a26d-39918e0a6cdb.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_ad964781-302e-4728-a26d-39918e0a6cdb.png)

## Solver SHCI_pt_2e-5, c71b90bd-3250-4c0c-b4e7-fc9878f141f6

solver_uuid:c71b90bd-3250-4c0c-b4e7-fc9878f141f6

solver_short_name:SHCI_pt_2e-5

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with eps_var 2e-5 + PT

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: 5e5324f7-2007-4ad8-9d88-a5195bf31dfc

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 30

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 100

number_of_tasks_solved_within_run_time_limit: 181

number_of_tasks_solved_within_accuracy_threshold: 100

max_run_time_of_attempted_tasks: 77244.15200000002

sum_of_run_time_of_attempted_tasks: 1096251.301

solvability_ratio: 0.807

comments: solvability ratio based on PCA embedding.

f1_score: [0.9285714285714286, 0.98989898989899]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_c71b90bd-3250-4c0c-b4e7-fc9878f141f6_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_c71b90bd-3250-4c0c-b4e7-fc9878f141f6_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_c71b90bd-3250-4c0c-b4e7-fc9878f141f6_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_c71b90bd-3250-4c0c-b4e7-fc9878f141f6.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_c71b90bd-3250-4c0c-b4e7-fc9878f141f6.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_c71b90bd-3250-4c0c-b4e7-fc9878f141f6.png)

## Solver SHCI_pt_5e-5, d626506c-7aae-4ad6-802a-b29af5f2bb93

solver_uuid:d626506c-7aae-4ad6-802a-b29af5f2bb93

solver_short_name:SHCI_pt_5e-5

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with eps_var 5e-5 + PT

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: ce4b587b-39d0-46ae-92bf-8f800805f3dd

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 28

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 98

number_of_tasks_solved_within_run_time_limit: 181

number_of_tasks_solved_within_accuracy_threshold: 98

max_run_time_of_attempted_tasks: 77244.15200000002

sum_of_run_time_of_attempted_tasks: 1096251.301

solvability_ratio: 0.7036

comments: solvability ratio based on PCA embedding.

f1_score: [0.9090909090909091, 0.9844559585492227]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_d626506c-7aae-4ad6-802a-b29af5f2bb93_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_d626506c-7aae-4ad6-802a-b29af5f2bb93_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_d626506c-7aae-4ad6-802a-b29af5f2bb93_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_d626506c-7aae-4ad6-802a-b29af5f2bb93.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_d626506c-7aae-4ad6-802a-b29af5f2bb93.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_d626506c-7aae-4ad6-802a-b29af5f2bb93.png)

## Solver SHCI_var_2e-4, 0db183e3-a86d-491b-9125-599556e37c7a

solver_uuid:0db183e3-a86d-491b-9125-599556e37c7a

solver_short_name:SHCI_var_2e-4

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with eps_var 2e-4

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: 1f8cdd4f-5ac2-4cb2-b81a-99b565bd5573

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 17

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 55

number_of_tasks_solved_within_run_time_limit: 181

number_of_tasks_solved_within_accuracy_threshold: 55

max_run_time_of_attempted_tasks: 77244.15200000002

sum_of_run_time_of_attempted_tasks: 1096251.301

solvability_ratio: 0.2838

comments: solvability ratio based on PCA embedding.

f1_score: [0.9310344827586207, 0.9272727272727272]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_0db183e3-a86d-491b-9125-599556e37c7a_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_0db183e3-a86d-491b-9125-599556e37c7a_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_0db183e3-a86d-491b-9125-599556e37c7a_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_0db183e3-a86d-491b-9125-599556e37c7a.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_0db183e3-a86d-491b-9125-599556e37c7a.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_0db183e3-a86d-491b-9125-599556e37c7a.png)

## Solver SHCI_var_2e-5, 86bfe50c-9342-4d54-bb68-abc8abd95688

solver_uuid:86bfe50c-9342-4d54-bb68-abc8abd95688

solver_short_name:SHCI_var_2e-5

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with eps_var 2e-5

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: 564020f6-5a56-4029-854c-d913f091e445

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 22

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 88

number_of_tasks_solved_within_run_time_limit: 181

number_of_tasks_solved_within_accuracy_threshold: 88

max_run_time_of_attempted_tasks: 77244.15200000002

sum_of_run_time_of_attempted_tasks: 1096251.301

solvability_ratio: 0.5218

comments: solvability ratio based on PCA embedding.

f1_score: [0.8421052631578947, 0.9467455621301775]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_86bfe50c-9342-4d54-bb68-abc8abd95688_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_86bfe50c-9342-4d54-bb68-abc8abd95688_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_86bfe50c-9342-4d54-bb68-abc8abd95688_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_86bfe50c-9342-4d54-bb68-abc8abd95688.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_86bfe50c-9342-4d54-bb68-abc8abd95688.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_86bfe50c-9342-4d54-bb68-abc8abd95688.png)

## Solver SHCI_var_5e-5, 01949b95-c427-4693-9134-01f47f688c09

solver_uuid:01949b95-c427-4693-9134-01f47f688c09

solver_short_name:SHCI_var_5e-5

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:SHCI with eps_var 5e-5

software_details:SHCI Arrow Code (https://github.com/QMC-Cornell/shci).

performance_metrics_uuid: ef3344ec-2cb3-4ce5-bb81-8773d324e9f2

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 18

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 75

number_of_tasks_solved_within_run_time_limit: 181

number_of_tasks_solved_within_accuracy_threshold: 75

max_run_time_of_attempted_tasks: 77244.15200000002

sum_of_run_time_of_attempted_tasks: 1096251.301

solvability_ratio: 0.4131

comments: solvability ratio based on PCA embedding.

f1_score: [0.8607594936708861, 0.9251700680272109]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_01949b95-c427-4693-9134-01f47f688c09_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_01949b95-c427-4693-9134-01f47f688c09_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_01949b95-c427-4693-9134-01f47f688c09_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_01949b95-c427-4693-9134-01f47f688c09.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_01949b95-c427-4693-9134-01f47f688c09.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_01949b95-c427-4693-9134-01f47f688c09.png)

## Solver THC_QPE_1mHa, 18c187af-3e5b-4e6c-87fd-73c26fd48a60

solver_uuid:18c187af-3e5b-4e6c-87fd-73c26fd48a60

solver_short_name:THC_QPE_1mHa

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': 'Tensor Hypercontraction QPE resource estimates based on methodology of arXiv:2011.03494. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.', 'algorithm_parameters': {'overlap_csv': 'overlaps.csv'}, 'description': 'Tensor Hypercontraction QPE resource estimates for 1mHa accuracy (more stringent than benchmark-requested 1.59 mHa accuracy) based on methodology of arXiv:2011.03494. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.'}

software_details:[{'software_name': 'benchq', 'software_version': '0.7.1.dev10+g80b8279.d20250116'}, {'software_name': 'openfermion', 'software_version': '1.6.1'}, {'software_name': 'Python', 'software_version': '3.12.2'}, {'software_name': 'JAX', 'software_version': '0.4.31'}, {'software_name': 'benchq', 'software_version': '0.1.dev153+g3d429cb.d20250508'}]

logical_resource_estimate_solution_uuid:f9a5bd95-6968-4078-b115-88e5b7a7ddcb

quantum_hardware_details:{'quantum_hardware_description': 'Superconducting hardware model based on that described in https://arxiv.org/abs/2011.03494. Used with THC.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 0.001, 'cycle_time_microseconds': 1}}

logical_resource_estimate_solver_uuid:d6f49cca-6f10-4de8-bc94-4c6fe4d23296

performance_metrics_uuid: 9a77ed4f-4ccf-4c16-840a-074a348329bf

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 3

number_of_problem_instances_solved: 0

number_of_tasks: 184

number_of_tasks_attempted: 23

number_of_tasks_solved: 0

number_of_tasks_solved_within_run_time_limit: 0

number_of_tasks_solved_within_accuracy_threshold: 23

max_run_time_of_attempted_tasks: 203781742944.55988

sum_of_run_time_of_attempted_tasks: 398497180382.5944

solvability_ratio: None

f1_score: None

ml_metrics_calculator_version: 1

comment: All labels were either all `True` or all `False` and we cannot create an ML model with only one class.

![Solver success/failure plot](supporting_artifacts/solver_18c187af-3e5b-4e6c-87fd-73c26fd48a60_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_18c187af-3e5b-4e6c-87fd-73c26fd48a60_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_18c187af-3e5b-4e6c-87fd-73c26fd48a60_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_18c187af-3e5b-4e6c-87fd-73c26fd48a60.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_18c187af-3e5b-4e6c-87fd-73c26fd48a60.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_18c187af-3e5b-4e6c-87fd-73c26fd48a60.png)

## Solver CISD, 418f060e-496b-4024-8d2d-9b1f8791e76d

solver_uuid:418f060e-496b-4024-8d2d-9b1f8791e76d

solver_short_name:CISD

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:CISD

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: 64abdae4-162e-466f-95af-c76ee1ad5d82

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 13

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 21

number_of_tasks_solved_within_run_time_limit: 182

number_of_tasks_solved_within_accuracy_threshold: 21

max_run_time_of_attempted_tasks: 62.58296537399292

sum_of_run_time_of_attempted_tasks: 2112.998790025711

solvability_ratio: 0.0217

comments: solvability ratio based on PCA embedding.

f1_score: [0.9777777777777777, 0.9130434782608695]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_418f060e-496b-4024-8d2d-9b1f8791e76d_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_418f060e-496b-4024-8d2d-9b1f8791e76d_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_418f060e-496b-4024-8d2d-9b1f8791e76d_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_418f060e-496b-4024-8d2d-9b1f8791e76d.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_418f060e-496b-4024-8d2d-9b1f8791e76d.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_418f060e-496b-4024-8d2d-9b1f8791e76d.png)

## Solver CCSD, 0a29e54f-bef9-4d19-bafa-d94b1c4b37aa

solver_uuid:0a29e54f-bef9-4d19-bafa-d94b1c4b37aa

solver_short_name:CCSD

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:CCSD

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: a34a5668-3bf3-4ad4-a636-829488b2df51

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 63

number_of_problem_instances_solved: 14

number_of_tasks: 184

number_of_tasks_attempted: 174

number_of_tasks_solved: 26

number_of_tasks_solved_within_run_time_limit: 174

number_of_tasks_solved_within_accuracy_threshold: 26

max_run_time_of_attempted_tasks: 460.71552085876465

sum_of_run_time_of_attempted_tasks: 6873.791479110718

solvability_ratio: 0.048

comments: solvability ratio based on PCA embedding.

f1_score: [0.9824561403508771, 0.9454545454545454]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_0a29e54f-bef9-4d19-bafa-d94b1c4b37aa.png)

## Solver HF, 5f5e617a-19c2-4d82-bebc-b2d6b3dcb012

solver_uuid:5f5e617a-19c2-4d82-bebc-b2d6b3dcb012

solver_short_name:HF

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:Hartree Fock

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: 4d81a24d-830a-4051-b929-cae3d97aa7b1

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 6

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 6

number_of_tasks_solved_within_run_time_limit: 182

number_of_tasks_solved_within_accuracy_threshold: 6

max_run_time_of_attempted_tasks: 20.338801622390747

sum_of_run_time_of_attempted_tasks: 686.8769178390503

solvability_ratio: 0.0

comments: solvability ratio based on PCA embedding.

f1_score: [0.0, 0.10084033613445378]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_5f5e617a-19c2-4d82-bebc-b2d6b3dcb012.png)

## Solver MP2, b420358b-5def-41e6-8c5d-b9d93b6aecd2

solver_uuid:b420358b-5def-41e6-8c5d-b9d93b6aecd2

solver_short_name:MP2

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:MP2

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: aa4dcfaf-cd7a-4731-a048-05949cf167b7

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 63

number_of_problem_instances_solved: 6

number_of_tasks: 184

number_of_tasks_attempted: 174

number_of_tasks_solved: 6

number_of_tasks_solved_within_run_time_limit: 174

number_of_tasks_solved_within_accuracy_threshold: 6

max_run_time_of_attempted_tasks: 2.230440139770508

sum_of_run_time_of_attempted_tasks: 71.48596668243408

solvability_ratio: 0.0

comments: solvability ratio based on PCA embedding.

f1_score: [0.0, 0.10084033613445378]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_b420358b-5def-41e6-8c5d-b9d93b6aecd2.png)

## Solver CCSD(T), c09217e6-d0f7-4b0f-81c4-79210b7ac878

solver_uuid:c09217e6-d0f7-4b0f-81c4-79210b7ac878

solver_short_name:CCSD(T)

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'LCRC Improv (per node)', 'cpu_description': '2x AMD EPYC 7713 64C', 'ram_available_gb': '256GB', 'clock_speed': '2 GHz', 'total_num_cores': 128}

algorithm_details:CCSD(T)

software_details:pyscf (https://github.com/pyscf/pyscf).

performance_metrics_uuid: 1ef975d0-66e6-4b4d-85da-2ff98e605b63

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 63

number_of_problem_instances_solved: 23

number_of_tasks: 184

number_of_tasks_attempted: 174

number_of_tasks_solved: 64

number_of_tasks_solved_within_run_time_limit: 174

number_of_tasks_solved_within_accuracy_threshold: 64

max_run_time_of_attempted_tasks: 469.1432478427887

sum_of_run_time_of_attempted_tasks: 7687.804200410843

solvability_ratio: 0.9196

comments: solvability ratio based on PCA embedding.

f1_score: [0.9696969696969697, 0.9763779527559056]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_c09217e6-d0f7-4b0f-81c4-79210b7ac878.png)

## Solver DF_QPE, 7c8ef984-4d3a-4468-8900-e0da3bd8b22d

solver_uuid:7c8ef984-4d3a-4468-8900-e0da3bd8b22d

solver_short_name:DF_QPE

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': 'Double factorized QPE resource estimates based on methodology of arXiv:2406.06335. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.', 'algorithm_parameters': {'overlap': 0.94868329805, 'sf_threshold': 1e-12, 'df_threshold': 0.001, 'max_orbitals': 70}}

software_details:[{'software_name': 'benchq', 'software_version': '0.7.1.dev10+g80b8279.d20250116'}, {'software_name': 'openfermion', 'software_version': '1.6.1'}, {'software_name': 'Python', 'software_version': '3.11.5 (main, Sep 11 2023, 08:31:25) [Clang 14.0.6 ]'}, {'software_name': 'benchq', 'software_version': '0.7.1.dev10+g80b8279.d20250116'}]

quantum_hardware_details:{'quantum_hardware_description': 'Superconducting hardware model based on the optimistic model described in https://arxiv.org/abs/2011.03494.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 0.0001, 'cycle_time_microseconds': 1}}

logical_resource_estimate_solution_uuid:e135679c-e314-4808-9634-252bc376d295

logical_resource_estimate_solver_uuid:f2d73e1f-3058-43c4-a634-b6c267c84ff1

performance_metrics_uuid: 996168f0-ea98-43a5-ab93-f7243ccdd5d7

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 4

number_of_problem_instances_solved: 1

number_of_tasks: 184

number_of_tasks_attempted: 24

number_of_tasks_solved: 1

number_of_tasks_solved_within_run_time_limit: 1

number_of_tasks_solved_within_accuracy_threshold: 24

max_run_time_of_attempted_tasks: 451622221.769206

sum_of_run_time_of_attempted_tasks: 4206142119.554202

solvability_ratio: 0.0

comments: solvability ratio based on PCA embedding., ML model calculated without `GridSearchCV`

f1_score: [0.9230769230769231, 0.1111111111111111]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_7c8ef984-4d3a-4468-8900-e0da3bd8b22d_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_7c8ef984-4d3a-4468-8900-e0da3bd8b22d_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_7c8ef984-4d3a-4468-8900-e0da3bd8b22d_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_7c8ef984-4d3a-4468-8900-e0da3bd8b22d.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_7c8ef984-4d3a-4468-8900-e0da3bd8b22d.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_7c8ef984-4d3a-4468-8900-e0da3bd8b22d.png)

## Solver DF_QPE, 5d768520-b3d0-4292-bbb4-9776fa128107

solver_uuid:5d768520-b3d0-4292-bbb4-9776fa128107

solver_short_name:DF_QPE

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': 'Double factorized QPE resource estimates based on methodology of arXiv:2406.06335. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.', 'algorithm_parameters': {'overlap_csv': 'overlaps.csv', 'sf_threshold': 1e-12, 'df_threshold': 0.001, 'max_orbitals': 70}}

software_details:[{'software_name': 'pyLIQTR', 'software_version': '1.4.2'}, {'software_name': 'qb-gsee-benchmark', 'software_version': '0.1.0a3.dev107+gc9c6ccda3.d20260302'}, {'software_name': 'Python', 'software_version': '3.12.2 (main, Feb 26 2026, 10:21:15) [GCC 11.4.0]'}, {'software_name': 'qualtran', 'software_version': '0.4.0'}]

quantum_hardware_details:{'quantum_hardware_description': 'Superconducting hardware model based on that described in https://arxiv.org/abs/2011.03494 with an extremely optimistic physical error rate.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 1e-06, 'cycle_time_microseconds': 1, 'parallelize_shots': False}}

logical_resource_estimate_solution_uuid:27aa9788-c0c7-4f8e-ba5b-315099c05240

logical_resource_estimate_solver_uuid:f2d73e1f-3058-43c4-a634-b6c267c84ff1

performance_metrics_uuid: 02a33104-045e-405e-93ea-cfb0d6fb5bfb

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 25

number_of_problem_instances_solved: 2

number_of_tasks: 184

number_of_tasks_attempted: 139

number_of_tasks_solved: 2

number_of_tasks_solved_within_run_time_limit: 2

number_of_tasks_solved_within_accuracy_threshold: 139

max_run_time_of_attempted_tasks: 71881480309304.23

sum_of_run_time_of_attempted_tasks: 92452303180814.38

solvability_ratio: 0.0

comments: solvability ratio based on PCA embedding.

f1_score: [1.0, 1.0]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_5d768520-b3d0-4292-bbb4-9776fa128107_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_5d768520-b3d0-4292-bbb4-9776fa128107_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_5d768520-b3d0-4292-bbb4-9776fa128107_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_5d768520-b3d0-4292-bbb4-9776fa128107.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_5d768520-b3d0-4292-bbb4-9776fa128107.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_5d768520-b3d0-4292-bbb4-9776fa128107.png)

## Solver DF_QPE, f6b36bde-be4a-4eee-975b-2c5f7e553f5f

solver_uuid:f6b36bde-be4a-4eee-975b-2c5f7e553f5f

solver_short_name:DF_QPE

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': 'Double factorized QPE resource estimates based on methodology of arXiv:2406.06335. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.', 'algorithm_parameters': {'overlap_csv': 'overlaps.csv', 'sf_threshold': 1e-12, 'df_threshold': 0.001, 'max_orbitals': 70}}

software_details:[{'software_name': 'pyLIQTR', 'software_version': '1.4.2'}, {'software_name': 'qb-gsee-benchmark', 'software_version': '0.1.0a3.dev107+gc9c6ccda3.d20260302'}, {'software_name': 'Python', 'software_version': '3.12.2 (main, Feb 26 2026, 10:21:15) [GCC 11.4.0]'}, {'software_name': 'qualtran', 'software_version': '0.4.0'}]

quantum_hardware_details:{'quantum_hardware_description': 'Ultra-optimistic hardware model based on the superconducting architecture described in https://arxiv.org/abs/2011.03494.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 1e-06, 'cycle_time_microseconds': 0.1, 'parallelize_shots': False}}

logical_resource_estimate_solution_uuid:712bb942-1d58-4bfb-bdee-a7635f0b9cd7

logical_resource_estimate_solver_uuid:f2d73e1f-3058-43c4-a634-b6c267c84ff1

performance_metrics_uuid: 13cf01f0-8705-43a4-b222-557526a62ded

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 25

number_of_problem_instances_solved: 4

number_of_tasks: 184

number_of_tasks_attempted: 139

number_of_tasks_solved: 5

number_of_tasks_solved_within_run_time_limit: 5

number_of_tasks_solved_within_accuracy_threshold: 139

max_run_time_of_attempted_tasks: 7188148034586.839

sum_of_run_time_of_attempted_tasks: 9245230449871.828

solvability_ratio: 0.0

comments: solvability ratio based on PCA embedding.

f1_score: [0.9863013698630136, 0.5714285714285714]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_f6b36bde-be4a-4eee-975b-2c5f7e553f5f_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_f6b36bde-be4a-4eee-975b-2c5f7e553f5f_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_f6b36bde-be4a-4eee-975b-2c5f7e553f5f_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_f6b36bde-be4a-4eee-975b-2c5f7e553f5f.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_f6b36bde-be4a-4eee-975b-2c5f7e553f5f.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_f6b36bde-be4a-4eee-975b-2c5f7e553f5f.png)

## Solver DMRG_Niagara_cluster_lowest_energy, 16537433-9f4c-4eae-a65d-787dc3b35b59

solver_uuid:16537433-9f4c-4eae-a65d-787dc3b35b59

solver_short_name:DMRG_Niagara_cluster_lowest_energy

compute_hardware_type:classical_computer

classical_hardware_details:{'computing_environment_name': 'Niagara Cluster, Compute Canada', 'cpu_description': '40 Intel "Skylake" cores at 2.4 GHz or 40 Intel "CascadeLake" cores at 2.5 GHz', 'ram_available_gb': '202 GB (188 GiB)', 'clock_speed': '2.4 GHz or 2.5 GHz', 'total_num_cores': 40}

algorithm_details:DMRG with the lowest variational energy obtained so far.

software_details:Block2 v0.5.3rc16 with dmrghandler, commit version d603fdc6409fc194a416aa3a519362d5d91790d9 or later.

performance_metrics_uuid: 9ba76779-7ad2-4901-8dce-3c7cd6a13753

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 66

number_of_problem_instances_solved: 13

number_of_tasks: 184

number_of_tasks_attempted: 182

number_of_tasks_solved: 67

number_of_tasks_solved_within_run_time_limit: 182

number_of_tasks_solved_within_accuracy_threshold: 67

max_run_time_of_attempted_tasks: 80820.729907066

sum_of_run_time_of_attempted_tasks: 1826529.25386094

solvability_ratio: 0.386

comments: solvability ratio based on PCA embedding.

f1_score: [0.967741935483871, 0.9774436090225563]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_16537433-9f4c-4eae-a65d-787dc3b35b59_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_16537433-9f4c-4eae-a65d-787dc3b35b59_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_16537433-9f4c-4eae-a65d-787dc3b35b59_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_16537433-9f4c-4eae-a65d-787dc3b35b59.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_16537433-9f4c-4eae-a65d-787dc3b35b59.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_16537433-9f4c-4eae-a65d-787dc3b35b59.png)

## Solver DF_QPE, 4b07b89f-c66f-4e72-8c24-df3e4222cb41

solver_uuid:4b07b89f-c66f-4e72-8c24-df3e4222cb41

solver_short_name:DF_QPE

compute_hardware_type:quantum_computer

algorithm_details:{'algorithm_description': 'Double factorized QPE resource estimates based on methodology of arXiv:2406.06335. Note that the truncation error is not included in the error bounds and that the SCF compute time is not included in the preprocessing time. Ground-state overlap is taken to be that estimated for the dominant CSF as estimated by DMRG and that this DMRG runtime is not included in the classical compute costs.', 'algorithm_parameters': {'overlap_csv': 'overlaps.csv', 'sf_threshold': 1e-12, 'df_threshold': 0.001, 'max_orbitals': 70}}

software_details:[{'software_name': 'pyLIQTR', 'software_version': '1.4.2'}, {'software_name': 'qb-gsee-benchmark', 'software_version': '0.1.0a3.dev107+gc9c6ccda3.d20260302'}, {'software_name': 'Python', 'software_version': '3.12.2 (main, Feb 26 2026, 10:21:15) [GCC 11.4.0]'}, {'software_name': 'qualtran', 'software_version': '0.4.0'}]

quantum_hardware_details:{'quantum_hardware_description': 'Optimistic superconducting hardware model based on that described in https://arxiv.org/abs/2011.03494. Assumes that enough QPUs are available to run all shots in parallel.', 'quantum_hardware_parameters': {'num_factories': 4, 'physical_error_rate': 0.0001, 'cycle_time_microseconds': 1, 'parallelize_shots': True}}

logical_resource_estimate_solution_uuid:612747d5-61ee-40cd-b440-0ad59c064c04

logical_resource_estimate_solver_uuid:f2d73e1f-3058-43c4-a634-b6c267c84ff1

performance_metrics_uuid: 9c99f40e-d05a-4a88-ad36-8044dffc059c

creation_timestamp: 2026-05-14T19:00:21.508451+00:00

number_of_problem_instances: 67

number_of_problem_instances_attempted: 23

number_of_problem_instances_solved: 3

number_of_tasks: 184

number_of_tasks_attempted: 133

number_of_tasks_solved: 3

number_of_tasks_solved_within_run_time_limit: 3

number_of_tasks_solved_within_accuracy_threshold: 133

max_run_time_of_attempted_tasks: 27517246880.125843

sum_of_run_time_of_attempted_tasks: 423832831791.01337

solvability_ratio: 0.0

comments: solvability ratio based on PCA embedding.

f1_score: [0.995475113122172, 0.8]

ml_metrics_calculator_version: 1

![Solver success/failure plot](supporting_artifacts/solver_4b07b89f-c66f-4e72-8c24-df3e4222cb41_plot.png)

Note: plot only contains `attempted` tasks.

![Solver success/failure logFCI plot](supporting_artifacts/log_fci_dim_vs_runtime_solver_4b07b89f-c66f-4e72-8c24-df3e4222cb41_plot.png)

Note: plot only contains `attempted` tasks.

![Solver utility capture](supporting_artifacts/solver_4b07b89f-c66f-4e72-8c24-df3e4222cb41_utility_capture_plot.png)

![Solver PCA plot](supporting_artifacts/PCA_embedding_plot_solver_4b07b89f-c66f-4e72-8c24-df3e4222cb41.png)

![Solver NNMF plot](supporting_artifacts/NNMF_embedding_plot_solver_4b07b89f-c66f-4e72-8c24-df3e4222cb41.png)

Note: `attempted` may be `True` or `False`.  Tasks with a `reference_energy` can be labeled as solved or failed-to-solve. A task with a `reference_energy` that was NOT `attempted` is labeled as a failed-to-solve.  White stars indicate Hamiltonians for which we do not have a `reference_energy`.

![SHAP summary plot](supporting_artifacts/shap_summary_plot_solver_4b07b89f-c66f-4e72-8c24-df3e4222cb41.png)

# ML Feature Analysis

![NNMF components plot](supporting_artifacts/nnmf_components.png)

Features: ['max_vertex_degree', 'min_vertex_degree', 'mean_vertex_degree', 'std_dev_vertex_degree', 'max_weight', 'min_weight', 'mean_weight', 'std_dev_weight', 'max_edge_order', 'mean_edge_order', 'std_dev_edge_order', 'one_norm', 'log_fci_dim', 'n_elec', 'n_orbs', 'df_gap']

NNMF Component 1: [0.03745208 0.21516493 0.04107935 0.02808182 0.33905073 0.00185411
 0.01484    0.08651885 0.55613848 0.58830985 0.5442858  0.
 1.12818961 1.01905998 0.5323174  0.115369  ]

NNMF Component 2: [0.42590339 0.35405    0.43390494 0.40922594 0.34180125 0.
 0.00081299 0.02198064 0.6037736  0.60302563 0.59960665 0.45485798
 0.34001469 0.         0.60246848 0.45272373]

![PCA components plot](supporting_artifacts/pca_components.png)

Features: ['max_vertex_degree', 'min_vertex_degree', 'mean_vertex_degree', 'std_dev_vertex_degree', 'max_weight', 'min_weight', 'mean_weight', 'std_dev_weight', 'max_edge_order', 'mean_edge_order', 'std_dev_edge_order', 'one_norm', 'log_fci_dim', 'n_elec', 'n_orbs', 'df_gap']

PCA Component 1: [ 0.30636115  0.26305785  0.31222235  0.29416036  0.13887147 -0.02010789
 -0.03188961 -0.04146377  0.34053294  0.33354463  0.34055038  0.29044829
  0.20123208  0.00217411  0.34536166  0.20780103]

PCA Component 2: [ 0.01874822  0.14481938  0.02091595  0.01334236 -0.39580411 -0.03719602
 -0.07152145 -0.19349572  0.00971009  0.01341835  0.01015107 -0.18947978
  0.48160168  0.63411357  0.00901645 -0.32719802]

![solver similarity: PCA space of area](supporting_artifacts/solver_similarity_in_PCA_space_of_area_summary.png)

![solver similarity: PCA space of SHAP](supporting_artifacts/solver_similarity_in_PCA_space_of_shap_summary.png)

![solver similarity: matrix/area](supporting_artifacts/solver_similarity_matrix_area_summary.png)

![solver similarity: matrix/SHAP values](supporting_artifacts/solver_similarity_matrix_shap_summary.png)

![Hamiltonian features correlation matrix](supporting_artifacts/hamiltonian_features_correlation_matrix_plot.png)

![Histogram of Hamiltonian features: max_vertex_degree](supporting_artifacts/hamiltonian_feature_histogram_max_vertex_degree.png)

![Histogram of Hamiltonian features: min_vertex_degree](supporting_artifacts/hamiltonian_feature_histogram_min_vertex_degree.png)

![Histogram of Hamiltonian features: mean_vertex_degree](supporting_artifacts/hamiltonian_feature_histogram_mean_vertex_degree.png)

![Histogram of Hamiltonian features: std_dev_vertex_degree](supporting_artifacts/hamiltonian_feature_histogram_std_dev_vertex_degree.png)

![Histogram of Hamiltonian features: max_weight](supporting_artifacts/hamiltonian_feature_histogram_max_weight.png)

![Histogram of Hamiltonian features: min_weight](supporting_artifacts/hamiltonian_feature_histogram_min_weight.png)

![Histogram of Hamiltonian features: mean_weight](supporting_artifacts/hamiltonian_feature_histogram_mean_weight.png)

![Histogram of Hamiltonian features: std_dev_weight](supporting_artifacts/hamiltonian_feature_histogram_std_dev_weight.png)

![Histogram of Hamiltonian features: max_edge_order](supporting_artifacts/hamiltonian_feature_histogram_max_edge_order.png)

![Histogram of Hamiltonian features: mean_edge_order](supporting_artifacts/hamiltonian_feature_histogram_mean_edge_order.png)

![Histogram of Hamiltonian features: std_dev_edge_order](supporting_artifacts/hamiltonian_feature_histogram_std_dev_edge_order.png)

![Histogram of Hamiltonian features: one_norm](supporting_artifacts/hamiltonian_feature_histogram_one_norm.png)

![Histogram of Hamiltonian features: log_fci_dim](supporting_artifacts/hamiltonian_feature_histogram_log_fci_dim.png)

![Histogram of Hamiltonian features: n_elec](supporting_artifacts/hamiltonian_feature_histogram_n_elec.png)

![Histogram of Hamiltonian features: n_orbs](supporting_artifacts/hamiltonian_feature_histogram_n_orbs.png)

![Histogram of Hamiltonian features: df_gap](supporting_artifacts/hamiltonian_feature_histogram_df_gap.png)

