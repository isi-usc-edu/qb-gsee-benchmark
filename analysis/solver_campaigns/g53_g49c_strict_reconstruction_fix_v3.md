# G-53 strict-refinement reconstruction fix v3

Date: 2026-07-15

Status: preregistered before v3 execution

The v2 runner invoked the authorized bootstrap refinement, then failed before
Newton because the shared PySCF reconstruction helper refuses a branch whose
campaign-level converged label is false. The candidate nevertheless contains
the complete canonical orbitals, occupations, density, Fock data, energy, and
spin needed to continue the preregistered refinement.

V3 passes a temporary dataclass copy with converged set true only through the
existing reconstruction helper. This does not accept the candidate. After the
single Newton refinement, the runner discards the temporary label and
recomputes G-53 acceptance from the engine flag, energy change below 1e-10 Ha,
and maximum occupied-virtual gradient below 1e-7. No scientific protocol,
branch order, follow rule, or convergence threshold changes.

All prior records remain immutable. Their actual use totals 0.1216666667
node-hours. One additional five-minute compute job keeps cumulative worst-case
use at 0.205 node-hours, below the authorized 1.0 node-hour cap.
