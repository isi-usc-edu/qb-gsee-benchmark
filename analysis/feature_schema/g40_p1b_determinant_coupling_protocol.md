# G40 P1-B determinant-coupling protocol

Status: v1 exposed unstratified sparse-class variance; v2 fixed QSZ hopping but left
rare pairing transfers noisy; v3 added exact sparse-double combinatorics; v4 doubles determinant draws
to satisfy the predeclared precision gate and requires a replacement cross-band pilot before production.

## Reference determinant

The T0 reference occupies, separately for alpha and beta electrons, the orbitals
with the lowest diagonal one-body values `h[p,p]`. Ties use the orbital index.
This rule requires no mean-field calculation. The particle counts are frozen as
`n_alpha = (NELEC + MS2) / 2` and `n_beta = (NELEC - MS2) / 2`, with invalid
parity rejected by the FCIDUMP parser. Orbital-index tie breaking makes the
reference and its coupling features ordering-sensitive when diagonal values
are degenerate; the physical outputs are therefore tagged `T0/BAS+ORD/NONE`.
It is not presented as an HF determinant.

All one-hop single and double couplings are evaluated by the spatial-orbital
Slater-Condon rules. The implementation scans sparse nonzero ERIs to identify
double-excitation candidates, then evaluates the complete direct/exchange
matrix element. Alpha and beta same-spin channels remain distinct. Unit tests
compare complete small closed- and open-shell determinant rows against PySCF.

## Concentration features

The relative scale is

`max(max_pq |h[p,q]|, max_pqrs |(pq|rs)|)`.

The frozen relative threshold grid is
`[1e-12, 1e-10, 1e-8, 1e-6, 1e-4, 1e-2]`; counts use strict `>`.
`det_coupling_nonzero_degree` counts all nonzero one-hop couplings. Top-k mass
for `k = 1, 10, 100` is the fraction of total squared coupling mass in the k
largest magnitudes. The participation ratio is
`(sum |H_DI|^2)^2 / sum |H_DI|^4`, with zero for an empty distribution.

The tail slope sorts positive magnitudes in descending order, drops the first
`max(1, floor(0.2 n))` values, and fits
`log10(|H_DI| / scale)` against `log10(rank)` over the remainder. It is null
when fewer than eight positive couplings exist or fewer than four tail points
remain. Rank is the global one-based rank before the head is dropped. For an
empty coupling distribution every top-k mass fraction is defined as `0.0`.

## Random-determinant branching

The profile draws 64 determinants uniformly from the fixed `(N_alpha,N_beta)`
sector with NumPy PCG64 seed 40040. For each determinant it draws 512 substitutions with replacement from each
nonempty legal excitation class: singles, alpha-alpha doubles, beta-beta
doubles, and alpha-beta doubles. Stratifying the classes prevents the
combinatorially dominant double space from starving sparse hopping events. The estimated degree at each frozen
threshold is the observed hit fraction times the exact combinatorial number of
legal substitutions. For tensors with at most 100,000 symmetry-unique ERI records, double-excitation
degrees are instead summed exactly and weighted by the fixed-sector
hypergeometric probability that both holes are occupied and both particles are
empty. Singles remain stratified-sampled. Denser tensors use stratified Monte
Carlo for every class. The method and cutoff are audit-only.

The reported value is the mean over determinants; the
reported audit-only MC error is the sample standard deviation of the 64 degree
estimates divided by `sqrt(64)`.

The estimand, seed, determinant count, and class-stratified sampling scheme are
part of this protocol. Bitwise sample reproduction additionally uses the
versioned code snapshot because it pins NumPy RNG call order.

## Precision gate and declaration history

Production requires, for every task and threshold,
`MC standard error <= max(1.0, 0.1 * expected degree)`. This rule first entered
the committed record in `59d9517`, after the v1-v4 pilot runs whose acceptance
it was used to assess. It was therefore not predeclared before those runs. The
pilot history and results remain valid as an empirical calibration, but the
timing is recorded explicitly. Future gates described as predeclared must be
committed before their gated runs are submitted.

The seed, determinant count, substitutions per class, reference rule,
MC errors, and extractor version are audit-only. They are retained beside the
model-eligible expected-degree values and bind resume-state identity.

## Representation gate

The G21 smoke check passed both certified equivalence groups with extractor
`g40_p1b_determinant_coupling_v4`: the block declares no `INV` features and at least one `BAS` feature changed in each group. The exact check is regenerated
from checksum-bound states for the committed pilot and production reports.

No feature-table values are changed before the pilot is accepted.
