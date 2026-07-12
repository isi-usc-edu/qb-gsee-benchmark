# G40 P1-B determinant-coupling protocol

Status: v1 exposed unstratified sparse-class variance; v2 fixed QSZ hopping but left
rare pairing transfers noisy; v3 adds exact sparse-double combinatorics and
requires a replacement cross-band pilot before production.

## Reference determinant

The T0 reference occupies, separately for alpha and beta electrons, the orbitals
with the lowest diagonal one-body values `h[p,p]`. Ties use the orbital index.
This rule is equivariant under orbital permutation and requires no mean-field
calculation. It is basis-sensitive and all physical outputs are tagged
`T0/BAS/NONE`. It is not presented as an HF determinant.

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
20 percent (at least the largest value), and fits
`log10(|H_DI| / scale)` against `log10(rank)` over the remainder. It is null
when fewer than eight positive couplings exist or fewer than four tail points
remain.

## Random-determinant branching

The profile draws 32 determinants uniformly from the fixed `(N_alpha,N_beta)`
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
reported audit-only MC error is the sample standard deviation of the 32 degree
estimates divided by `sqrt(32)`.

The seed, determinant count, substitutions per class, reference rule,
MC errors, and extractor version are audit-only. They are retained beside the
model-eligible expected-degree values and bind resume-state identity.

## Representation gate

The G21 smoke check passed both certified equivalence groups with extractor
`g40_p1b_determinant_coupling_v3`: the block declares no `INV` features and at least one `BAS` feature changed in each group. The exact check is regenerated
from checksum-bound states for the committed pilot and production reports.

No feature-table values are changed before the pilot is accepted.
