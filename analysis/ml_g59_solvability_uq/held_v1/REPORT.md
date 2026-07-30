# ML-8D UQ solvability estimator + solvability-ratio v2 — HELD

Two-track estimator over **gradeable tasks only**. The design-based
selection-weighted rate is the **ratio of record**; the model-based track
is a calibration-gated estimate. Every model output here is an estimate:
the ML-6 no-validated-predictor rule stands.

## Scope

- gradeable corpus population: 609
- design-track covered subpopulation: 609 (orphaned 0, disclosed never reassigned)
- training labels: 96 retained gradeable panel tasks in 23 canonical families
- variants: 18; LOFO folds: 40
- per-task posterior rows: 12924

## Track 1 — design-based ratio (ratio of record)

| variant | successes/centers | ratio | family-grouped 95% (PRIMARY) | center-level 95% (sensitivity) |
|---|---|---|---|---|
| `DMRG_bond_dimension_1024` | 53/96 | 0.620690 | [0.388160, 0.776987] | [0.392603, 0.792852] |
| `DMRG_bond_dimension_2048` | 54/96 | 0.622332 | [0.388725, 0.780576] | [0.395977, 0.793998] |
| `DMRG_bond_dimension_256` | 35/96 | 0.449918 | [0.244146, 0.579895] | [0.200000, 0.670201] |
| `DMRG_bond_dimension_512` | 48/96 | 0.589491 | [0.383942, 0.760171] | [0.356189, 0.770801] |
| `ipie_uhf_trial` | 29/96 | 0.239737 | [0.153351, 0.360981] | [0.107085, 0.427999] |
| `SHCI_orbopt_var_1e-4_nchunks8` | 48/96 | 0.645320 | [0.462236, 0.809260] | [0.436627, 0.802815] |
| `SHCI_orbopt_var_2e-4_nchunks8` | 48/96 | 0.645320 | [0.462236, 0.809260] | [0.436627, 0.802815] |
| `SHCI_orbopt_var_2e-5_nchunks8` | 48/96 | 0.674877 | [0.500845, 0.842216] | [0.472901, 0.817093] |
| `SHCI_orbopt_var_5e-5_nchunks8` | 50/96 | 0.683087 | [0.507983, 0.857154] | [0.483324, 0.825448] |
| `SHCI_pt_2e-5_nchunks8` | 47/96 | 0.669951 | [0.492555, 0.833842] | [0.464878, 0.813802] |
| `TrimCI_default` | 56/96 | 0.665025 | [0.485664, 0.832213] | [0.456331, 0.817510] |
| `TrimCI_ndet_100000` | 53/96 | 0.663383 | [0.486665, 0.832079] | [0.459454, 0.814144] |
| `TrimCI_ndet_1000000` | 57/96 | 0.681445 | [0.501968, 0.861392] | [0.482348, 0.826259] |
| `TrimCI_ndet_10000000` | 55/96 | 0.663383 | [0.481888, 0.830177] | [0.453681, 0.815911] |
| `TrimCI_ndet_2000000` | 57/96 | 0.691297 | [0.502904, 0.860785] | [0.490736, 0.834545] |
| `TrimCI_ndet_250000` | 54/96 | 0.676519 | [0.493542, 0.854683] | [0.472855, 0.822786] |
| `TrimCI_ndet_500000` | 56/96 | 0.679803 | [0.498812, 0.860068] | [0.478042, 0.824538] |
| `TrimCI_ndet_5000000` | 57/96 | 0.691297 | [0.502904, 0.860785] | [0.490736, 0.834545] |

## Track 2 — calibration gate (the validation gate)

Frozen thresholds: ECE ≤ 0.1 AND the family-grouped 95% calibration-slope interval contains 1.0. Bins: 5 equal-count.

**Variants passing the gate: 1 of 18.**

| variant | ECE | ECE ≤ threshold | slope | slope 95% | contains 1 | gate |
|---|---|---|---|---|---|---|
| `DMRG_bond_dimension_1024` | 0.1369 | false | 3.3887 | [1.9222, 6.4910] | false | **fail** |
| `DMRG_bond_dimension_2048` | 0.1224 | false | 2.8986 | [1.5520, 5.2480] | false | **fail** |
| `DMRG_bond_dimension_256` | 0.1553 | false | 3.7100 | [2.2740, 7.0912] | false | **fail** |
| `DMRG_bond_dimension_512` | 0.2121 | false | 5.0880 | [3.3929, 8.9651] | false | **fail** |
| `ipie_uhf_trial` | 0.0757 | true | 0.8261 | [-0.2189, 2.6204] | true | **PASS** |
| `SHCI_orbopt_var_1e-4_nchunks8` | 0.1404 | false | 3.3448 | [1.5634, 6.4565] | false | **fail** |
| `SHCI_orbopt_var_2e-4_nchunks8` | 0.1404 | false | 3.3448 | [1.5634, 6.4565] | false | **fail** |
| `SHCI_orbopt_var_2e-5_nchunks8` | 0.1781 | false | 3.1286 | [1.1320, 6.2642] | false | **fail** |
| `SHCI_orbopt_var_5e-5_nchunks8` | 0.1467 | false | 3.3530 | [1.4036, 6.5703] | false | **fail** |
| `SHCI_pt_2e-5_nchunks8` | 0.1677 | false | 3.5106 | [1.4931, 6.7041] | false | **fail** |
| `TrimCI_default` | 0.1215 | false | 2.2397 | [0.8607, 4.0284] | true | **fail** |
| `TrimCI_ndet_100000` | 0.1863 | false | 4.4795 | [2.5958, 8.9813] | false | **fail** |
| `TrimCI_ndet_1000000` | 0.1754 | false | 3.1912 | [1.9282, 5.4606] | false | **fail** |
| `TrimCI_ndet_10000000` | 0.1506 | false | 2.4095 | [0.9386, 4.3029] | true | **fail** |
| `TrimCI_ndet_2000000` | 0.1325 | false | 2.5210 | [1.0912, 4.5265] | false | **fail** |
| `TrimCI_ndet_250000` | 0.1993 | false | 4.2086 | [2.4394, 8.3350] | false | **fail** |
| `TrimCI_ndet_500000` | 0.1675 | false | 3.5318 | [2.0771, 6.4410] | false | **fail** |
| `TrimCI_ndet_5000000` | 0.1325 | false | 2.5210 | [1.0912, 4.5265] | false | **fail** |

