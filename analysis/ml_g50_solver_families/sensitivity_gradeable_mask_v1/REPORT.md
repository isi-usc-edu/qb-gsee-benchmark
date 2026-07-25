# ML-8C gradeable-mask sensitivity annex to `final_v4`

Internal sensitivity annex. **Supersedes nothing** — `final_v4` remains
the analysis of record and its bytes are unchanged. Rerun of the accepted
solver-family analysis with the fail-by-construction panel tasks masked,
to test whether the 0/18 negative verdict survives label
decontamination.

## Mask

- panel tasks: 96
- masked (not gradeable for campaign scoring): **16**
- retained denominator: **80**
- labeled cells: 1728 → **1440**
- masked cells removed: 288, of which 0 were successes and 288 were failures

The mask is derived from the ML-8A census, not hand-listed. Masked tasks
and their reasons:

| task_uuid | reason |
|---|---|
| `084acde0-d1c7-4721-aa45-acb4832e0998` | `excluded_reference_grade_no_reference` |
| `1094e868-f84e-403b-9b54-50802b1cdb60` | `excluded_reference_grade_no_reference` |
| `250107ee-1182-5b80-bbf7-6dbc4363c964` | `excluded_test_tier` |
| `34e0f543-0f23-405b-b06f-4be3cd556f9b` | `excluded_source_defect_documented` |
| `3d5186f9-82b3-4de0-9bc1-242d7bdb678a` | `excluded_reference_grade_no_reference` |
| `46eb70f6-9df3-515d-bdf3-d19681e495ce` | `excluded_source_defect_documented` |
| `4fb7e994-8e7a-4acd-86d4-bb52db824cfc` | `excluded_reference_grade_no_reference` |
| `57830810-1133-4c19-9a19-30183dd86a9f` | `excluded_reference_grade_no_reference` |
| `64e051dd-532e-51b3-94e1-9409438d3764` | `excluded_reference_grade_variational_upper_bound` |
| `75c6898e-ac12-5058-85bd-db7408e2bff2` | `excluded_reference_grade_uncontrolled_estimate` |
| `992b9494-5f30-5893-ae1d-1b92f5d9ec18` | `excluded_test_tier` |
| `da5fe92d-18e9-5990-9346-81bc874e25b5` | `excluded_test_tier` |
| `db75bf65-181b-40c2-b978-26453437c2b0` | `excluded_reference_grade_no_reference` |
| `f936469c-1d1e-4295-a006-84a778c1714c` | `excluded_reference_grade_no_reference` |
| `f96de7fe-5c88-4083-8c48-72bc094cccfd` | `excluded_reference_grade_no_reference` |
| `fe55f18e-d86d-50d9-83ae-49ae37799e0a` | `excluded_test_tier` |

## Equivalence guard

Before masking, the run regenerated the parent observation table and
compared it byte-for-byte to the pinned `final_v4` table: **IDENTICAL**.
The mask is therefore the only difference from the parent analysis.

## Gradeable-population reweighting

- gradeable corpus population: 609
- covered by a retained center: **577** (0.947455)
- orphaned (frozen nearest center is masked; disclosed, never reassigned): **32**

Restated population rates estimate the **covered** gradeable
subpopulation, not all
609 gradeable tasks. The parent
`/96` corpus-weighted rates are quoted unchanged from `final_v4`;
neither denominator is presented alone.

## Headline verdict

| counter | `final_v4` | masked |
|---|---|---|
| variants whose with-JW AP beats the size-sector baseline (95% lower bound > 0) | 0/18 | **0/18** |
| variants where adding JW features improves AP (95% lower bound > 0) | 0/18 | **0/18** |

`negative_verdict_survives_decontamination`: **true**

STOP-AT not triggered: no variant's physics-over-size-sector
average-precision paired delta has a 95% lower bound above zero
under the mask.

## Eligibility changes

None: every variant keeps its parent eligibility status under the unchanged floor.

## Per-variant physics-over-size-sector average precision

| variant | labels | successes | AP delta (parent) | 95% lower (parent) | AP delta (masked) | 95% lower (masked) |
|---|---|---|---|---|---|---|
| `DMRG_bond_dimension_1024` | 96→80 | 42→42 | -0.000935 | -0.192138 | -0.153078 | -0.284300 |
| `DMRG_bond_dimension_2048` | 96→80 | 42→42 | -0.000935 | -0.192138 | -0.153078 | -0.284300 |
| `DMRG_bond_dimension_256` | 96→80 | 28→28 | +0.052400 | -0.137498 | -0.144207 | -0.337375 |
| `DMRG_bond_dimension_512` | 96→80 | 38→38 | -0.020478 | -0.206337 | -0.166057 | -0.310366 |
| `ipie_uhf_trial` | 96→80 | 25→25 | +0.057519 | -0.013077 | +0.111618 | -0.002287 |
| `SHCI_orbopt_var_1e-4_nchunks8` | 96→80 | 38→38 | -0.101077 | -0.348527 | -0.094320 | -0.344739 |
| `SHCI_orbopt_var_2e-4_nchunks8` | 96→80 | 38→38 | -0.101077 | -0.348527 | -0.094320 | -0.344739 |
| `SHCI_orbopt_var_2e-5_nchunks8` | 96→80 | 37→37 | -0.159622 | -0.376598 | -0.087137 | -0.346260 |
| `SHCI_orbopt_var_5e-5_nchunks8` | 96→80 | 39→39 | -0.051991 | -0.309099 | -0.032840 | -0.293522 |
| `SHCI_pt_2e-5_nchunks8` | 96→80 | 36→36 | -0.140619 | -0.353179 | -0.080695 | -0.344969 |
| `TrimCI_default` | 96→80 | 39→39 | -0.122398 | -0.358047 | -0.011061 | -0.199590 |
| `TrimCI_ndet_100000` | 96→80 | 37→37 | +0.018538 | -0.112542 | +0.073304 | -0.121110 |
| `TrimCI_ndet_1000000` | 96→80 | 39→39 | +0.039864 | -0.092910 | +0.100813 | -0.097825 |
| `TrimCI_ndet_10000000` | 96→80 | 38→38 | -0.107027 | -0.322275 | -0.003635 | -0.192792 |
| `TrimCI_ndet_2000000` | 96→80 | 39→39 | -0.112011 | -0.354713 | -0.005955 | -0.201281 |
| `TrimCI_ndet_250000` | 96→80 | 37→37 | +0.018538 | -0.112542 | +0.073304 | -0.121110 |
| `TrimCI_ndet_500000` | 96→80 | 38→38 | +0.036899 | -0.093789 | +0.091190 | -0.098264 |
| `TrimCI_ndet_5000000` | 96→80 | 39→39 | -0.112011 | -0.354713 | -0.005955 | -0.201281 |

## Fences honoured

- supersedes nothing; `final_v4` bytes unchanged
- no metric, tolerance, seed, floor, model, or label-policy change
- no reselection, reassignment, or new solver run
- internal annex only: no public or dashboard placement
- canonical family is grouping and reporting only, never a model input
- no validated-predictor claim is made or implied
