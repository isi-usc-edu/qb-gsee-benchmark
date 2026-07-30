# G50 solver-family solvability analysis

This is internal descriptive evidence, not a validated predictor or a public/dashboard release. Canonical Hamiltonian family is used only for held-family-out training exclusion, family-balanced scoring, uncertainty, and reporting; it is never a model input.

## Observed family ladders

| Variant | Labels | Success | Fail | Weighted population rate | ML status |
|---|---:|---:|---:|---:|---|
| DMRG_bond_dimension_256 | 96 | 35 | 61 | 0.450 | eligible |
| DMRG_bond_dimension_512 | 96 | 48 | 48 | 0.589 | eligible |
| DMRG_bond_dimension_1024 | 96 | 53 | 43 | 0.621 | eligible |
| DMRG_bond_dimension_2048 | 96 | 54 | 42 | 0.622 | eligible |
| ipie_uhf_trial | 96 | 29 | 67 | 0.240 | eligible |
| SHCI_orbopt_var_2e-4_nchunks8 | 96 | 48 | 48 | 0.645 | eligible |
| SHCI_orbopt_var_1e-4_nchunks8 | 96 | 48 | 48 | 0.645 | eligible |
| SHCI_orbopt_var_5e-5_nchunks8 | 96 | 50 | 46 | 0.683 | eligible |
| SHCI_orbopt_var_2e-5_nchunks8 | 96 | 48 | 48 | 0.675 | eligible |
| SHCI_pt_2e-5_nchunks8 | 96 | 47 | 49 | 0.670 | eligible |
| TrimCI_ndet_100000 | 96 | 53 | 43 | 0.663 | eligible |
| TrimCI_ndet_250000 | 96 | 54 | 42 | 0.677 | eligible |
| TrimCI_ndet_500000 | 96 | 56 | 40 | 0.680 | eligible |
| TrimCI_ndet_1000000 | 96 | 57 | 39 | 0.681 | eligible |
| TrimCI_ndet_2000000 | 96 | 57 | 39 | 0.691 | eligible |
| TrimCI_ndet_5000000 | 96 | 57 | 39 | 0.691 | eligible |
| TrimCI_ndet_10000000 | 96 | 55 | 41 | 0.663 | eligible |
| TrimCI_default | 96 | 56 | 40 | 0.665 | eligible |

The weighted rate uses the mandatory ML-5 selection weights only for complete 96-task panels. Every TrimCI cap now has a complete bounded-run panel: reached checkpoints are scored, while an unreached cap is an explicit binary failure with no energy.

## Eligible variant performance

Family-balanced average precision is shown for the with-JW physics KNN and the strong size-sector ridge. The last column is physics minus size-sector under identical whole-family bootstrap draws.

