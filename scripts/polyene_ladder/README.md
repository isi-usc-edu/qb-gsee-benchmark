# Polyene ladder generator

This generator defines the project-owned G-30 all-trans polyene convention.
It does not reconstruct or redistribute the Hamiltonians used by Hachmann,
Cardoen, and Chan. Their 2006 results are cross-checks only.

## Frozen convention

- Molecules: planar all-trans `C_k H_(k+2)` for `k = 4, 8, 12, 16, 24`.
- Geometry: `R(C=C)=1.3693 Angstrom`, `R(C-C)=1.4244 Angstrom`,
  `R(C-H)=1.0820 Angstrom`, all valence angles `120 degrees`, and planar
  torsions. These values are transcribed from Figure 2 of Hachmann et al.,
  [arXiv:cond-mat/0606115](https://arxiv.org/abs/cond-mat/0606115).
- Electronic structure: PySCF RHF/STO-3G without density fitting.
- Active space: one carbon `2p_z` AO per site, symmetrically
  orthogonalized with `S^-1/2`, in carbon-chain order; `k` active electrons
  in `k` spatial orbitals, `MS2=0`.
- Frozen orbitals: all occupied RHF orbitals outside the occupied `pi_z`
  subspace. The FCIDUMP constant contains nuclear repulsion plus the frozen
  RHF-core energy.
- Absolute-energy convention: the FCIDUMP eigenvalue is the molecular total
  energy. Equivalently, the reference is RHF total energy plus active-space
  correlation energy.

The generator checks active-orbital orthonormality, occupied-subspace
separation, and equality between full-molecule RHF and the RHF determinant of
the emitted active-space Hamiltonian. For `k<=12`, it also computes exact FCI
and an explicit CI-vector residual.

## Usage

From the public repository:

```bash
python scripts/polyene_ladder/generate_polyene_ladder.py \
  --output-dir ../work/fcidumps/polyene_ladder \
  --analysis-dir ../analysis/polyene_ladder
```

The historical Table II totals and active-space correlation energies are
serialized in the generation manifest only as non-blocking cross-checks.
