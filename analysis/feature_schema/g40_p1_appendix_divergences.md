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
