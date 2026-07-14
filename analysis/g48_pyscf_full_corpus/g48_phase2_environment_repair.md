# G-48 Phase 2 Environment Repair

## Status

The first stratified pilot remains immutable failure evidence and is not a
designation-quality campaign. All 30 method-task pairs reached a harvested
terminal outcome (24 completed, 6 failed), but the terminal verifier stopped
at 238/240 checks.

## Defect

The `ccsd_t_q080_34ee114f` row reached PySCF's DIIS singular-matrix handler.
PySCF 2.8.0 catches that exception through
`numpy.linalg.linalg.LinAlgError`; user-site NumPy 2.4.6 removed that module
path. The adapter failed closed with a null scored energy, but the exception
occurred before it could emit the required HF and post-HF convergence flags.

The nominal Mamba environment was not internally inconsistent. Python user
sites were enabled, so NumPy 2.4.6 and SciPy 1.18.0 from the user site
shadowed the environment's NumPy 1.26.4 and SciPy 1.12.0 while PySCF 2.8.0
and h5py 3.12.1 came from the Mamba prefix.

## Repair Contract

- Launch with `PYTHONNOUSERSITE=1` from interpreter startup.
- Pin PySCF 2.8.0, NumPy 1.26.4, SciPy 1.12.0, and h5py 3.12.1.
- Fail preflight unless user sites are disabled and every pinned package is
  imported from the selected Python prefix.
- Probe the exact `numpy.linalg.linalg.LinAlgError` path used by PySCF 2.8.0.
- Set `NUMEXPR_MAX_THREADS=128` before `NUMEXPR_NUM_THREADS=128` in Improv launchers.

Because this changes the numerical environment, the repair is not applied as
a one-row overwrite. A fresh detached bundle must rerun all 30 pilot pairs;
the failed pilot, its raw outputs, submission ledger, and PBS accounting stay
unchanged. Phase 3 remains gated on repaired-pilot review and written PI authorization.
