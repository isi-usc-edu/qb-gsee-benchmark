# G50 solver-family solvability analysis

This is internal descriptive evidence, not a validated predictor or a public/dashboard release. Canonical Hamiltonian family is used only for held-family-out training exclusion, family-balanced scoring, uncertainty, and reporting; it is never a model input.

## Observed family ladders

| Variant | Labels | Success | Fail | Weighted population rate | ML status |
|---|---:|---:|---:|---:|---|
| DMRG_bond_dimension_256 | 96 | 28 | 68 | 0.398 | eligible |
| DMRG_bond_dimension_512 | 96 | 38 | 58 | 0.508 | eligible |
| DMRG_bond_dimension_1024 | 96 | 42 | 54 | 0.533 | eligible |
| DMRG_bond_dimension_2048 | 96 | 42 | 54 | 0.533 | eligible |
| ipie_uhf_trial | 96 | 25 | 71 | 0.184 | eligible |
| SHCI_orbopt_var_2e-4_nchunks8 | 96 | 38 | 58 | 0.584 | eligible |
| SHCI_orbopt_var_1e-4_nchunks8 | 96 | 38 | 58 | 0.584 | eligible |
| SHCI_orbopt_var_5e-5_nchunks8 | 96 | 39 | 57 | 0.623 | eligible |
| SHCI_orbopt_var_2e-5_nchunks8 | 96 | 37 | 59 | 0.610 | eligible |
| SHCI_pt_2e-5_nchunks8 | 96 | 36 | 60 | 0.606 | eligible |
| TrimCI_ndet_100000 | 96 | 37 | 59 | 0.525 | eligible |
| TrimCI_ndet_250000 | 96 | 37 | 59 | 0.525 | eligible |
| TrimCI_ndet_500000 | 96 | 38 | 58 | 0.526 | eligible |
| TrimCI_ndet_1000000 | 96 | 39 | 57 | 0.528 | eligible |
| TrimCI_ndet_2000000 | 96 | 39 | 57 | 0.545 | eligible |
| TrimCI_ndet_5000000 | 96 | 39 | 57 | 0.545 | eligible |
| TrimCI_ndet_10000000 | 96 | 38 | 58 | 0.525 | eligible |
| TrimCI_default | 96 | 39 | 57 | 0.526 | eligible |

The weighted rate uses the mandatory ML-5 selection weights only for complete 96-task panels. Every TrimCI cap now has a complete bounded-run panel: reached checkpoints are scored, while an unreached cap is an explicit binary failure with no energy.

## Eligible variant performance

Family-balanced average precision is shown for the with-JW physics KNN and the strong size-sector ridge. The last column is physics minus size-sector under identical whole-family bootstrap draws.

