# G-33 H-chain threshold regeneration

The ratified O5 classes are applied by hydrogen-chain size:

| class | tasks | absolute threshold (Ha) |
| --- | ---: | ---: |
| H10 (STO-6G and cc-pVDZ) | 20 | 0.00159362 |
| H30 (STO-6G) | 10 | 0.003 |
| H50 (STO-6G) | 10 | 0.005 |

Evidence:

- `python scripts/generate_simons_hydrogen_chain_thresholds.py --check`
  reports the 20/10/10 split and a current, byte-stable instance.
- `python scripts/verify_simons_hydrogen_chain_thresholds.py` passes the named
  check `h_chain_thresholds_match_o5_classes` with 40/40 tasks matching O5.
- `python ../analysis/taxonomy_backfill/verify_o1_taxonomy_backfill.py` passes
  all six schema/taxonomy checks over the full public corpus.
- `PYTHONPATH=src:. pytest -q` passes 106 tests with one skip.

The frozen G-31 tranche plan has 216 solver-task rows and zero Simon H30/H50
rows, so no in-flight G-31 success label is changed. Any metrics bundle built
before this commit must nevertheless be regenerated because thresholds are
part of outcome classification.
