# G-54 fb87d637 real-UHF disconnected-basin search

Date: 2026-07-16

Status: preregistered before execution

## Scope

G-54 is a new annotation-only generation,
`g49c_uhf_multifollow_v1`, under the existing
`g49_pyscf_stability_resolved_2026-07_v1` campaign. It never pools with or
replaces G-48/G-53 records. The search is restricted to real UHF. It performs
no GHF, complex-orbital, or external-stability operation. The previously
recorded UHF-to-GHF instability remains immutable context only.

The G-53 fb87d637 terminal energy, -46.05956572894405 Ha, and density hash are
report-only comparators. Neither is used to initialize, rank, stop, accept, or
prune a branch. There is no target energy. Finding no lower real-UHF minimum
is an accepted result only if this preregistered search is exhausted.

## Global starts and branch search

The search starts from all four frozen MFPROTO-v3 UHF densities, in order:
G1 canonical one-body occupations, G2 shipped-orbital occupations, G3
alternating shipped-orbital occupations, and G4 finite-temperature one-body
occupations. Every start runs the same real-UHF primary SCF, frozen Newton
fallback, and at most one strict refinement. Starts are never selected by
energy. Converged states are deduplicated at combined alpha/beta density
Frobenius distance 1e-6.

Each distinct converged start seeds a deterministic breadth-first internal
multi-follow. At every stationary point, all internal roots no more than
5e-5 Ha above the lowest root are followed. Root signs, queue ordering, and
density deduplication match G-53. The global budget is 16 unique converged
stationary points, including starts, with a six-hop cap per path. Search is
exhausted only when all four starts and all reachable in-window roots have
been processed. A start failure, root-enumeration failure, panel disagreement,
hop cap, or stationary-point cap makes the result unresolved and forbids the
"no lower minimum found" annotation.

## Strict convergence and stability

A stationary point requires engine convergence, final energy change strictly
below 1e-10 Ha, and maximum occupied-virtual gradient strictly below 1e-7.
At most one frozen-controls Newton refinement may enforce those already-fixed
limits.

Every claimed within-UHF-stable minimum requires two independent deterministic
Davidson start panels. Panel A uses unit vectors at the eight lowest finite
internal-Hessian diagonal entries. Panel B uses eight orthonormalized
Rademacher vectors derived from SHA-256 of the task UUID, stationary density
hash, and counter. Each root residual must be at most 1e-7; the two lowest
roots must agree within 1e-6 Ha and both be at least -1e-5 Ha. Panel failure or
disagreement is unresolved, never stable. This is internal real-UHF tangent-
space certification only; the term `stability_clean` is not used.

## Cost and evidence

One Improv `compute` job requests one whole 128-core node, no explicit memory,
and 00:30:00 walltime. The task and verifier share that allocation, so the
hard cap is exactly 0.5 node-hours. `debug` is forbidden. `backfill` is allowed
only after compute allocation exhaustion with an immutable queue-only
amendment.

The public preregistration commit must precede `qsub`. The frozen bundle must
bind code, input, public protocol, and environment hashes; use the canonical
environment-capture template; fail closed before submission; and archive raw
`qstat -xf`, accounting, JUnit, environment, start, stationary-point, branch,
and two-panel stability records inside the bundle before closeout.
