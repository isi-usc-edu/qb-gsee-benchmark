# Diamond 2x2x2 variational-bound promotion

The direct `2x2x2` Gamma-point diamond supercell is released as the first
ab initio periodic-solid instance in the corpus. Its epistemic labels are
deliberately conservative:

- curation tier: `expanded`
- provenance grade: `variational_upper_bound`
- reference independence from panel solvers: `false`
- retained inequality: `E0 <= -77.56718950649218 Ha`

## Hamiltonian

- 16 carbon atoms, 64 valence electrons, 64 RHF spatial orbitals
- PySCF-PBC GTH-SZV/GTH-PADE, direct Gamma supercell, `exxdiv=None`
- raw FCIDUMP SHA-256:
  `c87c2c11ac799eacae40dcf965edeb7be959944a80aa17a1dd1a8a2d9bf24814`
- compressed FCIDUMP SHA-1:
  `2d1b17351997c692cf4379b8867442a80206dc22`
- generation/cold verification: 17/17 checks passed, including independent
  generic-reader RHF and primitive-k-mesh/supercell equivalence

## Reference

The bound is the lowest variational state from the 10-million-determinant T3
TrimCI runs, seed `20260712`. The wavefunction SHA-256 is
`829d76f266e1f6a0cae3225454c3b0444d330ca5726670297638cadeaacdecc9` and the
solver-internal orbital-rotation SHA-256 is
`15cba5dc26ff4d5aa190c4cd42a51990768bace2ab681f374959b4e1f69042e7`.
The engine content matches revision
`8944a2be6b2c1e2a4f6c6c8cbbf6355baa068393`.

The selected T3 PT2 magnitude, `0.06387459293438362 Ha`, is one-sided
distance-to-ground context and is not an uncertainty. The outer-seed spread,
`0.017823129403524263 Ha`, is a protocol diagnostic only. No rung passed the
original extrapolation gate, no nearly exact reference is claimed, and the
block2 M=500 attempt completed zero sweeps before its wall limit.

## Emission

- object key:
  `fcidumps/v1/periodic_solids/diamond_2x2x2_gamma_gth_szv.fcidump.gz`
- anonymous HTTPS: 200, 30,987,320 bytes, downloaded SHA-1 matches local
- bucket reconciliation: 868 objects before, 869 after this one authorized
  upload
- standard family-verifier contract: 9/9 checks passed

No push was performed. A future reference improvement must use the normal
versioned metadata path and cannot silently upgrade this grade.
