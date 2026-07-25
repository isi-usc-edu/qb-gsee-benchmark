# ML-8A gradeability census — HELD (pending PI review)

Corpus-wide, outcome-blind census of campaign gradeability over every
task. This is a new analysis layer: it modifies no committed artifact,
promotes nothing, and selects nothing. Not the eligibility substrate of
record until the PI accepts it.

## Totals

- corpus tasks: **718**
- gradeable for campaign scoring: **609**
- not gradeable: **109**
- canonical families: 40
- JW whole-block-null (censused, NOT a gradeability criterion): 3

## Count by reason

| reason | tasks |
|---|---|
| `gradeable` | 609 |
| `excluded_test_tier` | 11 |
| `excluded_source_defect_documented` | 12 |
| `excluded_missing_taxonomy_grade` | 0 |
| `excluded_reference_grade_no_reference` | 75 |
| `excluded_reference_grade_uncontrolled_estimate` | 10 |
| `excluded_reference_grade_variational_upper_bound` | 1 |
| `excluded_missing_reference_energy` | 0 |
| `excluded_missing_or_invalid_threshold` | 0 |

## Count by reference grade

| reference grade | checkable | tasks | gradeable | not gradeable |
|---|---|---|---|---|
| `exact` | true | 415 | 399 | 16 |
| `multiple_nearly_exact` | true | 84 | 84 | 0 |
| `no_reference` | false | 75 | 0 | 75 |
| `one_nearly_exact` | true | 132 | 126 | 6 |
| `uncontrolled_estimate` | false | 10 | 0 | 10 |
| `variational_upper_bound` | false | 2 | 0 | 2 |

## Structural consequences (amendment A1; counts only, no recommendation)

- canonical families with **zero** gradeable tasks: **6** of 40
- canonical families with at least one gradeable task: 34
- canonical families with at least one non-gradeable task: 18

A canonical family with zero gradeable tasks cannot be represented in any gradeable-eligible selection at any k or seed. Which of these families should be dispositioned, and how, is Matt's O43 call; ML-8A offers no recommendation.

| canonical family with zero gradeable tasks | tasks |
|---|---|
| `catalyst_fe_red` | 9 |
| `catalyst_mo2_n2` | 3 |
| `catalyst_vonburg_ru_ix_cas16_fb_68e62o` | 1 |
| `diamond_2x2x2_periodic_solid` | 1 |
| `tight_binding_controls` | 5 |
| `validation_ccpvdz` | 4 |

## Canonical family breakdown

| canonical family | tasks | gradeable | not gradeable |
|---|---|---|---|
| `attractive_hubbard_1d_ed` | 20 | 20 | 0 |
| `benzene_eriksen_fci_challenge` | 1 | 1 | 0 |
| `block2_c2_ccpvdz_scan` | 3 | 3 | 0 |
| `block2_siam_script_exact` | 1 | 1 | 0 |
| `block2_ueg_script_exact` | 1 | 1 | 0 |
| `ca2cuo3_downfolded_extended_hubbard` | 1 | 1 | 0 |
| `catalyst_blue_dimer` | 12 | 3 | 9 |
| `catalyst_fe_mo_co` | 2 | 1 | 1 |
| `catalyst_fe_red` | 9 | 0 | 9 |
| `catalyst_mn_mono` | 8 | 8 | 0 |
| `catalyst_mo2_n2` | 3 | 0 | 3 |
| `catalyst_mo_n2` | 4 | 2 | 2 |
| `catalyst_mo_n2_pincer` | 16 | 7 | 9 |
| `catalyst_p450_cpd1_spin5_goings_dmrg_ladder` | 7 | 5 | 2 |
| `catalyst_ru_macho` | 9 | 7 | 2 |
| `catalyst_ru_mono` | 6 | 5 | 1 |
| `catalyst_vonburg_ru_ix_cas16_fb_68e62o` | 1 | 0 | 1 |
| `diamond_2x2x2_periodic_solid` | 1 | 0 | 1 |
| `gao_distributed_fci` | 127 | 123 | 4 |
| `h2_fragmentation_sto6g` | 25 | 25 | 0 |
| `hubbard_chain_mean_field_orbitals` | 16 | 12 | 4 |
| `hubbard_lieb_wu_1d_site_basis` | 8 | 8 | 0 |
| `hubbard_square_mean_field_orbitals` | 30 | 30 | 0 |
| `ifciqmc_first_row_diatomics` | 15 | 15 | 0 |
| `orbital_representation_pairs` | 4 | 4 | 0 |
| `planted_synthetic_instances` | 11 | 11 | 0 |
| `propane_sto3g_exact_fci` | 1 | 1 | 0 |
| `prototype_small_molecules_pyscf` | 56 | 20 | 36 |
| `prototype_transition_metal_atoms_monoxides` | 44 | 44 | 0 |
| `qsz_hubbard_2d_halffilled` | 48 | 42 | 6 |
| `richardson_gaudin` | 140 | 140 | 0 |
| `simons_hydrogen_chains` | 40 | 30 | 10 |
| `tight_binding_controls` | 5 | 0 | 5 |
| `ueg_n14_planewave` | 12 | 12 | 0 |
| `validation_ccpvdz` | 4 | 0 | 4 |
| `varbench_hubbard_square16_site_basis` | 4 | 4 | 0 |
| `varbench_impurity_sb_imp9` | 1 | 1 | 0 |
| `varbench_tv_chain32_site_basis` | 3 | 3 | 0 |
| `varbench_tv_square16_ed` | 4 | 4 | 0 |
| `w3b_hubbard_1d_doped_ed` | 15 | 15 | 0 |

## Preregistered falsifiable prediction

Restricting the census to the accepted `final_v4` 96-task panel gives **80 gradeable / 16 not gradeable** against the preregistered expectation of 80 / 16: **CONFIRMED**.

Non-gradeable panel tasks and their reasons:

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

## JW block

- corpus-complete model-eligible `jw_encoding` columns: 15 (coverage 715/718)
- partial columns excluded from the null test: ['max_edge_order', 'min_edge_order']
- whole-block-null tasks: ['2cb87d49-8fc6-54d4-ad36-680cc7234ffc', '38105998-616e-50a7-8927-c8c990a9f9fb', '81f65b14-2085-5443-b91b-3d791a55ab00']

## Conservative choices of record

- variational_upper_bound is recorded as not gradeable under the frozen metrics rule and reported as its own reason class for Matt's O43 disposition
- uncontrolled_estimate is recorded as not gradeable under the frozen metrics rule and reported as its own reason class for Matt's O43 disposition
- test-tier exclusion is retained even where the underlying reference grade is exact
- a documented source defect excludes the task regardless of reference grade
- the JW-null flag is censused but excluded from the derived boolean

## Fences honoured

- no solver outcome, metrics bundle, or campaign ledger was read
- no committed artifact was modified; no public or dashboard placement
- no selection, reweighting, or panel revision (that is ML-8B, held)
- canonical family is carried for reporting only, never as a decision input
