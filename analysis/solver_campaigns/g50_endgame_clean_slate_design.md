# G-50 endgame clean-slate solver campaign design

Date: 2026-07-15

Status: pilot design submitted; execution held for PI design review

Changelog 2026-07-15: corpus gate settled at 718 tasks; Matt selected iPIE-A,
DMRG-A, TrimCI-A, and SHCI-A, selected himself as Swing submitter, and added
the DMRG/TrimCI retained-rung directives below.

Changelog 2026-07-16: O34 replaced solver-specific admission with a universal
attempt policy and one uniform per-task resource cap. The 12-hour value is a
planning cap; Matt pins the final value at gate 3 from pilot measurements.

## Purpose and clean-slate definition

G-50 will run iPIE, DMRG, TrimCI, and SHCI against one frozen, versioned core
task manifest after the corpus and ML-core decisions settle. A clean-slate
campaign means:

- fresh execution from checksum-bound FCIDUMPs under a new campaign identity;
- one preregistered configuration per solver and one uniform resource cap;
- no pooling with legacy, G-31, G-43, or other July campaigns;
- no production reuse of pilot energies or checkpoints;
- every solver attempts every task, with one terminal row for each pair;
- `timeout` is a scored non-success, while OOM and build/ingest failures are
  `failed`; `not_attempted` is forbidden for these four campaign solvers;
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
   backfill merged; no task admissions or removals are pending. The settled
   corpus contains 718 tasks. This gate is satisfied.
2. **Matt's per-solver configuration sign-off.** Solver configurations are
   Matt-reserved. The implementer supplies the adapter/environment evidence,
   resource-cap pilot calibration, and the options-plus-recommendation tables
   below. Matt selects or amends one option per solver and selects the iPIE
   submitter. No solver configuration, seed policy, or final production cap
   may be frozen before that sign-off. Matt selected iPIE-A,
   DMRG-A, TrimCI-A, and SHCI-A and selected himself as the Swing submitter.
   This gate is satisfied; exact numeric pins remain pilot outputs.
3. **PI design review.** After Matt's selections are encoded in immutable
   configuration manifests, the PI reviews the signed configurations, the
   pilot-derived uniform cap recommendation and campaign-budget projection,
   pilot separation, v1.9 designation hooks, and the complete Swing handoff
   package. The PI does
   not choose or substitute solver configurations. This gate remains pending.
   No production `qsub` or Swing submission is permitted before it.

The evidence supplied for gate 2 includes a clean source snapshot,
immutable dependency lock, compute-node smoke, failure-injection tests,
outcome-vocabulary tests, measured walltime and peak-memory distributions,
timeout-fraction projection, and campaign-budget projection. Those are
evidence for Matt's decision. Exact ladders, phase caps, seeds, and the final
uniform cap remain pilot-calibrated numeric pins. All four candidate bundles
must cross-check the same task manifest.

## Configuration options for Matt

The tables preserve the alternatives presented to Matt. The machine-readable
contract now records his binding selections.

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

**Selected: iPIE-A. Submitter: Matt on Swing.** Pilot diagnostics calibrate
uncertainty and cost but do not silently switch the selected option.

### DMRG options for Matt

| Option | Configuration | Tradeoff | Recommendation |
| --- | --- | --- | --- |
| DMRG-A | One global, pilot-calibrated multi-bond-dimension ladder with fixed sweep counts and lowest within-run variational energy | Preserves convergence and nestedness evidence under a fixed cap | Recommended |
| DMRG-B | One globally fixed terminal bond dimension and sweep schedule | Lower cost and simpler accounting, but weak convergence evidence | Not recommended for the endgame panel |
| DMRG-C | Global discarded-weight stopping rule with a hard bond-dimension ceiling | Can save work on easy rows, but makes cost prediction and cross-row comparability more complex | Alternative after a successful deterministic pilot |

Recommendation to Matt: choose DMRG-A; Matt signs the exact ordering, bond
dimensions, sweep counts, discarded-weight rule, and checkpoint policy after
pilot calibration.

**Selected: DMRG-A.** Every bond-dimension rung is retained as a separate,
nested result, not only the terminal lowest variational value. The pilot pins
the global ladder and sweep schedule; all retained rungs feed the
solvability-region-growth analysis.

