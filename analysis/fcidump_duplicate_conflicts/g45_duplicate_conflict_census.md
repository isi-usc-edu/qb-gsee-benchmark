# G45 FCIDUMP duplicate-conflict census

- Shipped FCIDUMPs scanned: **591**
- Scan failures: **0**
- Dumps with duplicate keys: **351**
- Dumps with conflicting keys: **4**
- Gate: `numpy.isclose(running_mean, next_value, rtol, atol)` with rtol=1e-08 and atol=1e-08

| Task UUID | Family | Conflicting keys | Duplicate keys | Max abs (Ha) | Max rel | Writer provenance |
|---|---|---:|---:|---:|---:|---|
| `34e0f543-0f23-405b-b06f-4be3cd556f9b` | fe_mo_co | 341029 | 341055 | 0.21489576404527999 | 1.9999522431530252 | TURBOMOLE V6.4 (structure optimization) and MOLCAS (molecular orbital integrals) |
| `81f65b14-2085-5443-b91b-3d791a55ab00` | simons_hydrogen_chains | 49733 | 396749 | 0.016786249941870307 | 1.9999928374364713 | PySCF 2.8.0 pyscf.tools.fcidump.from_scf; project C13 W2 generator analysis/simons_hydrogen_chains/generate_simons_hydrogen_chains.py version 2026-07-08.c13-w2; tol=1e-15 |
| `2cb87d49-8fc6-54d4-ad36-680cc7234ffc` | simons_hydrogen_chains | 5045 | 382364 | 1.0323593317897867e-05 | 1.9999914390033287 | PySCF 2.8.0 pyscf.tools.fcidump.from_scf; project C13 W2 generator analysis/simons_hydrogen_chains/generate_simons_hydrogen_chains.py version 2026-07-08.c13-w2; tol=1e-15 |
| `38105998-616e-50a7-8927-c8c990a9f9fb` | simons_hydrogen_chains | 21 | 350461 | 2.9558784617883533e-08 | 1.9998151002821278 | PySCF 2.8.0 pyscf.tools.fcidump.from_scf; project C13 W2 generator analysis/simons_hydrogen_chains/generate_simons_hydrogen_chains.py version 2026-07-08.c13-w2; tol=1e-15 |

The JSON and CSV contain all 591 per-dump rows, including zero-conflict
rows, declared and observed checksums, source URLs, container metadata,
maximum-disagreement keys, and writer provenance where known.

## Execution evidence

- Code revision: `2e2f0bfebf4b81eed39668d939b03f8c058e874d`
- PBS job: `7651319.imgt1` on `compute`
- Stdout: `../work/feature_runs/g45_duplicate_census/census.out` (`a27ecb29f2112507bec977a14348cd1d40c913c1851e5075be4da3798656028b`)
- Stderr: `../work/feature_runs/g45_duplicate_census/census.err` (`d0acd0d4bbabdceeeef82ac80706e0c0103934c33a56a5a3818a24f7e73d90e7`)
- Result: 591 selected; 591 success; 0 failed; exit status 0; walltime 00:15:05
- Command: `PYTHONPATH=src:. python scripts/run_g45_duplicate_census.py --cache-dir <shared-cache> --state-dir <run-state> --workers 96 --offline`
