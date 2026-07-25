# ML-8D UQ solvability estimator + solvability-ratio v2 — HELD

Two-track estimator over **gradeable tasks only**. The design-based
selection-weighted rate is the **ratio of record**; the model-based track
is a calibration-gated estimate. Every model output here is an estimate:
the ML-6 no-validated-predictor rule stands.

## Scope

- gradeable corpus population: 609
- design-track covered subpopulation: 577 (orphaned 32, disclosed never reassigned)
- training labels: 80 retained gradeable panel tasks in 22 canonical families
- variants: 18; LOFO folds: 40
- per-task posterior rows: 12924

## Track 1 — design-based ratio (ratio of record)

| variant | successes/centers | ratio | family-grouped 95% (PRIMARY) | center-level 95% (sensitivity) |
|---|---|---|---|---|
| `DMRG_bond_dimension_1024` | 42/80 | 0.639515 | [0.339224, 0.802493] | [0.372461, 0.826137] |
| `DMRG_bond_dimension_2048` | 42/80 | 0.639515 | [0.339224, 0.802493] | [0.372461, 0.826137] |
| `DMRG_bond_dimension_256` | 28/80 | 0.474870 | [0.190318, 0.637010] | [0.166658, 0.712036] |
| `DMRG_bond_dimension_512` | 38/80 | 0.608319 | [0.335162, 0.766302] | [0.333333, 0.802590] |
| `ipie_uhf_trial` | 25/80 | 0.202773 | [0.095585, 0.416692] | [0.080797, 0.396831] |
| `SHCI_orbopt_var_1e-4_nchunks8` | 38/80 | 0.679376 | [0.441911, 0.831641] | [0.422684, 0.839014] |
| `SHCI_orbopt_var_2e-4_nchunks8` | 38/80 | 0.679376 | [0.441911, 0.831641] | [0.422684, 0.839014] |
| `SHCI_orbopt_var_2e-5_nchunks8` | 37/80 | 0.696707 | [0.473906, 0.844809] | [0.438172, 0.850791] |
| `SHCI_orbopt_var_5e-5_nchunks8` | 39/80 | 0.705373 | [0.483858, 0.855133] | [0.450980, 0.857381] |
| `SHCI_pt_2e-5_nchunks8` | 36/80 | 0.691508 | [0.464200, 0.839236] | [0.426740, 0.845712] |
| `TrimCI_default` | 39/80 | 0.615251 | [0.386358, 0.758549] | [0.323501, 0.800363] |
| `TrimCI_ndet_100000` | 37/80 | 0.613518 | [0.383217, 0.758175] | [0.319242, 0.799779] |
| `TrimCI_ndet_1000000` | 39/80 | 0.616984 | [0.387289, 0.762116] | [0.325924, 0.801505] |
| `TrimCI_ndet_10000000` | 38/80 | 0.613518 | [0.382745, 0.756241] | [0.320982, 0.799049] |
| `TrimCI_ndet_2000000` | 39/80 | 0.637782 | [0.384761, 0.782376] | [0.356644, 0.810975] |
| `TrimCI_ndet_250000` | 37/80 | 0.613518 | [0.383217, 0.758175] | [0.319242, 0.799779] |
| `TrimCI_ndet_500000` | 38/80 | 0.615251 | [0.384847, 0.760276] | [0.324189, 0.801020] |
| `TrimCI_ndet_5000000` | 39/80 | 0.637782 | [0.384761, 0.782376] | [0.356644, 0.810975] |

## Track 2 — calibration gate (the validation gate)

Frozen thresholds: ECE ≤ 0.1 AND the family-grouped 95% calibration-slope interval contains 1.0. Bins: 5 equal-count.

**Variants passing the gate: 3 of 18.**