| Variant | Physics AP | Size-sector AP | AP improvement |
|---|---:|---:|---:|
| DMRG_bond_dimension_256 | 0.576 [0.377, 0.818] | 0.742 [0.497, 0.923] | -0.166 [-0.294, 0.006] |
| DMRG_bond_dimension_512 | 0.801 [0.649, 0.959] | 0.907 [0.815, 0.976] | -0.106 [-0.243, 0.032] |
| DMRG_bond_dimension_1024 | 0.830 [0.678, 0.965] | 0.902 [0.809, 0.969] | -0.072 [-0.202, 0.037] |
| DMRG_bond_dimension_2048 | 0.822 [0.685, 0.947] | 0.895 [0.805, 0.967] | -0.073 [-0.191, 0.028] |
| ipie_uhf_trial | 0.357 [0.200, 0.611] | 0.257 [0.150, 0.472] | 0.100 [-0.027, 0.259] |
| SHCI_orbopt_var_2e-4_nchunks8 | 0.753 [0.528, 0.910] | 0.735 [0.510, 0.944] | 0.018 [-0.232, 0.240] |
| SHCI_orbopt_var_1e-4_nchunks8 | 0.753 [0.528, 0.910] | 0.735 [0.510, 0.944] | 0.018 [-0.232, 0.240] |
| SHCI_orbopt_var_5e-5_nchunks8 | 0.758 [0.539, 0.928] | 0.689 [0.464, 0.939] | 0.069 [-0.229, 0.317] |
| SHCI_orbopt_var_2e-5_nchunks8 | 0.765 [0.563, 0.927] | 0.752 [0.546, 0.950] | 0.013 [-0.272, 0.261] |
| SHCI_pt_2e-5_nchunks8 | 0.768 [0.565, 0.930] | 0.745 [0.535, 0.953] | 0.023 [-0.278, 0.278] |
| TrimCI_ndet_100000 | 0.913 [0.791, 0.985] | 0.950 [0.894, 0.990] | -0.037 [-0.140, 0.031] |
| TrimCI_ndet_250000 | 0.911 [0.789, 0.979] | 0.950 [0.894, 0.990] | -0.040 [-0.152, 0.028] |
| TrimCI_ndet_500000 | 0.912 [0.793, 0.978] | 0.955 [0.902, 0.991] | -0.043 [-0.149, 0.018] |
| TrimCI_ndet_1000000 | 0.915 [0.798, 0.979] | 0.949 [0.890, 0.988] | -0.034 [-0.137, 0.030] |
| TrimCI_ndet_2000000 | 0.891 [0.774, 0.964] | 0.954 [0.902, 0.995] | -0.063 [-0.184, 0.008] |
| TrimCI_ndet_5000000 | 0.891 [0.774, 0.964] | 0.954 [0.902, 0.995] | -0.063 [-0.184, 0.008] |
| TrimCI_ndet_10000000 | 0.892 [0.768, 0.964] | 0.950 [0.896, 0.992] | -0.058 [-0.193, 0.026] |
| TrimCI_default | 0.870 [0.730, 0.961] | 0.949 [0.894, 0.991] | -0.079 [-0.228, 0.020] |

## Ladder diagnostics

| Ladder | Earlier to later | Joint labels | Newly solved | Lost success |
|---|---|---:|---:|---:|
| g50_dmrg_bond_dimension_v1 | 256 to 512 | 96 | 13 | 0 |
| g50_dmrg_bond_dimension_v1 | 512 to 1024 | 96 | 5 | 0 |
| g50_dmrg_bond_dimension_v1 | 1024 to 2048 | 96 | 1 | 0 |
| g50_shci_orbopt_variational_eps_var_v1 | 0.0002 to 0.0001 | 96 | 0 | 0 |
| g50_shci_orbopt_variational_eps_var_v1 | 0.0001 to 5e-05 | 96 | 3 | 1 |
| g50_shci_orbopt_variational_eps_var_v1 | 5e-05 to 2e-05 | 96 | 1 | 3 |
| g50_trimci_target_determinants_v1 | 100000 to 250000 | 96 | 1 | 0 |
| g50_trimci_target_determinants_v1 | 250000 to 500000 | 96 | 2 | 0 |
| g50_trimci_target_determinants_v1 | 500000 to 1000000 | 96 | 1 | 0 |
| g50_trimci_target_determinants_v1 | 1000000 to 2000000 | 96 | 2 | 2 |
| g50_trimci_target_determinants_v1 | 2000000 to 5000000 | 96 | 0 | 0 |
| g50_trimci_target_determinants_v1 | 5000000 to 10000000 | 96 | 0 | 2 |

`lost_success` is reported rather than repaired: no monotonic postprocessing is applied to observed labels or predictions. TrimCI diagnostics include the complete bounded-run panels and retain metric-indeterminate, binary-fail cells for unreached caps.

## Reproducibility and scope

The normalized table contains 1728 binary labels over 1728 potential cells. 18 of 18 variants pass the frozen model floor, producing 25848 task-keyed predictions across the with/without-JW arms.

The bundle preserves the outcome-blind preflight, the pre-fit size-sector amendment, normalized labels and coverage, model eligibility decisions, predictions, family-bootstrap performance and paired deltas, growth/nestedness tables, schemas, and file hashes. Promotion additionally requires two fresh directories to be recursively byte-identical.
