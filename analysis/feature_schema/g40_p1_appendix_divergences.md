# G-40 P1 appendix divergences

## FLAG: repeated fourfold FCIDUMP records require canonicalization

The binding appendix defines features on the shipped Hamiltonian but does not
specify how to canonicalize FCIDUMPs that contain repeated pair-matrix
orientations with unequal values. The P1-A pilot encountered this in four of 25
cross-band tasks under the original strict parser.

The largest inspected case is Simons hydrogen-chain task
`81f65b14-2085-5443-b91b-3d791a55ab00`. Its PySCF-written FCIDUMP contains
49,733 duplicate two-body records beyond a `1e-8` absolute/relative symmetry
gate; the maximum observed absolute disagreement is
`0.016786249941870307` Hartree and the maximum relative disagreement is
`1.9999928374364713`. This is not roundoff-level noise. The generating script
uses `pyscf.tools.fcidump.from_scf`; PySCF's 4-fold writer can emit both
pair-matrix orientations, while its reader collapses them into an 8-fold packed
array by assignment.

P1-A v2 applies a declared policy: all repeated orientations are averaged to
form an exactly Hermitian/eightfold tensor; conflict counts and maximum
absolute/relative disagreements are retained per row; strict mode rejects any
conflict above the frozen gate. The universal pass therefore remains complete
without hiding source anomalies.

PI reconciliation is still required before model release: decide whether
conflicted source FCIDUMPs should be regenerated/canonicalized and whether the
solver harness must use the same averaging convention. Until then,
`fcidump_symmetry_status=conflict_above_tolerance` is an applicability flag,
not a benign diagnostic.

## FLAG: canonical modified-Cholesky block has no completed P1 slot

The amended appendix requires canonical modified-Cholesky rank, effective rank,
and participation/decay diagnostics across the universal corpus. P1-A populated
the 591-row linear block but did not run a modified-Cholesky extractor. The
current feature table has `df_rank`, `df_gap`, `df_eig_decay_exponent`,
`df_rank_per_orbital`, and `df_eigs` on only **184 of 591** rows. No universal
post-P1-A extractor exists in `src/qb_gsee_benchmark/features`.

The subsequent tracker labels assign P1-B to determinant coupling and P1-C to
orderability/MPO, then direct execution to P2. Therefore legacy partial DF
coverage must not be treated as satisfying the amended P1 contract. PI
reconciliation is required: insert a separately pilot-gated invariant DF block
before P2, or explicitly amend the appendix and G40 completion contract. P1-C
coefficient-matricization ranks are basis/ordering-sensitive and do not replace
this missing invariant interaction-spectrum block.

## FLAG: P2 MF-PROTO numerical conventions are not yet declared

The amended goal and feature appendix require a fully specified, versioned
mean-field protocol, including a small deterministic initial-guess set and a
predeclared MP2 regularizer grid. Neither source currently names the density
matrices in that initial-guess set, the SCF convergence/stability tolerances,
the stationary-solution deduplication tolerance and selection rule, the
thermal broadening or energy-window widths, or the numerical regularizers and
denominator thresholds. These choices change the resulting T1/T2 values and
applicability masks; they therefore cannot be introduced as undocumented
extractor defaults.

The FCIDUMP-only setting also rules out PySCF's atom-based initial guess for the
universal protocol because lattice/model dumps generally carry no atom or AO
metadata. Before P2 production, the PI must either ratify an explicit
FCIDUMP-native protocol (for example, density guesses constructed only from
the one-body matrix and shipped orbital basis, with all numerical grids frozen)
or provide a different reproducible convention. Extractor scaffolding and
small-system validation can proceed after that ruling, but no P2 pilot or
production artifact should claim appendix compliance before it.
