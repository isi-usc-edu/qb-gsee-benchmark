# G-50 endgame clean-slate solver campaign design

Date: 2026-07-15

Status: desk design only; execution held at the three gates below

## Purpose and clean-slate definition

G-50 will run iPIE, DMRG, TrimCI, and SHCI against one frozen, versioned core
task manifest after the corpus and ML-core decisions settle. A clean-slate
campaign means:

- fresh execution from checksum-bound FCIDUMPs under a new campaign identity;
- one preregistered configuration and admission model per solver;
- no pooling with legacy, G-31, G-43, or other July campaigns;
- no production reuse of pilot energies or checkpoints;
- one terminal row for every solver-task pair, including deterministic
  `not_attempted` rows for tasks outside the frozen admission region;
- immutable raw failures, accounting, environment evidence, and verifier
  reports.

The campaign panel is for solver coverage and accuracy. G-51 runtime data stay
descriptive; no hardware-normalized efficiency ranking is implied.

## Gates

Execution remains held until all three Matt-ruled gates pass in order:

1. **Core corpus settled.** Defined as: G-48 closed out, FeMoco-54 quarantine
   filed, Gao feature backfill decided, no pending task admissions/removals.
   The final task UUID manifest, FCIDUMP hashes, family and structure balance,
   source-defect exclusions, and core-manifest version then become immutable.
   Current state: G-48 closed out; FeMoco-54 quarantine filed; Gao feature
   backfill not decided; no task admissions or removals are pending. This gate
   is not satisfied.
2. **Matt's per-solver configuration sign-off.** Solver configurations are
   Matt-reserved. The implementer supplies the adapter/environment evidence,
   target-blind pilot calibration, and the options-plus-recommendation tables
   below. Matt selects or amends one option per solver and selects the iPIE
   submitter. No solver configuration, admission threshold, seed policy, or
   production cap may be frozen before that sign-off.
3. **PI design review.** After Matt's selections are encoded in immutable
   configuration manifests, the PI reviews the signed configurations,
   admission thresholds, per-task caps, total cost ceilings, pilot separation,
   v1.9 designation hooks, and the complete Swing handoff package. The PI does
   not choose or substitute solver configurations. No production `qsub` or
   Swing submission is permitted before this gate.

Before gate 2, each option package must include a clean source snapshot,
immutable dependency lock, compute-node smoke, failure-injection tests,
outcome-vocabulary tests, cost calibration, and a candidate static admission
rule. Those are evidence for Matt's decision, not an implicit configuration
freeze. All four candidate bundles must cross-check the same task manifest.

## Configuration options for Matt

Every recommendation below is provisional. The machine-readable contract keeps
all selected-option fields null until Matt signs them.

### iPIE options for Matt

| Option | Configuration | Tradeoff | Recommendation |
| --- | --- | --- | --- |
| iPIE-A | G-43 scientific baseline: UHF trial, 512 walkers, 1,000 blocks, 25 steps/block, timestep 0.005, one A100 | Proven end-to-end path and cleanest comparability; pilot must still establish uncertainty and cap | Recommended |
| iPIE-B | iPIE-A with 1,024 walkers | Lower population-control risk at roughly doubled walker work and memory | Alternative if the pilot rejects iPIE-A |
| iPIE-C | iPIE-A with 2,000 blocks | More post-equilibration samples at roughly doubled propagation work | Alternative if sampling error, rather than population control, is limiting |

Recommendation to Matt: choose iPIE-A unless the preregistered pilot fails its
uncertainty or population diagnostics; use that failure mode to choose B or C.
Matt also chooses whether his Swing agent or the implementer performs the
single-command submission.

### DMRG options for Matt

| Option | Configuration | Tradeoff | Recommendation |
| --- | --- | --- | --- |
| DMRG-A | One global, pilot-calibrated multi-bond-dimension ladder with fixed sweep counts and lowest within-run variational energy | Preserves convergence and nestedness evidence with predictable admission | Recommended |
| DMRG-B | One globally fixed terminal bond dimension and sweep schedule | Lower cost and simpler accounting, but weak convergence evidence | Not recommended for the endgame panel |
| DMRG-C | Global discarded-weight stopping rule with a hard bond-dimension ceiling | Can save work on easy rows, but makes cost prediction and cross-row comparability more complex | Alternative after a successful deterministic pilot |

Recommendation to Matt: choose DMRG-A; Matt signs the exact ordering, bond
dimensions, sweep counts, discarded-weight rule, and checkpoint policy after
pilot calibration.

### TrimCI options for Matt

