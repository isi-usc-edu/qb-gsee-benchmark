# G-54 v2 fb87d637 real-UHF disconnected-basin search

Date: 2026-07-17

Status: preregistered before execution

## Scope and single protocol delta

G-54 v2 is a new annotation-only generation,
`g49c_uhf_multifollow_v2`, under the unchanged
`g49_pyscf_stability_resolved_2026-07_v1` campaign. It never pools with or
replaces G-48, G-53, or G-54 v1 records. The search remains restricted to
real UHF and performs no GHF, complex-orbital, or external-stability
operation.

The only scientific protocol change from G-54 v1 is that each branch may use
up to eight strict Newton refinement cycles instead of one. One refinement
cycle is one invocation of the same frozen PySCF second-order Newton kernel,
initialized from the immediately preceding branch orbitals and occupations.
Strict acceptance is evaluated after every cycle. Refinement stops early when
the unchanged engine-convergence, energy-change, and occupied-virtual-gradient
tests all pass, or when no orbitals remain available; otherwise it stops after
cycle eight. The kernel configuration within a cycle is unchanged from v1.

The disposition names are fixed before execution as `stable_lower_found`,
`no_lower_stable_within_protocol`, and `still_unresolved`. This is a reporting
schema replacement for the three v1 outcomes, not a change to their scientific
decision rules.

## Frozen search

The G-53 fb87d637 terminal energy, -46.05956572894405 Ha, and density hash
remain report-only comparators. Neither is used to initialize, rank, stop,
accept, or prune a branch. There is no target energy.

The search starts from the same four frozen MFPROTO-v3 UHF densities, in the
same order: G1 canonical one-body occupations, G2 shipped-orbital occupations,
G3 alternating shipped-orbital occupations, and G4 finite-temperature
one-body occupations. Starts are never selected by energy. Converged states
are deduplicated at combined alpha/beta density Frobenius distance 1e-6.

Each distinct converged start seeds the unchanged deterministic breadth-first
internal multi-follow. At every stationary point, all internal roots no more
than 5e-5 Ha above the lowest root are followed. Root signs, queue ordering,
density deduplication, the 16-point global budget, and the six-hop cap are
unchanged. Search is exhausted only when all four starts and all reachable
in-window roots have been processed. A start failure, root-enumeration failure,
panel disagreement, hop cap, or stationary-point cap produces
`still_unresolved`.

## Frozen convergence and stability

A stationary point still requires engine convergence, final energy change
strictly below 1e-10 Ha, and maximum occupied-virtual gradient strictly below
1e-7. No threshold or engine-acceptance rule changes in v2.

Every claimed within-UHF-stable minimum still requires the same two
independent deterministic Davidson start panels. Panel A uses unit vectors at
the eight lowest finite internal-Hessian diagonal entries. Panel B uses eight
orthonormalized Rademacher vectors derived from SHA-256 of the task UUID,
stationary density hash, and counter. Each root residual must be at most 1e-7;
the two lowest roots must agree within 1e-6 Ha and both be at least -1e-5 Ha.
Panel failure or disagreement is unresolved, never stable. This remains
internal real-UHF tangent-space certification only.

`stable_lower_found` requires at least one certified within-UHF-stable point
below the report-only G-53 comparator. `no_lower_stable_within_protocol`
requires no such point and complete exhaustion of the frozen search.
`still_unresolved` covers every other completed search outcome.

## Cost and evidence

One Improv `compute` job requests one whole 128-core node, no explicit memory,
and 00:30:00 walltime. The task and verifier share that allocation, so the hard
cap is exactly 0.5 node-hours. `debug` is forbidden. `backfill` is allowed only
after a documented compute-allocation exhaustion rejection, as an immutable
queue-only amendment.

This separate public preregistration commit must precede `qsub`. The distinct
v2 bundle must bind code, input, both public protocol generations, environment,
and preregistration hashes; fail closed before submission; and archive raw
`qstat -xf`, accounting, JUnit, environment, start, stationary-point, branch,
per-branch refinement-cycle, and two-panel stability records before closeout.