| variant | ECE | ECE ≤ threshold | slope | slope 95% | contains 1 | gate |
|---|---|---|---|---|---|---|
| `DMRG_bond_dimension_1024` | 0.1508 | false | 3.6382 | [1.5919, 6.4184] | false | **fail** |
| `DMRG_bond_dimension_2048` | 0.1508 | false | 3.6382 | [1.5919, 6.4184] | false | **fail** |
| `DMRG_bond_dimension_256` | 0.0722 | true | 1.9806 | [0.3085, 5.0874] | true | **PASS** |
| `DMRG_bond_dimension_512` | 0.2329 | false | 6.2133 | [3.1989, 11.7500] | false | **fail** |
| `ipie_uhf_trial` | 0.1372 | false | 0.1879 | [-0.8818, 2.0995] | true | **fail** |
| `SHCI_orbopt_var_1e-4_nchunks8` | 0.0964 | true | 2.7290 | [0.4936, 6.1596] | true | **PASS** |
| `SHCI_orbopt_var_2e-4_nchunks8` | 0.0964 | true | 2.7290 | [0.4936, 6.1596] | true | **PASS** |
| `SHCI_orbopt_var_2e-5_nchunks8` | 0.1900 | false | 3.0212 | [0.5750, 6.7523] | true | **fail** |
| `SHCI_orbopt_var_5e-5_nchunks8` | 0.1257 | false | 3.2358 | [0.9183, 6.9436] | true | **fail** |
| `SHCI_pt_2e-5_nchunks8` | 0.2185 | false | 3.5036 | [0.9128, 7.6470] | true | **fail** |
| `TrimCI_default` | 0.1492 | false | 3.4089 | [1.2217, 7.6690] | false | **fail** |
| `TrimCI_ndet_100000` | 0.2727 | false | 6.8196 | [3.3377, 17.2860] | false | **fail** |
| `TrimCI_ndet_1000000` | 0.2229 | false | 5.2569 | [2.4730, 13.4903] | false | **fail** |
| `TrimCI_ndet_10000000` | 0.1856 | false | 3.8078 | [1.4070, 8.8513] | false | **fail** |
| `TrimCI_ndet_2000000` | 0.1740 | false | 3.4471 | [1.1783, 7.8953] | false | **fail** |
| `TrimCI_ndet_250000` | 0.2727 | false | 6.8196 | [3.3377, 17.2860] | false | **fail** |
| `TrimCI_ndet_500000` | 0.2344 | false | 6.3693 | [2.9439, 17.6588] | false | **fail** |
| `TrimCI_ndet_5000000` | 0.1740 | false | 3.4471 | [1.1783, 7.8953] | false | **fail** |

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
| `DMRG_bond_dimension_1024` | 0.639515 | 0.868637 | 0.587472 | 0.562432 | [0.508080, 0.613790] |
| `DMRG_bond_dimension_2048` | 0.639515 | 0.868637 | 0.587472 | 0.562432 | [0.508080, 0.613790] |
| `DMRG_bond_dimension_256` | 0.474870 | 0.348112 | 0.465022 | 0.395939 | [0.344836, 0.449964] |
| `DMRG_bond_dimension_512` | 0.608319 | 0.860427 | 0.580869 | 0.524028 | [0.469977, 0.576083] |
| `ipie_uhf_trial` | 0.202773 | 0.004926 | 0.325451 | 0.329380 | [0.280069, 0.383785] |
| `SHCI_orbopt_var_1e-4_nchunks8` | 0.679376 | 0.929392 | 0.643300 | 0.533833 | [0.479397, 0.586268] |
| `SHCI_orbopt_var_2e-4_nchunks8` | 0.679376 | 0.929392 | 0.643300 | 0.533833 | [0.479397, 0.586268] |
| `SHCI_orbopt_var_2e-5_nchunks8` | 0.696707 | 0.942529 | 0.644575 | 0.513061 | [0.459225, 0.566766] |
| `SHCI_orbopt_var_5e-5_nchunks8` | 0.705373 | 0.950739 | 0.669296 | 0.553965 | [0.500176, 0.605286] |
| `SHCI_pt_2e-5_nchunks8` | 0.691508 | 0.940887 | 0.644031 | 0.505804 | [0.451819, 0.558748] |
| `TrimCI_default` | 0.615251 | 0.637110 | 0.557929 | 0.515147 | [0.460887, 0.567889] |
| `TrimCI_ndet_100000` | 0.613518 | 0.610837 | 0.554198 | 0.506182 | [0.452373, 0.560180] |
| `TrimCI_ndet_1000000` | 0.616984 | 0.633826 | 0.559295 | 0.526452 | [0.472202, 0.578858] |
| `TrimCI_ndet_10000000` | 0.613518 | 0.627258 | 0.555040 | 0.503849 | [0.449853, 0.556545] |
| `TrimCI_ndet_2000000` | 0.637782 | 0.643678 | 0.559741 | 0.513220 | [0.459299, 0.566061] |
| `TrimCI_ndet_250000` | 0.613518 | 0.610837 | 0.554198 | 0.506182 | [0.452373, 0.560180] |
| `TrimCI_ndet_500000` | 0.615251 | 0.633826 | 0.558012 | 0.517486 | [0.463134, 0.570813] |
| `TrimCI_ndet_5000000` | 0.637782 | 0.643678 | 0.559741 | 0.513220 | [0.459299, 0.566061] |

## Kernel PSD diagnostics (disclosed, never silent)

- kernels fitted: 480
- nearest-PSD projections applied: 480
- most negative eigenvalue seen before projection: -1.968e+00
- largest Frobenius correction: 2.148e+00

The block-averaged metric is not guaranteed Euclidean, so the Gram matrix
is not guaranteed positive semidefinite; every correction is recorded
per kernel in `kernel_psd_diagnostics.csv`.

## Fences honoured

- supersedes nothing; the census, ML-8C annex, and `final_v4` are read-only
- no new label, feature, variant, solver run, or reselection
- no family, mask, reason, or provenance column enters any model
- design-based ratio is the ratio of record; no model output displaces it
- internal analysis only: no public or dashboard placement
