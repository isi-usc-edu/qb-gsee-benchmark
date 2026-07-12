# G40 P1-D pre-pilot compute estimate

Status: committed before the first exact-spectrum pilot submission.

For `N` orbitals the full symmetric-pair dimension is `m=N(N+1)/2`; dense
float64 storage is `8m^2` bytes. Exact support reduction is substantial for
on-site lattice tensors but not for dense chemistry or the plane-wave UEG.

| Representative task | NORB | Full pairs | Active pairs | Matrix GiB |
|---|---:|---:|---:|---:|
| G21 representation pair | 8 | 36 | 36 | <0.001 |
| QSZ Hubbard | 100 | 5,050 | 100 | <0.001 |
| i-FCIQMC diatomic | 108 | 5,886 | 5,886 | 0.258 |
| H2S | 119 | 7,140 | 7,140 | 0.380 |
| Sc active space | 135 | 9,180 | 9,180 | 0.628 |
| UEG N14 | 179 | 16,110 | 16,109 | 1.933 |
| QSZ Hubbard (largest NORB) | 256 | 32,896 | 256 | <0.001 |

The census itself required about seven login-node minutes and peaked near
1.6 GiB while parsing the 25 cached inputs. The eigensolve is cubic in active
pair dimension and dominates dense cases. The pilot therefore uses one whole
128-core Improv node with no explicit memory request. Small tasks may run in a
bounded parallel phase; active dimensions above 5,000 run one at a time with
threaded BLAS. Requested pilot walltime is 12 hours, for an upper bound of 12
node-hours. Production cost is intentionally not extrapolated until the
NORB-179 and dense-molecular timings are measured. `compute` is used until the
allocation is exhausted, then `backfill`.
