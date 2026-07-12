# G40 P1-D exact interaction-spectrum protocol

Status: definition and pilot gate frozen before the first P1-D compute run.

## Matrix convention

The input is the duplicate-averaged canonical FCIDUMP tensor from P1-A. The
full pair matrix is `M[(p,q),(r,s)] = V[p,q,r,s]`. P1-D restricts it to the
normalized symmetric-pair basis with `p >= q`: diagonal pairs have weight 1
and off-diagonal pairs have weight `sqrt(2)`. Thus

`M_sym[(p,q),(r,s)] = w[p,q] * w[r,s] * V[p,q,r,s]`.

Rows and columns with no nonzero tensor entry are omitted before the dense
eigensolve. This is exact support reduction: those omitted basis vectors are
null modes, so the complete nonzero spectrum and every reported statistic are
unchanged. The full and active pair dimensions are retained as audit columns.

The active real-symmetric matrix is diagonalized in float64 with SciPy LAPACK
`eigh(..., eigvals_only=True, driver="evd")`. Eigenvalues with
`abs(lambda) <= max(1e-12 Ha, 1e-12 * max(abs(lambda)))` are set to zero. No
partial eigensolver, randomized estimator, Cholesky truncation, or stochastic
trace approximation is permitted in v1.

## Features

Let `a_k` be all `abs(lambda_k)` sorted descending, `A = sum_k a_k`, and
`p_k = a_k/A` over nonzero values.

- Relative ranks use strict `a_k > tau * a_1` for `tau = 1e-2, 1e-4, 1e-6`.
- Effective rank is `exp(-sum_k p_k log(p_k))`.
- Participation rank is `A^2 / sum_k a_k^2`.
- Decay exponent is the least-squares slope of `log10(a_k)` against
  `log10(k)` for one-based `k = 1..rank(1e-4)`; it is null for fewer than two
  retained values.
- Relative gap is `(a_1-a_2)/a_1`, with `a_2=0` for a one-mode tensor.
- Negative-mass fraction is `sum_{lambda<0}|lambda| / A` and is audit-only.
- Every ratio/rank is zero for an all-zero tensor.

All seven model columns are `T0/INV/NONE`. Scale, dimensions, tolerances,
negative mass, and extractor version are audit-only. The named representation
gate requires agreement on both G21 orbital-rotation pairs and the certified
molecular/lattice orbital-permutation pairs.

## Legacy comparison

The legacy implementation reshaped the full `N^2 x N^2` tensor, diagonalized
it densely, retained only positive eigenvalues `lambda >= 1e-8 Ha`, sorted them
ascending, set `df_rank` to their count, and defined `df_gap` as the absolute
difference between the two largest retained positive eigenvalues. It did not
use relative thresholds, absolute-value ranks, symmetric-pair normalization,
or a non-PSD diagnostic. P1-D therefore uses new names during the pilot. The
pilot-review comparison will report overlap and residuals on all 184 rows with
legacy `df_*` coverage before the PI chooses same-name backfill versus permanent
new names.

## Pilot gate

The committed 25-task selection spans NORB 5-256, includes all four G21 tasks,
the largest-NORB 256-orbital task, dense molecular cases through NORB 135, and
the NORB-179 UEG active-pair worst case. Acceptance requires 25/25 successful
checksum-bound states, exact-version consistency, the combined representation
gate green, zero numerical exceptions, and a measured runtime/memory report.
The subsequent 184-row legacy-comparison batch is not submitted until this
resource gate is reviewed.
