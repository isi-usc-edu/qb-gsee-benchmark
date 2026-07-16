# G-53 G-49c strict-tolerance remediation

Date: 2026-07-15

Status: preregistered before remediation execution

The first G-49c array and verifier completed successfully at the scheduler
level, but the verifier produced a false pass. The frozen MFPROTO-v3 helper
internally labels a branch converged at 1e-9 Ha energy change and 1e-6
maximum occupied-virtual gradient. G-53 preregistered stricter limits of
1e-10 Ha and 1e-7. The first verifier asserted the gradient limit but
omitted the energy-change limit.

Only the terminal fb87d637 branch violates the G-53 contract:
1.9818457985820714e-10 Ha energy change with a 9.91708444111875e-8
gradient. The ab61c91a result and all ca6f7678 stationary points satisfy
both strict limits and remain accepted, immutable first-generation evidence.
The original verifier JSON and raw JUnit are retained but explicitly invalid
as acceptance evidence.

The remediation reruns only fb87d637 under the distinct generation
g49c_strict_tolerance_fix_v1. After every SCF stage, acceptance is recomputed
as engine-converged AND energy change strictly below 1e-10 Ha AND maximum
occupied-virtual gradient strictly below 1e-7. A candidate that meets the
frozen MFPROTO-v3 helper criterion but misses either G-53 limit receives one
Newton refinement from its current orbitals. The standard frozen Newton
controls are retained except that conv_tol=1e-10 and
conv_tol_grad=1e-7 enforce the already-preregistered G-53 limits. The
stability roots, two-hop follower, density deduplication, and all other
protocol choices are unchanged.

The first launch consumed 0.0847222222 node-hours from PBS accounting. One
five-minute full-node compute job adds at most 0.0833333333, so cumulative
worst-case use is 0.1680555556, below the authorized 1.0 node-hour cap.
Verification runs after the job without another scheduler node. The corrected
verifier must assert both strict convergence inequalities and emit a new raw
JUnit. The remediation replaces only the fb87d637 row if that verifier
passes; generations are never pooled.