> **STOP-AT TRIGGERED — FLAG FOR PI.** At least one variant passes the
> frozen calibration gate. That is a claim-language decision, not an ML
> agent conclusion: the numbers are reported plainly and no
> interpretation, paper framing, or predictor claim is offered. Matt acks
> claim language; the PI reviews first.

## Ratio comparison — design vs kNN vs GP

The kNN column of record is reported **twice**: as the argmax hard-label
rate (the quantity behind the quoted 0.150) and as the mean predicted
probability of the same predictions. The design-based ratio is a
probability-scale quantity, so both are shown to keep a thresholding
effect distinguishable from probability miscalibration.

| variant | design | kNN hard-label | kNN mean prob | GP | GP 95% credible |
|---|---|---|---|---|---|
| `DMRG_bond_dimension_1024` | 0.620690 | 0.842365 | 0.618450 | 0.584921 | [0.532600, 0.635136] |
| `DMRG_bond_dimension_2048` | 0.622332 | 0.883415 | 0.630913 | 0.595329 | [0.543269, 0.645255] |
| `DMRG_bond_dimension_256` | 0.449918 | 0.527094 | 0.488060 | 0.418604 | [0.368304, 0.473378] |
| `DMRG_bond_dimension_512` | 0.589491 | 0.837438 | 0.613494 | 0.549918 | [0.497231, 0.601440] |
| `ipie_uhf_trial` | 0.239737 | 0.000000 | 0.293280 | 0.311194 | [0.263624, 0.363256] |
| `SHCI_orbopt_var_1e-4_nchunks8` | 0.645320 | 0.888342 | 0.632981 | 0.557327 | [0.504403, 0.609067] |
| `SHCI_orbopt_var_2e-4_nchunks8` | 0.645320 | 0.888342 | 0.632981 | 0.557327 | [0.504403, 0.609067] |
| `SHCI_orbopt_var_2e-5_nchunks8` | 0.674877 | 0.929392 | 0.670661 | 0.555244 | [0.502458, 0.608143] |
| `SHCI_orbopt_var_5e-5_nchunks8` | 0.683087 | 0.939245 | 0.685243 | 0.589034 | [0.536481, 0.638969] |
| `SHCI_pt_2e-5_nchunks8` | 0.669951 | 0.929392 | 0.670125 | 0.549234 | [0.496343, 0.602705] |
| `TrimCI_default` | 0.665025 | 0.939245 | 0.679603 | 0.610438 | [0.558776, 0.658099] |
| `TrimCI_ndet_100000` | 0.663383 | 0.919540 | 0.662521 | 0.600166 | [0.547663, 0.650137] |
| `TrimCI_ndet_1000000` | 0.681445 | 0.947455 | 0.702760 | 0.635569 | [0.584634, 0.682060] |
| `TrimCI_ndet_10000000` | 0.663383 | 0.934319 | 0.678091 | 0.602646 | [0.550808, 0.650618] |
| `TrimCI_ndet_2000000` | 0.691297 | 0.950739 | 0.701948 | 0.623467 | [0.572090, 0.670780] |
| `TrimCI_ndet_250000` | 0.676519 | 0.942529 | 0.698251 | 0.614974 | [0.562905, 0.664136] |
| `TrimCI_ndet_500000` | 0.679803 | 0.945813 | 0.701816 | 0.628313 | [0.576927, 0.675534] |
| `TrimCI_ndet_5000000` | 0.691297 | 0.950739 | 0.701948 | 0.623467 | [0.572090, 0.670780] |

## Kernel PSD diagnostics (disclosed, never silent)

- kernels fitted: 480
- nearest-PSD projections applied: 480
- most negative eigenvalue seen before projection: -2.017e+00
- largest Frobenius correction: 2.259e+00

The block-averaged metric is not guaranteed Euclidean, so the Gram matrix
is not guaranteed positive semidefinite; every correction is recorded
per kernel in `kernel_psd_diagnostics.csv`.

## Fences honoured

- supersedes nothing; the census, ML-8C annex, and `final_v4` are read-only
- no new label, feature, variant, solver run, or reselection
- no family, mask, reason, or provenance column enters any model
- design-based ratio is the ratio of record; no model output displaces it
- internal analysis only: no public or dashboard placement