| Variant | Physics AP | Size-sector AP | AP improvement |
|---|---:|---:|---:|
| DMRG_bond_dimension_256 | 0.462 [0.273, 0.761] | 0.410 [0.236, 0.746] | 0.052 [-0.137, 0.230] |
| DMRG_bond_dimension_512 | 0.573 [0.362, 0.903] | 0.593 [0.383, 0.916] | -0.020 [-0.206, 0.149] |
| DMRG_bond_dimension_1024 | 0.586 [0.377, 0.904] | 0.587 [0.386, 0.913] | -0.001 [-0.192, 0.170] |
| DMRG_bond_dimension_2048 | 0.586 [0.377, 0.904] | 0.587 [0.386, 0.913] | -0.001 [-0.192, 0.170] |
| ipie_uhf_trial | 0.219 [0.108, 0.428] | 0.161 [0.093, 0.292] | 0.058 [-0.013, 0.176] |
| SHCI_orbopt_var_2e-4_nchunks8 | 0.453 [0.241, 0.802] | 0.554 [0.332, 0.822] | -0.101 [-0.349, 0.185] |
| SHCI_orbopt_var_1e-4_nchunks8 | 0.453 [0.241, 0.802] | 0.554 [0.332, 0.822] | -0.101 [-0.349, 0.185] |
| SHCI_orbopt_var_5e-5_nchunks8 | 0.482 [0.273, 0.834] | 0.534 [0.324, 0.816] | -0.052 [-0.309, 0.255] |
| SHCI_orbopt_var_2e-5_nchunks8 | 0.421 [0.248, 0.720] | 0.580 [0.372, 0.861] | -0.160 [-0.377, 0.080] |
| SHCI_pt_2e-5_nchunks8 | 0.419 [0.248, 0.720] | 0.560 [0.355, 0.846] | -0.141 [-0.353, 0.081] |
| TrimCI_ndet_100000 | 0.657 [0.433, 0.928] | 0.638 [0.423, 0.919] | 0.019 [-0.113, 0.150] |
| TrimCI_ndet_250000 | 0.657 [0.433, 0.928] | 0.638 [0.423, 0.919] | 0.019 [-0.113, 0.150] |
| TrimCI_ndet_500000 | 0.663 [0.441, 0.933] | 0.626 [0.419, 0.913] | 0.037 [-0.094, 0.181] |
| TrimCI_ndet_1000000 | 0.661 [0.441, 0.928] | 0.621 [0.413, 0.915] | 0.040 [-0.093, 0.194] |
| TrimCI_ndet_2000000 | 0.612 [0.398, 0.885] | 0.724 [0.520, 0.927] | -0.112 [-0.355, 0.166] |
| TrimCI_ndet_5000000 | 0.612 [0.398, 0.885] | 0.724 [0.520, 0.927] | -0.112 [-0.355, 0.166] |
| TrimCI_ndet_10000000 | 0.619 [0.401, 0.894] | 0.726 [0.519, 0.928] | -0.107 [-0.322, 0.153] |
| TrimCI_default | 0.606 [0.391, 0.881] | 0.728 [0.519, 0.934] | -0.122 [-0.358, 0.158] |

## Ladder diagnostics

| Ladder | Earlier to later | Joint labels | Newly solved | Lost success |
|---|---|---:|---:|---:|
| g50_dmrg_bond_dimension_v1 | 256 to 512 | 96 | 10 | 0 |
| g50_dmrg_bond_dimension_v1 | 512 to 1024 | 96 | 4 | 0 |
| g50_dmrg_bond_dimension_v1 | 1024 to 2048 | 96 | 0 | 0 |
| g50_shci_orbopt_variational_eps_var_v1 | 0.0002 to 0.0001 | 96 | 0 | 0 |
| g50_shci_orbopt_variational_eps_var_v1 | 0.0001 to 5e-05 | 96 | 2 | 1 |
| g50_shci_orbopt_variational_eps_var_v1 | 5e-05 to 2e-05 | 96 | 1 | 3 |
| g50_trimci_target_determinants_v1 | 100000 to 250000 | 96 | 0 | 0 |
| g50_trimci_target_determinants_v1 | 250000 to 500000 | 96 | 1 | 0 |
| g50_trimci_target_determinants_v1 | 500000 to 1000000 | 96 | 1 | 0 |
| g50_trimci_target_determinants_v1 | 1000000 to 2000000 | 96 | 2 | 2 |
| g50_trimci_target_determinants_v1 | 2000000 to 5000000 | 96 | 0 | 0 |
| g50_trimci_target_determinants_v1 | 5000000 to 10000000 | 96 | 0 | 1 |

`lost_success` is reported rather than repaired: no monotonic postprocessing is applied to observed labels or predictions. TrimCI diagnostics include the complete bounded-run panels and retain metric-indeterminate, binary-fail cells for unreached caps.

## Reproducibility and scope

The normalized table contains 1728 binary labels over 1728 potential cells. 18 of 18 variants pass the frozen model floor, producing 25848 task-keyed predictions across the with/without-JW arms.

The bundle preserves the outcome-blind preflight, the pre-fit size-sector amendment, normalized labels and coverage, model eligibility decisions, predictions, family-bootstrap performance and paired deltas, growth/nestedness tables, schemas, and file hashes. Promotion additionally requires two fresh directories to be recursively byte-identical.
