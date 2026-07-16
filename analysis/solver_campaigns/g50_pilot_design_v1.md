# G-50 universal-attempt resource-cap pilot design v1

Date: 2026-07-16

Status: three Improv CPU pilots authorized; Swing submission and all
production execution held

Scope amendment 2026-07-16: production uses the future frozen ML-5 binding
manifest at Matt's gate-3 k. The 12-task pilot is unchanged and is not gated
on ML-5.

## Authorization record

The PI authorized the three Improv CPU calibration pilots on 2026-07-16 after
the manifest-v3 re-check recorded in `work/IMPLEMENTER_GOALS.md`. The design
review is `work/PI_REVIEW_2026-07-16_g50_pilot_design.md` at SHA-256
`2076a82e94cafd9db11f1daf761122206c5bfb7d469fe3e0863a434554eb0505`.
The iPIE Swing submission remains held for Matt, and this is not authorization
for any clean-slate production campaign. Pilot outputs return to the PI as
exact configuration locks, measured walltime and peak-memory
distributions, timeout-fraction and campaign-budget projections, and one
uniform cap recommendation before gate 3 can close.

## Frozen pilot set

`g50_pilot_task_manifest_v3.json` contains 12 tasks selected reproducibly from
the frozen 718-row feature table. Selection uses rank-scaled maximin coverage
of orbital count, electron filling, spin polarization, and determinant-space
bound, with one row per generation/import-protocol family from
`analysis/feature_schema/canonical_families_v1.json`. Family membership is an
exact task-UUID lookup of `canonical_family_recommended`; v2 remains retained
as the superseded audit predecessor. Ties use task UUID. The
manifest includes input identities and checksums, but no reference energy,
accuracy threshold, prior solver result, success label, or energy error.

The same ordered task set is presented to every solver. Extreme rows are
intentional: a one-hour timeout or pre-solver resource failure is useful pilot
evidence and remains an attempted terminal outcome. No task is dropped after
looking at a solver result.

## Pilot isolation

Pilot campaign IDs differ from all four production IDs. Pilot energies and
checkpoints are never reusable in production, and no pilot row is eligible for
headline designation. The calibration view excludes all energy fields. It may
use only pilot status, walltime, and peak memory to characterize the fixed
configurations and
recommend one uniform production cap.

Every solver will attempt every task in the frozen ML-5 binding manifest.
Tasks outside that manifest are `not_attempted` with the selection manifest
cited as the machine-readable reason; `not_attempted` is forbidden within the
manifest. A cap hit is `timeout` and is scored as a non-success; OOM and
build/ingest failures are `failed`. The pilot cannot silently change a
selected solver option, choose per-task scientific settings, or create an
admission predictor.

The 12-task pilot remains independent of the unresolved production manifest.
Its CPU shape is one 128-core node per task and iPIE uses one A100. The
production SHCI hardware shape is Matt-reserved under O35; the pilot remains
single-node unless O35 later orders the bounded multinode calibration leg.

## Solver protocols

**iPIE-A.** Use the selected UHF-trial baseline: 512 walkers, 1,000 blocks, 25
steps per block, timestep 0.005, phaseless, on one 40 GB A100. One deterministic
seed is derived from campaign ID and task UUID. Each task has a one-hour cap;
the entire Swing pilot is capped at 12 A100-hours. Matt remains the submitter.

**DMRG-A.** Pilot the global Fiedler-ordered ladder M = 256, 512, 1,024, 2,048
with 4, 4, 6, 8 sweeps and cutoff 1e-8. Every completed rung is retained; no
extrapolation is used. The pilot determines which globally fixed ladder is
defensible for production, not a different ladder for each task.

**TrimCI-A.** Use the FE-enabled build at the selected revision, the intended
64-candidate phase 0, variational and PT2 records, and observation-only
milestones at 100k, 250k, 500k, 1M, 2M, 5M, and 10M determinants. The 10M
ceiling is tested, not assumed feasible. If milestone capture perturbs FE or
search behavior, the pilot fails that requirement instead of changing the
algorithm.

**SHCI-A.** Pilot one global eps_var ladder of 2e-4, 1e-4, 5e-5, and 2e-5.
Retain every variational rung and run stochastic PT only at the terminal rung,
with a deterministic task seed. The source, binary, compiler, MPI, and OpenMP
environment must be hash-bound before execution.

## Improv resources

The three CPU pilots use `QC_NA_Sim`, `compute`, whole 128-core nodes, and no
explicit memory request. Each solver uses a four-node `pbsdsh` fan-out with at
most three one-hour tasks per node and PBS walltime 03:30:00. This caps each
CPU pilot at 14 node-hours and all three at 42 node-hours. `debug` is forbidden.
After the compute allocation is exhausted, the byte-identical package may use
`backfill`; the queue is recorded and no scientific setting changes.

## Evidence before execution

Each bundle must bind its clean source/dependency environment, this pilot
manifest hash, adapter revision, generated run configs, seed ledger, input
checksums, and empty result ledger. Preflight must reject drift, existing
results, missing FE/GPU/MPI requirements, wrong task count/order, or a
submission while authorization remains false.

After execution, retain raw statuses, rung/phase observations, walltime, peak
memory, environment capture, scheduler accounting, and a fail-closed verifier.
The report gives measured walltime and peak-memory distributions, projected
timeout fractions and campaign budgets at the candidate cap, and one uniform
cap recommendation. At gate 3, Matt jointly pins the cap, the ML-5 binding k,
and the O35 SHCI production hardware shape before any production submit.
