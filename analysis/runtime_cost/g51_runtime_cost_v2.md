# G-51 descriptive runtime and cost layer

This artifact reports observed wall time and available node-hour evidence.
It is descriptive, not fairness-adjusted: campaigns used different hardware,
software, concurrency, stopping rules, and solver settings.

| Campaign | Method | Records | Attempted | Timed | Scheduler node-h | Status |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| g31_tranche1_2026-07 | DMRG_Niagara_cluster_lowest_energy | 1 | 1 | 1 |  | unavailable_no_attributable_accounting |
| g31_tranche1_2026-07 | FCI | 55 | 55 | 55 |  | unavailable_no_attributable_accounting |
| g31_tranche1_2026-07 | SHCI_opt | 55 | 55 | 55 |  | unavailable_no_attributable_accounting |
| g31_tranche1_2026-07 | ipie_uhf_trial | 55 | 0 | 0 |  | unavailable_no_attributable_accounting |
| g40_p2_production | MFPROTO-v3 | 566 | 566 | 566 | 31.160556 | scheduler_and_task_attributed |
| g48_pyscf_clean_slate_2026-07_v1 | CCSD | 591 | 459 | 459 | 2.462778 | scheduler_and_task_attributed |
| g48_pyscf_clean_slate_2026-07_v1 | CCSD(T) | 591 | 438 | 438 | 2.255000 | scheduler_and_task_attributed |
| g48_pyscf_clean_slate_2026-07_v1 | CISD | 591 | 458 | 458 | 2.371667 | scheduler_and_task_attributed |
| g48_pyscf_clean_slate_2026-07_v1 | HF | 591 | 541 | 541 | 0.944444 | scheduler_and_task_attributed |
| g48_pyscf_clean_slate_2026-07_v1 | MP2 | 591 | 550 | 550 | 1.212222 | scheduler_and_task_attributed |
| g49_pyscf_stability_resolved_2026-07_v1 | CCSD | 7 | 3 | 3 |  | unavailable_no_attributable_accounting |
| g49_pyscf_stability_resolved_2026-07_v1 | CCSD(T) | 7 | 3 | 3 |  | unavailable_no_attributable_accounting |
| g49_pyscf_stability_resolved_2026-07_v1 | CISD | 7 | 3 | 3 |  | unavailable_no_attributable_accounting |
| g49_pyscf_stability_resolved_2026-07_v1 | HF | 10 | 10 | 10 |  | unavailable_no_attributable_accounting |
| g49_pyscf_stability_resolved_2026-07_v1 | MP2 | 7 | 3 | 3 |  | unavailable_no_attributable_accounting |
| ipie_swing_2026-07 | ipie_uhf_trial | 49 | 49 | 49 |  | unavailable_no_attributable_accounting |
| ipie_swing_envfix_2026-07 | ipie_uhf_trial | 8 | 8 | 8 |  | unavailable_no_attributable_accounting |
| legacy:DMRG_Niagara_cluster_lowest_energy | DMRG_Niagara_cluster_lowest_energy | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:SHCI | SHCI_opt | 226 | 226 | 226 |  | unavailable_no_attributable_accounting |
| legacy:SHCI_sweep | SHCI_pt_1e-4 | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:SHCI_sweep | SHCI_pt_2e-4 | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:SHCI_sweep | SHCI_pt_2e-5 | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:SHCI_sweep | SHCI_pt_5e-5 | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:SHCI_sweep | SHCI_var_1e-4 | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:SHCI_sweep | SHCI_var_2e-4 | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:SHCI_sweep | SHCI_var_2e-5 | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:SHCI_sweep | SHCI_var_5e-5 | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:TrimCI_default | TrimCI_default | 1 | 1 | 1 |  | unavailable_no_attributable_accounting |
| legacy:pyscf_solutions | CCSD | 217 | 217 | 217 |  | unavailable_no_attributable_accounting |
| legacy:pyscf_solutions | CCSD(T) | 217 | 217 | 217 |  | unavailable_no_attributable_accounting |
| legacy:pyscf_solutions | CISD | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:pyscf_solutions | HF | 228 | 228 | 228 |  | unavailable_no_attributable_accounting |
| legacy:pyscf_solutions | MP2 | 220 | 220 | 220 |  | unavailable_no_attributable_accounting |

## Scheduler campaign totals

| Campaign | Components | Jobs | Scheduler node-h |
| --- | ---: | ---: | ---: |
| g40_p2_production | 2 | 16 | 31.191389 |
| g48_pyscf_clean_slate_2026-07_v1 | 5 | 76 | 9.246111 |
| g49_pyscf_stability_resolved_2026-07_v1 | 2 | 13 | 0.957500 |

## Scheduler components

| Campaign | Run generation | Component | Method | Scope | Jobs | Node-h |
| --- | --- | --- | --- | --- | ---: | ---: |
| g48_pyscf_clean_slate_2026-07_v1 | accepted_phase2_pilot_and_phase3_production | successful_method_jobs | CCSD | method | 16 | 2.462778 |
| g48_pyscf_clean_slate_2026-07_v1 | accepted_phase2_pilot_and_phase3_production | successful_method_jobs | CCSD(T) | method | 31 | 2.255000 |
| g48_pyscf_clean_slate_2026-07_v1 | accepted_phase2_pilot_and_phase3_production | successful_method_jobs | CISD | method | 11 | 2.371667 |
| g48_pyscf_clean_slate_2026-07_v1 | accepted_phase2_pilot_and_phase3_production | successful_method_jobs | HF | method | 9 | 0.944444 |
| g48_pyscf_clean_slate_2026-07_v1 | accepted_phase2_pilot_and_phase3_production | successful_method_jobs | MP2 | method | 9 | 1.212222 |
| g49_pyscf_stability_resolved_2026-07_v1 | g49_initial_generation | task_jobs_and_verifiers |  | campaign_shared_across_methods | 8 | 0.811111 |
| g49_pyscf_stability_resolved_2026-07_v1 | g49b_remediation_v1 | task_jobs_and_verifier |  | campaign_shared_across_methods | 5 | 0.146389 |
| g40_p2_production | g40_p2_production_e95e8f6 | extraction_shards | MFPROTO-v3 | method | 15 | 31.160556 |
| g40_p2_production | g40_p2_production_e95e8f6 | afterok_verifier |  | campaign_support | 1 | 0.030833 |

## Interpretation guardrails

- Wall time is the recorded per-task overall or adapter timing; it is not normalized across hardware.
- G48 scheduler node-hours sum archived successful method jobs from the accepted pilot and production arrays; verifier and smoke jobs are excluded.
- G48 family/size rows expose task-attributed full-node hours. Scheduler allocation is reported only at method level because shards mix strata.
- G49 and G49b ran all requested methods inside shared task jobs. Their 0.811111 and 0.146389 node-hour components are preserved at run-generation/campaign scope and are never duplicated across method rows.
- G40 production observations exclude the 25 preseeded pilot states. Its method-level scheduler value covers 15 extraction shards; the 0.030833 node-hour verifier appears only in the campaign total.
- Legacy campaigns retain wall-time summaries, but allocated node-hours are null where attributable scheduler accounting is absent.
- `not_attempted` rows are coverage records and never contribute zero seconds to timing statistics.
- These data do not support solver-efficiency rankings without a separately preregistered normalization study.

The QRE by solved-by-none frontier is intentionally outside G-51.
