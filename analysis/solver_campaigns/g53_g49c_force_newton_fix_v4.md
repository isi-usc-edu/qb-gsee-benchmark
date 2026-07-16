# G-53 forced-Newton implementation fix v4

Date: 2026-07-15

Status: preregistered before v4 execution

V3 passed a temporary usable branch through the existing reconstruction helper,
which sets the reconstructed PySCF object's engine-converged flag true. The
Newton wrapper consequently executed zero cycles and returned an
engine-unconverged result. The strengthened verifier correctly rejected that
trajectory for an unresolved search and zero clean minima.

V4 clears the reconstructed solver's transient engine-converged flag
immediately before constructing the Newton wrapper. This forces the single
already-authorized strict refinement to execute. The orbitals, density,
thresholds, Newton controls, branch order, follow rule, and one-refinement cap
are unchanged. Strict G-53 acceptance is recomputed only after Newton.

All prior records remain immutable. Their actual use totals 0.1397222222
node-hours. One additional five-minute compute job keeps cumulative worst-case
use at 0.2230555556, below the authorized 1.0 node-hour cap.
