# G-53 G-49c protocol-extension preregistration

Date: 2026-07-15

Status: preregistered before execution

## Scope

G-53 is a distinct run generation under the existing
`g49_pyscf_stability_resolved_2026-07_v1` campaign. It addresses exactly the
three tasks authorized by O30. It does not modify or pool with the frozen G-49
or G-49b generations.

For `ab61c91a` and `fb87d637`, the checksum-bound FCIDUMP is used to reconstruct
the G-48 default open-shell UHF diagnostic state. The frozen MFPROTO-v3 Newton
controls then bootstrap that state to a converged stationary point. From that
point, the original G-49 single-lowest-root follower runs for at most two
hops. Failure to converge is retained as an attempted, unresolved result.

For `ca6f7678`, the G-48 default UHF stationary point starts a deterministic
breadth-first multi-follow. At every visited stationary point, all internal
Hessian roots no more than `5e-5 Ha` above the lowest root are followed. Roots
are enumerated by deterministic Davidson solves until the first root above the
window is established or the remaining branch budget plus one roots have been
examined. Eigenvector signs are canonicalized by making the largest-magnitude
component positive, with lowest component index breaking ties.

The queue is ordered by path depth, parent stationary-point index, root
eigenvalue, and root index. A converged density within `1e-6` combined
alpha/beta Frobenius norm of an existing density is the same stationary point.
The global budget is 16 unique converged stationary points and each path has a
six-hop cap. Reaching either cap with unexplored branches yields an unresolved,
not stability-clean result; it never selects the lowest observed energy as a
substitute for exhausting the preregistered search.

## Acceptance

An SCF point is accepted only when the PySCF engine reports convergence, its
final energy change is below `1e-10 Ha`, and its maximum occupied-virtual
gradient is below `1e-7`. A terminal minimum is stability-clean only when both
the internal and external lowest roots are at least `-1e-5 Ha`. The stability
Davidson residual tolerance remains `1e-7`.

The audit value `-45.85907658 Ha` is a report-only comparator. It is not used
to initialize, order, stop, accept, or select any branch. Any lower clean
minimum discovered by the frozen search is reported independently.

## Cost and execution gates

Execution uses the Improv `compute` queue, one full 128-core node per array
element, no explicit memory request, and no `debug` queue. Three 15-minute task
elements plus one 15-minute dependent verifier cap the generation at exactly
1.0 node-hour. `backfill` is permitted only after the compute allocation is
exhausted and requires a recorded plan amendment before submission.

Before `qsub`, the implementation must commit this preregistration, freeze a
checksum-bound bundle, run the live allocation/queue preflight, and print the
exact submission commands. The closeout must retain raw scheduler logs and
accounting, per-task stationary-point and branch accounting, a raw JUnit XML,
an environment fingerprint, and an evidence line.

## Paper consumer

The resulting sidebar describes a follower-protocol limitation caused by a
near-degenerate Hessian subspace. It does not characterize the physics as
undecidable and does not erase the host dependence or failed parent-generation
evidence.