### TrimCI options for Matt

| Option | Configuration | Tradeoff | Recommendation |
| --- | --- | --- | --- |
| TrimCI-A | Repaired FE path, 64-run phase-0 search, globally frozen later-phase caps, separate best-variational and PT2 records | Preserves intended search and the strongest auditable result | Recommended |
| TrimCI-B | Same FE-enabled 64-run phase 0, but variational-only production | Lower cost, but drops the PT2 axis from the clean-slate panel | Alternative if PT2 calibration exceeds the approved cap |
| TrimCI-C | Reduced phase-0 ensemble | Cheaper, but changes the intended search protocol and raises miss risk | Not recommended |

Recommendation to Matt: choose TrimCI-A. Matt signs the exact FE revision,
phase caps, seed schedule, and which preregistered energy field is eligible for
headline designation.

**Selected: TrimCI-A.** Pilot calibration uses a later-phase ceiling of up to
10,000,000 determinants and returns to Matt only if that ceiling is infeasible.
Production retains nested observations at every phase boundary and at a
preregistered determinant-count grid up to the ceiling, including variational
energy and PT2 where computed. Snapshotting is observation-only: it must not
alter search decisions, phase caps, or the FE execution path. If the repaired
FE path cannot expose those observations without perturbing the search, the
pilot files that result instead of changing the algorithm.

### SHCI options for Matt

| Option | Configuration | Tradeoff | Recommendation |
| --- | --- | --- | --- |
| SHCI-A | One global eps_var ladder with retained variational states and a preregistered PT policy | Auditable convergence ladder and strongest continuity with archival SHCI | Recommended |
| SHCI-B | Same eps_var ladder, variational energies only | Deterministic and cheaper, but omits the PT-corrected axis | Alternative if PT cost is not tractable |
| SHCI-C | One globally fixed eps_var point | Cheapest, but cannot support nestedness or convergence checks | Not recommended |

Recommendation to Matt: choose SHCI-A. Matt signs the exact binary/toolchain,
eps_var ladder, PT mode, stochastic seeds, and scratch/checkpoint policy after
pilot calibration.

**Selected: SHCI-A.** The pilot pins the exact global ladder and PT policy;
every configured variational/PT rung remains retained for nestedness and
solvability-region-growth analysis.

## Common contract

The machine-readable companion is `g50_campaign_contract_v1.json`. All four
campaigns use the shared four-state vocabulary: `completed`, `failed`,
`timeout`, and `not_attempted`. For G-50, every solver attempts every task, so
`not_attempted` is forbidden. A cap hit is `timeout` and is scored as a
non-success; OOM and build/ingest failures are `failed` with a recorded reason.
Completed energies must be finite, and every other scored energy is null.
Failure stage, wall time, software versions, hardware, input hash, adapter
revision, and campaign id are mandatory.

There is no admission predictor or solver-specific admission region. Every
solver attempts all `N = 718` tasks with its globally frozen scientific
configuration. Per-task scientific tuning is forbidden. The fixed hardware
unit is one 128-core Improv node for DMRG, TrimCI, and SHCI, and one A100 for
iPIE.

The working planning cap is 12 wall-clock hours per task for every solver. At
that cap, the literal all-timeout upper bounds are:

| Solver scope | Tasks | Hardware unit | Working cap | Worst-case hours |
| --- | ---: | --- | ---: | ---: |
| iPIE | 718 | one A100 | 12 h/task | 8,616 A100-h |
| each CPU solver | 718 | one 128-core node | 12 h/task | 8,616 node-h |
| all three CPU solvers | 2,154 | one 128-core node/task | 12 h/task | 25,848 node-h |

These are budgetary worst cases, not production requests or runtime forecasts.
The pilots measure walltime and peak-memory distributions and project timeout
fractions and campaign budgets. Matt pins one final uniform cap at gate 3 from
that evidence; the cap is a resource ceiling, not a per-task tuning parameter.

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

The selected iPIE-A configuration is the documented G-43 ph-AFQMC UHF trial:
iPIE 0.7.1, one NVIDIA A100-SXM4-40GB, 512 walkers, 1,000 blocks, 25 steps per
block, timestep 0.005, phaseless, one determinant. The G-43 software snapshot
(Python 3.12.0, CuPy 13.6.0, NumPy 2.4.6, SciPy 1.18.0, h5py 3.16.0) is input
provenance, not yet the G-50 lock. Matt's sign-off selects the scientific
configuration and himself as submitter; the implementer now rebuilds and
hashes a fresh lock for the pilot package.

