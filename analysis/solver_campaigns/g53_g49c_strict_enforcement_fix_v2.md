# G-53 strict-enforcement implementation fix v2

Date: 2026-07-15

Status: preregistered before v2 execution

The v1 strict-remediation runner correctly relabeled the Newton bootstrap as
unconverged because PySCF's engine flag remained false, despite strict numeric
energy and gradient values. It then stopped without invoking the one strict
Newton refinement already authorized by the remediation design. Its verifier
also produced a false pass because it permitted an unresolved search with zero
clean minima.

This is an implementation correction, not a protocol change. The v2 runner
applies the one authorized strict refinement to the bootstrap candidate as
well as later followed candidates. The verifier requires a completed,
exhausted search, at least one internally and externally clean minimum, and
both strict convergence inequalities for every point labeled converged.

The original G-49c launch and v1 strict-remediation records remain immutable.
Their actual PBS use totals 0.1036111111 node-hours. One additional five-minute
full-node compute job keeps cumulative worst-case use at 0.1869444444, below
the authorized 1.0 node-hour cap.
