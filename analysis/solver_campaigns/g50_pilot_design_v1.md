# G-50 target-blind pilot design v1

Date: 2026-07-16

Status: submitted for PI review; all pilot and production execution held

## Decision requested

Authorize only the four calibration pilots defined here. This is not a request
to authorize any clean-slate production campaign. Pilot outputs return to the
PI as exact configuration locks, static admission ledgers over all 718 tasks,
and hard cost ceilings before gate 3 can close.

## Frozen pilot set

`g50_pilot_task_manifest_v2.json` contains 12 tasks selected reproducibly from
the frozen 718-row feature table. Selection uses rank-scaled maximin coverage
of orbital count, electron filling, spin polarization, and determinant-space
bound, with one row per family from the repository's
`canonical_problem_family` mapping. That mapping groups all `validation.*`
instances as `validation`, all Gao rows as `gao_distributed_fci`, trailing
numeric variants together, and transition-metal oxides with their metal.
Ties use task UUID. The
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
use only the frozen descriptors, pilot status, walltime, and peak memory to
propose a deterministic production admission rule.

Every proposal returns to PI review. In particular, the pilot cannot silently
change a selected solver option, choose per-task scientific settings, admit a
task to production, or convert a resource predictor into a success predictor.

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
The PI receives the complete calibration report before any production submit.