Every task receives one attempted iPIE run on a 40 GB A100 under the uniform
cap. UHF trial failure, OOM, or insufficient finite post-equilibration samples
is a recorded non-success, never `not_attempted`. Random seed and
population-control policy are frozen in the preregistered pilot design before
PI review; a seed changes uncertainty, not campaign identity or attempt scope.

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
insufficient for an endgame pin. DMRG-A is selected. The pilot bundle freezes
the block2 build, orbital ordering, sweep schedule, bond-dimension ladder,
discarded-weight cutoff, threading, checkpoint policy, and energy-selection
rule.

Every task receives one attempted DMRG run on a whole 128-core node under the
uniform cap. Production must retain every completed variational rung as a
separately addressable nested result and report the lowest *within-run* energy
only; it may not select across tuned per-task configurations.

## TrimCI

Campaign id: `g50_trimci_clean_slate_2026-07_v1`

The starting implementation is TrimCI 0.2.0 at git revision
`8944a2be6b2c1e2a4f6c6c8cbbf6355baa068393`, adapter v0.1.1, with the real
Fortran-extension path enabled. TrimCI-A is selected. The pilot bundle pins
the repaired FE build and reruns the end-to-end extension smoke; the
Python-only workaround is not an accepted production configuration.

The production seed policy must preserve the intended 64-run phase-0 search.
The campaign records all phase-0 candidates and the selected variational state;
one excellent variational state is sufficient for the reported best energy,
while seed/candidate spread remains diagnostic rather than an accuracy
penalty. Every task receives one attempted TrimCI run on a whole 128-core node
under the uniform cap. Phase caps and the rule for variational versus
PT2-reported energy are preregistered globally. The pilot tests the
10,000,000-determinant ceiling and pins a nested
determinant milestone grid. Milestone capture is observation-only and cannot
alter the FE search protocol.

## SHCI

Campaign id: `g50_shci_clean_slate_2026-07_v1`

The July `shci_arrow` adapter v0.1.0 demonstrates the path but does not record a
complete binary/compiler/MPI lock. SHCI-A is selected. The pilot bundle pins
the exact SHCI source, compiler/MPI/OpenMP environment, optimized-orbital
provenance,
`eps_var` schedule, PT policy, stochastic seed policy, and
scratch/checkpoint layout.

Every task receives one attempted SHCI run on a whole 128-core node under the
uniform cap. Production keeps the configured variational/PT ladder so
nestedness and convergence can be audited; a headline energy is derived only
by the preregistered rule. Historical SHCI files and ladders remain archival
comparison material, never production substitutes.

## Evidence package

Each solver bundle must contain the frozen task ledger, source and environment
manifests, preflight report, prepared runs, submission ledger, per-task
raw/status records, JUnit, terminal verification, and archived scheduler
accounting. A cross-campaign verifier enforces identical task order, exactly
`4N` attempted rows, campaign separation, the uniform cap, and the prohibition
on `not_attempted`. S3 publication, public solution-table merge, metrics
inclusion, and headline designation are separate post-review gates.

## Uniform-cap deliverable at gate 3

The pilot report must fill this table with measured values before PI review:

| Solver | Attempted rows | Resource | Working cap | Pilot walltime distribution | Peak memory | Projected timeout fraction | Projected campaign cost |
| --- | ---: | --- | ---: | --- | --- | --- | --- |
| iPIE | 718 | one A100 | 12 h/task | TBD | TBD | TBD | TBD |
| DMRG | 718 | one 128-core node | 12 h/task | TBD | TBD | TBD | TBD |
| TrimCI | 718 | one 128-core node | 12 h/task | TBD | TBD | TBD | TBD |
| SHCI | 718 | one 128-core node | 12 h/task | TBD | TBD | TBD | TBD |

The pilot report recommends one uniform cap from these distributions and
projections. Matt pins the final value at gate 3. No admission ledger is
produced. The resource-cap pilot design is `g50_pilot_design_v1.md` with
machine-readable companion `g50_pilot_design_v1.json`.
