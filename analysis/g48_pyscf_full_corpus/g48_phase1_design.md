# G-48 PySCF Full-Corpus Panel: Phase 1 Desk Design

## Verdict

Phase 1 is complete as a design, but Phase 2 must not launch yet. Two
adapter contract fixes and a stratified pilot review are hard gates.
No solver or PBS job was run or submitted by this work.

## Scope

- Campaign: `g48_pyscf_clean_slate_2026-07_v1` (never pooled with `legacy:pyscf_solutions`).
- Original clean-slate scope: 591 tasks x 5 solvers = 2955 pairs.
- Design-for-arrival addendum: 127 Gao tasks x 5 = 635 pairs.
- Every pair has either `planned_attempt` or `not_attempted` plus a closed reason taxonomy.
- FeMoco-54 is `not_attempted: held_femoco54_pending_o27` for all five methods.
- Solver records are emitted for every task; success scoring remains restricted to reference-valid, non-test tasks.

## Tractability Model

Walltime uses method-specific fixed asymptotic forms in NORB/occupied/virtual
counts. The coefficient is the 90th percentile of observed-seconds/model-unit
over the committed legacy PySCF overlaps. The old exporter multiplied walltime
by 128 to manufacture `run_time_cpu`; that field is deliberately not used.
Legacy thread environment, peak RSS, PySCF version, and failures were not
captured, so this is a pilot-sizing model, not a production performance claim.
Memory is an analytic dense-array upper model with 25% safety and is not labeled
as measured. Admission requires projected peak <=192 GiB on a 256 GiB node.

| method | calibration n | q90 wall cap (s) | baseline attempts | baseline not attempted | baseline node-h +25% | Gao attempts |
|---|---:|---:|---:|---:|---:|---:|
| HF | 182 | 1800 | 541 | 50 | 26.421 | 127 |
| MP2 | 174 | 1800 | 550 | 41 | 26.220 | 127 |
| CISD | 182 | 3600 | 458 | 133 | 47.241 | 127 |
| CCSD | 174 | 7200 | 459 | 132 | 89.970 | 127 |
| CCSD(T) | 174 | 10800 | 438 | 153 | 170.209 | 127 |

Baseline estimated use is **360.061 node-hours** with contingency; the cap-sum upper bound is 3235.500 node-hours.
The Gao addendum is **3.259 node-hours** with contingency.
These estimates assume one 128-thread task occupies one entire Improv node.

## Required Pre-Pilot Fixes

1. `prepare_method()` currently hard-codes `pyscf_methods_2026-07`; add an explicit campaign binding and fail closed unless it equals the reviewed G-48 ID.
2. The adapter currently marks a run `completed` when HF or a post-HF solver returns with `converged=False`. Metrics v1.8 calls default non-convergence indeterminate. Preserve the diagnostic energy in raw details, emit no scored solution energy, and harvest `failed` with `attempted=true`.
3. Pin the reviewed exporter commit and exact Python/PySCF/NumPy environment in an immutable bundle; the current desk pin is Python 3.12.0, PySCF 2.8.0, NumPy 2.4.6, adapter 0.3.0.

## Settings And PBS Plan

- One run per solver-task pair; no retries, per-task tuning, frozen-orbital changes, density fitting, convergence overrides, or lowest-of-N selection.
- Preserve the method adapter's legacy RHF/UHF rule, record RHF versus UHF, all convergence flags, method defaults, software versions, solver UUID, adapter revision, task/input checksums, and 128-thread resource binding.
- Use `compute` until allocation exhaustion and then `backfill`; never `debug`. PBS requests `select=1:ncpus=128` and no memory amount, with the method wall cap from the plan.
- Use five PBS arrays (one per method), immutable index maps, unique stdout/stderr paths, an append-only submission ledger, and an `afterok` verifier only after every array is terminal. Archive `qstat -fx` accounting per array index.
- Ledger states are `prepared`, `submitted`, `terminal`, `harvested`; harness outcomes are exactly `completed`, `failed`, `timeout`, `not_attempted`. Any execution evidence forces `attempted=true`.

## Exporter Hard-Fail Rules

The verifier rejects missing or duplicate pairs; campaign/solver/task/input identity drift; schema failure; malformed status or attempted semantics; zero-duration timeout; missing convergence flags; non-finite completed energy; energy on a non-converged scored record; absent version/settings provenance; absolute cluster paths; checksum mismatch; and any silent skip. Gated pairs are materialized as schema-valid `not_attempted` records with the exact reason in the plan.

## Legacy Agreement

The legacy source has 1110 five-method pairs: 886 have direct task-UUID identity in the frozen 591 and enter the comparison manifest; 224 stale/outside-current pairs are reported but not guessed into a mapping. The audit compares campaign IDs without pooling, new/legacy outcome presence, and energy deltas at method thresholds: HF/MP2 1e-8 Ha and CISD/CCSD/CCSD(T) 1e-7 Ha. A new failure/timeout where legacy completed, a finite-energy disagreement above threshold, duplicate records, or identity mismatch is material and stops headline designation pending PI review. A preregistered G-48 gate may yield `not_comparable_new_not_attempted`, but it remains visible and is never backfilled from legacy.

## Pilot Gate

Phase 2 must stratify by method, family, size band, open/closed shell, legacy overlap, predicted cost quantile, and include the largest admissible pair per method. Pilot evidence must recalibrate wall and measured RSS, test all four harness outcomes with constructed fixtures, exercise agreement checks, and receive PI review before Phase 3. Gao rows enter through their separate arrival plan. No FeMoco-54 row enters until O27 is released.
