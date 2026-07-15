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
| g48_pyscf_clean_slate_2026-07_v1 | CCSD | 591 | 459 | 459 | 2.462778 | scheduler_and_task_attributed |
| g48_pyscf_clean_slate_2026-07_v1 | CCSD(T) | 591 | 438 | 438 | 2.255000 | scheduler_and_task_attributed |
| g48_pyscf_clean_slate_2026-07_v1 | CISD | 591 | 458 | 458 | 2.371667 | scheduler_and_task_attributed |
| g48_pyscf_clean_slate_2026-07_v1 | HF | 591 | 541 | 541 | 0.944444 | scheduler_and_task_attributed |
| g48_pyscf_clean_slate_2026-07_v1 | MP2 | 591 | 550 | 550 | 1.212222 | scheduler_and_task_attributed |
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

## Interpretation guardrails

- Wall time is the recorded per-task overall or adapter timing; it is not normalized across hardware.
- G48 scheduler node-hours sum archived successful method jobs from the accepted pilot and production arrays; verifier and smoke jobs are excluded.
- G48 family/size rows expose task-attributed full-node hours. Scheduler allocation is reported only at method level because shards mix strata.
- Legacy and non-G48 campaigns retain wall-time summaries, but allocated node-hours are null because attributable scheduler accounting is absent.
- `not_attempted` rows are coverage records and never contribute zero seconds to timing statistics.
- These data do not support solver-efficiency rankings without a separately preregistered normalization study.

The QRE by solved-by-none frontier is intentionally outside G-51.
