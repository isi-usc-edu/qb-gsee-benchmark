# G-48 Phase 2 Environment Repair

## Status

The first stratified pilot remains immutable failure evidence and is not a
designation-quality campaign. All 30 method-task pairs reached a harvested
terminal outcome (24 completed, 6 failed), but the terminal verifier stopped
at 238/240 checks.

The first isolated-runtime repilot also remains immutable failure evidence.
All 30 rows passed the 27-check environment preflight and reached a harvested
outcome (24 completed, 6 failed), but the terminal verifier stopped at
268/270 because one raised solver exception lacked explicit convergence
metadata.

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

With user-site packages disabled, PySCF handled its legacy exception path and
then exposed the underlying `Singular matrix` from the CCSD stage. This is a
valid failed solver outcome, but adapter 0.4.0's generic-exception path stored
only a traceback. It therefore discarded the already-known HF convergence
flag and did not distinguish an unknown post-HF flag from a missing field.
The terminal verifier correctly rejected that provenance gap.

## Repair Contract

- Launch with `PYTHONNOUSERSITE=1` from interpreter startup.
- Pin PySCF 2.8.0, NumPy 1.26.4, SciPy 1.12.0, and h5py 3.12.1.
- Fail preflight unless user sites are disabled and every pinned package is
  imported from the selected Python prefix.
- Probe the exact `numpy.linalg.linalg.LinAlgError` path used by PySCF 2.8.0.
- Set `NUMEXPR_MAX_THREADS=128` before `NUMEXPR_NUM_THREADS=128` in Improv
  launchers.
- Adapter 0.4.1 preserves known HF convergence, records the failing solver
  stage, and emits an explicit null post-HF convergence flag when a stage
  raises before returning normally.

Neither repair is applied as a one-row overwrite. A fresh detached bundle
must rerun all 30 pilot pairs; both failed pilots, their raw outputs,
submission ledgers, and PBS accounting stay unchanged. Phase 3 remains gated
on repaired-pilot review and written PI authorization.
