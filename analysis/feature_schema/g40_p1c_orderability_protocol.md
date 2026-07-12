# G40 P1-C orderability and MPO-compressibility protocol

Status: extractor implemented; focused tests pass; cross-band compute pilot is
required before production or feature-table population.

## Interaction graph

For distinct spatial orbitals `p,q`, the symmetric graph weight is

`w[p,q] = |h[p,q]| + sqrt(sum_rs |V[p,r,q,s]|^2)`.

Here `V[p,r,q,s]` is read in the chemists-notation FCIDUMP convention used by
the canonical sparse parser.

The diagonal is zero. This exchange-block Frobenius graph uses the complete
two-electron tensor rather than only density-density terms. It is basis
sensitive. Edge count uses strict positive weight and total weight counts each
undirected edge once.

## Ordering panel

The four frozen heuristics are the weighted combinatorial-Laplacian Fiedler
order, unweighted reverse Cuthill-McKee, minimum-degree elimination with fill,
and the normalized-Laplacian linear-arrangement relaxation. An eigenvector sign
is fixed by making its largest-absolute component positive; equal coordinates
are ordered by orbital index. A min-fill elimination independently
reports its maximum active-neighbor count as a treewidth upper bound.

For each ordering and cut, cut weight is the sum of graph weights crossing the
cut. Each heuristic reports maximum, 95th percentile, and sum over all cuts.
Best-of-heuristics is the minimum separately for each statistic. Improvement
over shipped and deterministic-random order is `1 - best / baseline`, or zero
when the baseline is zero. Heuristic spread is `(max - min) / max`, or zero
when all values are zero. The 95th percentile uses NumPy's linear
interpolation convention. The random baseline is one NumPy PCG64 permutation
at seed 40041 and is therefore shared across all tasks with equal `NORB`.

Heuristic and best-of-heuristic graph values are `T0/BAS/NONE`. Shipped/random
baselines and relative improvements are conservatively `T0/BAS+ORD/NONE`.

## Coefficient-matricization panel

The MPO-side ordering is the heuristic with minimum total graph cut weight,
with the heuristic name as a deterministic tie-break. At every orbital cut,
the two-electron coefficients are matricized as

`M_cut[(p,r),(q,s)] = V[p,r,q,s]`

for `p,r` left of the cut and `q,s` right of it. The per-cut effective rank is
the exact Renyi-2 singular-value participation rank

`r_eff = ||M||_F^4 / ||M^T M||_F^2`.

An all-zero cut matricization has `r_eff := 0.0`.

The implementation uses sparse matrices and forms the Gram matrix on the
smaller side. The model columns are maximum, 95th percentile, and mean rank
over all cuts. These are coefficient/MPO-compressibility diagnostics only:
they are not an exact MPO bond dimension and contain no wavefunction or state
entanglement data. They are tagged `T0/BAS+ORD/NONE`.

Seed, chosen heuristic names, and extractor version are audit-only. Runtime
and peak memory across the NORB 5-256 cross-band pilot determine whether the
exact all-cut implementation is viable for production; approximation or cut
subsampling requires an explicit PI reconciliation and version change.
