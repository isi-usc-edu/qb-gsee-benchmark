# G-40 P0 appendix divergences

## FLAG: fermionic-norm rotation counterexample

The representation tag in `draft_v1/appendices/appendix_features.tex` is
correct: the entrywise fermionic coefficient L1 norm is basis dependent and
must be tagged `BAS`, not `INV`. The specific 2x2 example in the appendix does
not establish that claim, however. A 45-degree rotation maps `diag(1, -1)` to
an off-diagonal matrix whose entrywise L1 norm is still 2.

A valid counterexample is `diag(1, 0)`: its entrywise L1 norm is 1, while a
45-degree rotation gives four entries of magnitude 1/2 and norm 2. The P0
implementation and tests use the valid example. The PI-authored appendix is
left unchanged for PI reconciliation, as required by the G-40 priority
directive.