| Option | Configuration | Tradeoff | Recommendation |
| --- | --- | --- | --- |
| TrimCI-A | Repaired FE path, 64-run phase-0 search, globally frozen later-phase caps, separate best-variational and PT2 records | Preserves intended search and the strongest auditable result | Recommended |
| TrimCI-B | Same FE-enabled 64-run phase 0, but variational-only production | Lower cost, but drops the PT2 axis from the clean-slate panel | Alternative if PT2 calibration exceeds the approved cap |
| TrimCI-C | Reduced phase-0 ensemble | Cheaper, but changes the intended search protocol and raises miss risk | Not recommended |

Recommendation to Matt: choose TrimCI-A. Matt signs the exact FE revision,
phase caps, seed schedule, and which preregistered energy field is eligible for
headline designation.

### SHCI options for Matt

| Option | Configuration | Tradeoff | Recommendation |
| --- | --- | --- | --- |
| SHCI-A | One global eps_var ladder with retained variational states and a preregistered PT policy | Auditable convergence ladder and strongest continuity with archival SHCI | Recommended |
| SHCI-B | Same eps_var ladder, variational energies only | Deterministic and cheaper, but omits the PT-corrected axis | Alternative if PT cost is not tractable |
| SHCI-C | One globally fixed eps_var point | Cheapest, but cannot support nestedness or convergence checks | Not recommended |

Recommendation to Matt: choose SHCI-A. Matt signs the exact binary/toolchain,
eps_var ladder, PT mode, stochastic seeds, and scratch/checkpoint policy after
pilot calibration.

## Common contract

The machine-readable companion is `g50_campaign_contract_v1.json`. All four
campaigns use `completed`, `failed`, `timeout`, and `not_attempted`; completed
energies must be finite, and every other scored energy is null. Failure stage,
wall time, software versions, hardware, input hash, adapter revision, and
campaign id are mandatory.

Admission is deterministic and target-blind. It may use NORB, electron counts,
spin sector, integral sparsity/norms, symmetry/ordering metadata, determinant
space bounds, and pilot-calibrated resource predictors. It may not use the
reference energy, accuracy threshold, prior solver outcome, or supervised
success label. Thresholds are frozen before production, and the verifier
recomputes every decision.

The planning unit is a final core of `N` tasks. Every campaign emits `N` rows;
attempt count `A_s <= N` is fixed by solver `s`'s admission rule. The hard
allocation bound is `A_s * per_task_cap + verifier/allocation overhead`, not a
q90 forecast. Exact `N`, `A_s`, and production ceilings are gate-1/gate-2
outputs.

For allocation planning before calibration, use a conservative envelope of 2
A100-hours per admitted iPIE task and 4 full-node hours per admitted task for
each CPU solver. The all-admitted upper bounds are:

| Scenario | Core rows per solver | iPIE GPU-h | DMRG + TrimCI + SHCI node-h |
| --- | ---: | ---: | ---: |
| Small core | 100 | 200 | 1,200 |
| Medium core | 250 | 500 | 3,000 |
| Full current corpus | 591 | 1,182 | 7,092 |

These are budgetary worst cases, not production requests or runtime forecasts.
Gate 2 replaces `N` with the frozen core, computes each `A_s`, and calibrates
caps from pilots; static admission should make actual cost lower.

## Metrics-spec v1.9 designation

All four G-50 campaigns integrate through the metrics-spec v1.9
headline-designation mechanism. A technically valid production result remains
excluded from headline metrics until a separate campaign designation artifact
binds its campaign id, solver id, accepted manifest hash, task/pair counts,
reference-valid scope, and explicit PI approval. The accepted G-48 designation
artifact is the structural template; it does not designate G-50.

The historical campaigns ipie_swing_2026-07 and
ipie_swing_envfix_2026-07 remain in-tree as July provenance and are explicitly
excluded from headline metrics. They cannot be pooled into, substituted for,
or used to pre-designate the clean-slate G-50 iPIE campaign.

## iPIE on Swing

Campaign id: `g50_ipie_swing_clean_slate_2026-07_v1`

The provisional recommendation iPIE-A is the documented G-43 ph-AFQMC UHF trial:
iPIE 0.7.1, one NVIDIA A100-SXM4-40GB, 512 walkers, 1,000 blocks, 25 steps per
block, timestep 0.005, phaseless, one determinant. The G-43 software snapshot
(Python 3.12.0, CuPy 13.6.0, NumPy 2.4.6, SciPy 1.18.0, h5py 3.16.0) is input
provenance, not yet the G-50 lock. Matt's sign-off selects the scientific
configuration; only then may the implementer rebuild and hash a fresh lock.

