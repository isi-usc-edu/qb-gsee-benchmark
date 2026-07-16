# G58 JW encoding statistics protocol v1

Status: preregistered before pilot or production compute  
Protocol identifier: `g58_jw_encoding_v1`  
Parent repository commit: `54abae48eea9b24a612f53b46e6be8061800b875`

## Scope

G58 fills the 15 current `jw_encoding` feature columns for the 534 rows where
all 15 are null. Existing populated cells are immutable production inputs; a
stratified covered-row sample is recomputed only as a compatibility gate.

This protocol preserves the existing column semantics. It does not reinterpret
the block as a spin-orbital encoding and does not change the feature-table
shape. The companion JSON contract is machine-readable and binding.

## Declared representation

Let `N = NORB`. The modes and qubits are the `N` FCIDUMP orbitals in their
shipped, zero-based order: mode `p` maps to qubit `p`. The operator used by the
existing block is

```text
Q = sum[p,q] h[p,q] a_p^ a_q
  + sum[p,q,r,s] V[p,q,r,s] a_p^ a_q a_r^ a_s,
```

where `h` is the restored real one-body matrix and `V` is the real, eightfold
symmetry-restored FCIDUMP two-electron tensor in chemist order. This convention
has one fermionic mode per FCIDUMP orbital and no additional one-half prefactor.
It is the convention being measured, not a claim that `Q` is the physical
spin-orbital Hamiltonian.

The Dirac-to-Majorana map is

```text
a_p^ = (gamma[2p] - i gamma[2p+1]) / 2
a_p  = (gamma[2p] + i gamma[2p+1]) / 2.
```

Majorana products are canonicalized in increasing index order, repeated
Majoranas cancel, permutation parity is retained, and equal canonical strings
are summed. After aggregation, coefficients with absolute value below
`1.0e-8` are removed. Jordan-Wigner then maps

```text
gamma[2p]   -> Z[0] ... Z[p-1] X[p]
gamma[2p+1] -> Z[0] ... Z[p-1] Y[p].
```

Canonical Majorana monomials map one-to-one to Pauli strings, so an exact
implementation may compute support and coefficient statistics without
constructing Pauli-operator objects.

## Hypergraph and exact definitions

`number_of_terms` counts every surviving Pauli string, including the identity.
All other statistics exclude the identity. Let `E` be the nonidentity strings,
`S_e` the qubits on which string `e` acts nontrivially, `w_e = |c_e|`, and
`V_touch = union_e S_e`. Only touched vertices participate in degree moments.
Population standard deviation (`ddof = 0`) is used throughout.

| Column | Exact definition |
| --- | --- |
| `max_vertex_degree` | `max_v sum_e 1[v in S_e]`, `v in V_touch` |
| `min_vertex_degree` | corresponding minimum over `V_touch` |
| `mean_vertex_degree` | population mean over touched-vertex degrees |
| `std_dev_vertex_degree` | population standard deviation of touched-vertex degrees |
| `max_weight` | `max_e w_e` |
| `mean_weight` | population mean of `w_e` |
| `std_dev_weight` | population standard deviation of `w_e` |
| `mean_edge_order` | population mean of `|S_e|` |
| `std_dev_edge_order` | population standard deviation of `|S_e|` |
| `number_of_terms` | surviving identity plus nonidentity Pauli-string count |
| `pauli_terms_per_orbital_quartic` | `number_of_terms / N^4` |
| `mean_vertex_degree_per_orbital` | `mean_vertex_degree / N` |
| `max_vertex_degree_per_orbital` | `max_vertex_degree / N` |
| `vertex_degree_coefficient_of_variation` | `std_dev_vertex_degree / mean_vertex_degree` |
| `edge_order_coefficient_of_variation` | `std_dev_edge_order / mean_edge_order` |

An empty nonidentity support, nonfinite coefficient, complex residue above
`1.0e-10`, nonpositive denominator, or missing/invalid `NORB` is infeasible;
the 15 cells remain null with a machine-readable reason.

## Exact computation route

1. Verify the supporting-object checksum, stream/decompress the FCIDUMP, and
   fail on conflicting symmetry-equivalent records.
2. Canonicalize one- and two-body records under the declared Hermitian/eightfold
   symmetries. Group two-body records by orbital-index multiset.
3. Apply the exact eightfold-symmetry Majorana formulas. Terms that receive
   contributions from multiple groups use an `O(N^2)` accumulator. Unique
   quartic Majorana terms stream directly into coefficient, edge-order, and
   vertex-degree sufficient statistics after the absolute threshold.
4. Determine JW support directly from each canonical Majorana tuple. Do not
   construct dense `N^4` tensors or Pauli-operator objects.
5. A reference materialization route is permitted only for compatibility tests
   when its deterministic upper bound is at most 2,000,000 Pauli terms and its
   estimated peak RSS is at most 32 GiB. It must agree with the streaming route.

No sampled, pruned, rounded, or statistically estimated value may enter these
columns. Integral sparsity changes runtime only; it does not change definitions.

## Compatibility and feasibility gates

Before the worst-case pilot, recompute at least 12 covered rows spanning every
available covered source class and small-to-large size regimes. The committed
184-row block contains molecular and synthetic rows but no lattice row; the
mandated 256-orbital lattice pilot therefore validates exact execution but has
no historical value to compare. Integer-valued columns must agree exactly with
the committed table. Floating columns must agree within
`rtol = 5e-9, atol = 5e-10`. Any systematic mismatch holds production and
requires a versioned protocol amendment.

Every task emits one atomic result record with status `exact`, `infeasible`,
`timeout`, or `failed`. Infeasible reasons are restricted to the enum in the
JSON contract. A task is infeasible before launch when checksum/input access
fails, the exact temporary-disk projection exceeds 180 GiB, or exact peak RSS
projects above 192 GiB. At runtime, a task is infeasible if exact intermediate
state reaches either bound. Timeout and application failures are distinct from
infeasibility and never produce feature values.

The pilot contains the 256-orbital lattice case, 135-orbital Cr case, and
largest-orbital Gao case, plus compatibility controls. Projection uses measured
walltime and peak RSS stratified by integral-record/multiset counts, with
deterministic first-fit-decreasing packing under the same worker and memory
limits intended for production. Cumulative pilot plus projected production
must be at most 20 node-hours to proceed automatically. Cumulative executed
G58 work has a hard 25-node-hour cap.

## Production and merge discipline

- Improv whole CPU nodes: `select=1:ncpus=128`, no memory request.
- Use `compute`; use explicit `backfill` only after normal allocation is
  exhausted. Do not use `debug`.
- Force implicit numerical thread pools to one thread. Worker concurrency is
  chosen from measured pilot RSS and never exceeds 128 processes per node.
- Jobs are restartable by task UUID, write exclusive logs, and atomically rename
  terminal result records.
- Production writes a held candidate CSV and complete status/accounting
  ledgers. It does not edit the public feature table in place.
- Merge requires held verification, raw JUnit and environment evidence, a filed
  evidence line, and fresh GR23-O1 PI acknowledgment. The table remains
  718 rows by 580 columns and only null cells in the 15 named columns may fill.