Admission must predict trial construction, Cholesky/integral memory, walker
memory, and wall cap on a 40 GB A100. UHF trial failure or insufficient finite
post-equilibration samples is an attempted failure, not `not_attempted`.
Random seed and population-control policy are frozen at gate 2; a seed changes
uncertainty, not campaign identity or task admission.

The implementer writes the complete Swing package: source snapshot, input
manifest, config generator, one-command preflight/submit wrapper, result
ledger, accounting collector, and verifier. Matt submits exactly one documented
command after the PI gate and returns scheduler records/logs. The wrapper must
fail before submission on any hash, environment, task-count, GPU, or existing-
ledger mismatch.

## DMRG

Campaign id: `g50_dmrg_clean_slate_2026-07_v1`

The July `dmrg_block2` adapter v0.1.0 and 40-core/202 GB provenance establish a
working path, but the recorded block2 version and production parameters are
insufficient for an endgame pin. DMRG-A is the implementer's recommendation,
not a decision. After Matt signs an option, the bundle freezes the block2
build, orbital ordering, sweep schedule, bond-dimension ladder,
discarded-weight cutoff, threading, checkpoint policy, and energy-selection
rule.

Admission uses deterministic memory and walltime predictors based on NORB,
electron sector, ordering features, and a preregistered short pilot. Production
must retain the full variational ladder and report the lowest *within-run*
energy only; it may not select across tuned per-task configurations.

## TrimCI

Campaign id: `g50_trimci_clean_slate_2026-07_v1`

The starting implementation is TrimCI 0.2.0 at git revision
`8944a2be6b2c1e2a4f6c6c8cbbf6355baa068393`, adapter v0.1.1, with the real
Fortran-extension path enabled. TrimCI-A is the implementer's recommendation,
not a decision. After Matt signs an option, the bundle pins the repaired FE
build and reruns the end-to-end extension smoke; the Python-only workaround is
not an accepted production configuration.

The production seed policy must preserve the intended 64-run phase-0 search.
The campaign records all phase-0 candidates and the selected variational state;
one excellent variational state is sufficient for the reported best energy,
while seed/candidate spread remains diagnostic rather than an accuracy
penalty. Admission predicts determinant growth, FE memory, orbital-optimization
cost, and PT2 cost from target-blind features and a frozen pilot. Phase caps and
the rule for variational versus PT2-reported energy are preregistered globally.

## SHCI

Campaign id: `g50_shci_clean_slate_2026-07_v1`

The July `shci_arrow` adapter v0.1.0 demonstrates the path but does not record a
complete binary/compiler/MPI lock. SHCI-A is the implementer's recommendation,
not a decision. After Matt signs an option, the bundle pins the exact SHCI
source, compiler/MPI/OpenMP environment, optimized-orbital provenance,
`eps_var` schedule, PT policy, stochastic seed policy, and
scratch/checkpoint layout.

Admission uses deterministic estimates of selected-determinant growth, memory,
PT work, and walltime. Production keeps the configured variational/PT ladder so
nestedness and convergence can be audited; a headline energy is derived only
by the preregistered rule. Historical SHCI files and ladders remain archival
comparison material, never production substitutes.

## Evidence package

Each solver bundle must contain the frozen task/admission ledger, source and
environment manifests, preflight report, prepared runs, submission ledger,
per-task raw/status records, JUnit, terminal verification, and archived
scheduler accounting. A cross-campaign verifier enforces identical task order,
exactly `4N` rows, campaign separation, target-blind admission, and cost
ceilings. S3 publication, public solution-table merge, metrics inclusion, and
headline designation are separate post-review gates.

## Cost projection deliverable at gate 2

The pilot report must fill this table with measured values before PI review:

| Solver | Core rows `N` | Admitted `A_s` | Resource | Per-task hard cap | Total hard cap | Pilot q50/q90 | Peak memory |
| --- | ---: | ---: | --- | ---: | ---: | --- | --- |
| iPIE | TBD | TBD | A100 GPU | planning: 2 h | `2 A_ipie` GPU-h | TBD | TBD |
| DMRG | TBD | TBD | full node | planning: 4 h | `4 A_dmrg` node-h | TBD | TBD |
| TrimCI | TBD | TBD | full node | planning: 4 h | `4 A_trimci` node-h | TBD | TBD |
| SHCI | TBD | TBD | full node | planning: 4 h | `4 A_shci` node-h | TBD | TBD |

The task counts and calibrated columns remain TBD because the core manifest and
admission models do not yet exist. The formulas above are sufficient for
allocation-scale planning without fabricating a production request.
